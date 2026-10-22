"""Review open connector peer pins when native role metadata is incomplete."""

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

RULE_ID: DesignLintRuleId = "connector.footprint_peer_pin_missing_metadata_open_outlier"


def connector_footprint_peer_pin_missing_metadata_open_outliers(
    observed: NetlistContract,
    declared_references: tuple[str, ...] = (),
    peer_assignment_groups: Mapping[str, tuple[str, str]] | None = None,
) -> tuple[Candidate, ...]:
    """Review a partially open peer pin when exact assignments and an anchor agree."""
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
    groups = connector_footprint_peer_candidate_groups(
        observed,
        declared_references,
        include_part_id_peers=True,
    )
    for group in groups:
        inventory = complete_connector_footprint_peer_pin_inventory(observed, group.references)
        if inventory is None:
            continue
        pin_numbers, displayed_numbers = inventory

        for pin_number in pin_numbers:
            assignments_by_pin: dict[str, tuple[str, ...]] = {}
            metadata_by_reference: dict[str, tuple[str, str, str]] = {}
            missing_by_reference: dict[str, tuple[str, ...]] = {}
            for reference in group.references:
                reference_key = reference.casefold()
                display_pin = displayed_numbers[reference_key][pin_number.casefold()]
                pin = f"{reference}.{display_pin}"
                function = functions.get(pin.casefold())
                electrical_type = electrical_types.get(pin.casefold())
                missing_fields = tuple(
                    field
                    for field, value in (
                        ("pin_function", function),
                        ("pin_electrical_type", electrical_type),
                    )
                    if native_pin_metadata_is_missing(value)
                )
                if missing_fields:
                    missing_by_reference[reference_key] = missing_fields
                metadata_by_reference[reference_key] = (
                    pin,
                    "<missing>"
                    if native_pin_metadata_is_missing(function)
                    else (function or "").strip(),
                    "<missing>"
                    if native_pin_metadata_is_missing(electrical_type)
                    else (electrical_type or "").strip(),
                )
                assignments_by_pin[pin] = tuple(
                    sorted(
                        pin_nets.get(pin.casefold(), ()), key=lambda item: (item.casefold(), item)
                    )
                )

            if not missing_by_reference:
                continue

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
                if not any(
                    reference.casefold() in missing_by_reference for reference in scope_references
                ):
                    continue

                assignment_values = tuple(scoped_assignments.values())
                assigned_values = tuple(nets for nets in assignment_values if nets)
                if (
                    not assigned_values
                    or len(assigned_values) == len(assignment_values)
                    or any(len(nets) != 1 for nets in assigned_values)
                    or len({nets[0] for nets in assigned_values}) != 1
                ):
                    continue

                if not _metadata_agrees_where_present(
                    scope_references,
                    pin_number,
                    displayed_numbers,
                    functions,
                    electrical_types,
                ):
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

                missing_evidence = tuple(
                    f"{metadata_by_reference[reference.casefold()][0]}: {field}"
                    for reference in scope_references
                    for field in missing_by_reference.get(reference.casefold(), ())
                )
                metadata_evidence = tuple(
                    f"{metadata_by_reference[reference.casefold()][0]}: "
                    f"function={metadata_by_reference[reference.casefold()][1]}; "
                    f"electrical_type={metadata_by_reference[reference.casefold()][2]}"
                    for reference in scope_references
                )
                assignment_evidence = tuple(
                    f"{pin}={nets[0] if nets else '<unassigned>'}"
                    for pin, nets in sorted(
                        scoped_assignments.items(),
                        key=lambda item: (item[0].casefold(), item[0]),
                    )
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
                        subject=(f"{group.value} [{group.footprint}] pin {displayed_target}"),
                        message=(
                            "Fitted connector aliases with matching value, footprint, and complete "
                            "pin inventory have missing or unnamed native role metadata for this "
                            "pin. It is assigned to one exact net on some peers and unassigned on "
                            "others, while another pin has one exact common net. Review the exact "
                            "symbol pinouts and project requirement; these clues do not establish "
                            "a shared role or require the open pin to connect."
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
                            "missing_metadata": missing_evidence,
                            "peer_pin_metadata": metadata_evidence,
                            "assignments": assignment_evidence,
                            "symbols": symbols_evidence,
                            "peer_identity_basis": (
                                "part_id" if group.part_id is not None else "footprint_value",
                            ),
                            **({} if group.part_id is None else {"part_id": (group.part_id,)}),
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
                tuple(item.evidence["missing_metadata"]),
            ),
        )
    )


def _metadata_agrees_where_present(
    references: tuple[str, ...],
    pin_number: str,
    displayed_numbers: Mapping[str, Mapping[str, str]],
    functions: Mapping[str, str],
    electrical_types: Mapping[str, str],
) -> bool:
    """Reject scopes whose available metadata already shows different pin roles."""
    for metadata in (functions, electrical_types):
        values: set[str] = set()
        for reference in references:
            value = metadata.get(
                f"{reference}.{displayed_numbers[reference.casefold()][pin_number.casefold()]}".casefold()
            )
            if value is not None and not native_pin_metadata_is_missing(value):
                values.add(value.strip().casefold())
        if len(values) > 1:
            return False
    return True
