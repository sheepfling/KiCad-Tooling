"""Review open connector alias pins when known role metadata differs."""

from __future__ import annotations

from collections.abc import Mapping

from .connector_footprint_peer_anchors import (
    connector_footprint_peer_common_anchor_pin_numbers,
)
from .connector_footprint_peer_groups import (
    complete_connector_footprint_peer_pin_inventory,
    connector_footprint_peer_candidate_groups,
)
from .connector_identity import native_pin_metadata_is_missing, partition_peer_assignments
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .models import NetlistContract

RULE_ID: DesignLintRuleId = "connector.footprint_peer_pin_metadata_open_outlier"


def connector_footprint_peer_pin_metadata_open_outliers(
    observed: NetlistContract,
    declared_references: tuple[str, ...] = (),
    peer_assignment_groups: Mapping[str, tuple[str, str]] | None = None,
) -> tuple[Candidate, ...]:
    """Review exact partial-open assignments on peers with different pin roles."""
    symbols = {reference.casefold(): item for reference, item in observed.component_symbols.items()}
    functions = {pin.casefold(): value for pin, value in observed.pin_functions.items()}
    electrical_types = {
        pin.casefold(): value for pin, value in observed.pin_electrical_types.items()
    }
    pin_nets: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin.casefold(), set()).add(net)

    candidates: list[Candidate] = []
    groups = connector_footprint_peer_candidate_groups(observed, declared_references)
    for group in groups:
        inventory = complete_connector_footprint_peer_pin_inventory(observed, group.references)
        if inventory is None:
            continue
        pin_numbers, displayed_numbers = inventory

        for pin_number in pin_numbers:
            metadata_by_reference: dict[str, tuple[str, str | None, str | None]] = {}
            assignments_by_pin: dict[str, tuple[str, ...]] = {}
            for reference in group.references:
                reference_key = reference.casefold()
                displayed_pin = displayed_numbers[reference_key][pin_number.casefold()]
                pin = f"{reference}.{displayed_pin}"
                function = functions.get(pin.casefold())
                electrical_type = electrical_types.get(pin.casefold())
                metadata_by_reference[reference_key] = (
                    pin,
                    function,
                    electrical_type,
                )
                assignments_by_pin[pin] = tuple(
                    sorted(
                        pin_nets.get(pin.casefold(), ()),
                        key=lambda item: (item.casefold(), item),
                    )
                )
            for peer_group, scoped_assignments, peer_basis in partition_peer_assignments(
                assignments_by_pin,
                peer_assignment_groups,
            ):
                if len(scoped_assignments) < 2:
                    continue
                scope_references = tuple(
                    sorted(
                        (pin.rsplit(".", 1)[0] for pin in scoped_assignments),
                        key=lambda item: (item.casefold(), item),
                    )
                )
                assignments = tuple(scoped_assignments.values())
                assigned = tuple(nets for nets in assignments if nets)
                if (
                    not assigned
                    or len(assigned) == len(assignments)
                    or any(len(nets) != 1 for nets in assigned)
                    or len({nets[0] for nets in assigned}) != 1
                ):
                    continue

                scoped_metadata = tuple(
                    metadata_by_reference[reference.casefold()] for reference in scope_references
                )
                if any(
                    native_pin_metadata_is_missing(function)
                    or native_pin_metadata_is_missing(electrical_type)
                    for _, function, electrical_type in scoped_metadata
                ):
                    continue
                mismatch_fields = tuple(
                    field
                    for field, index in (("pin_function", 1), ("pin_electrical_type", 2))
                    if len({(values[index] or "").strip().casefold() for values in scoped_metadata})
                    > 1
                )
                if not mismatch_fields:
                    continue

                anchors = connector_footprint_peer_common_anchor_pin_numbers(
                    pin_numbers,
                    pin_number,
                    scope_references,
                    displayed_numbers,
                    pin_nets,
                )
                if not anchors:
                    continue

                assignment_evidence = tuple(
                    f"{pin}={nets[0] if nets else '<unassigned>'}"
                    for pin, nets in sorted(
                        scoped_assignments.items(),
                        key=lambda item: (item[0].casefold(), item[0]),
                    )
                )
                metadata_evidence = tuple(
                    f"{pin}: function={function or ''}; electrical_type={electrical_type or ''}"
                    for pin, function, electrical_type in scoped_metadata
                )
                symbols_evidence = tuple(
                    f"{reference}={symbols[reference.casefold()]}" for reference in scope_references
                )
                displayed_target = displayed_numbers[group.references[0].casefold()][
                    pin_number.casefold()
                ]
                candidates.append(
                    Candidate(
                        rule_id=RULE_ID,
                        subject=f"{group.value} [{group.footprint}] pin {displayed_target}",
                        message=(
                            "Fitted connector aliases with matching value, footprint, and complete "
                            "pin inventory have different known function or electrical-type "
                            "metadata for this pin. It has one exact assigned net on some peers "
                            "and is open on others, while another pin has one exact common net. "
                            "Review the symbol pinouts and project requirement; the roles may be "
                            "intentionally different, and this finding does not require a connection."
                            + (
                                " The comparison is scoped to a source-reviewed peer-assignment group."
                                if peer_group is not None
                                else ""
                            )
                        ),
                        evidence={
                            "value": (group.value,),
                            "footprint": (group.footprint,),
                            "pin_number": (displayed_target,),
                            "metadata_mismatch_fields": mismatch_fields,
                            "peer_pin_metadata": metadata_evidence,
                            "assignments": assignment_evidence,
                            "peer_symbols": symbols_evidence,
                            "common_anchor_pin_numbers": anchors,
                            **(
                                {}
                                if peer_group is None
                                else {
                                    "peer_assignment_group": (peer_group,),
                                    "peer_assignment_basis": peer_basis,
                                }
                            ),
                        },
                    )
                )

    return tuple(
        sorted(
            candidates,
            key=lambda item: (
                item.subject.casefold(),
                tuple(item.evidence["assignments"]),
                tuple(item.evidence["peer_pin_metadata"]),
            ),
        )
    )
