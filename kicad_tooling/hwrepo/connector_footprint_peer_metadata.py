"""Review split connector-alias assignments when native pin metadata differs."""

from __future__ import annotations

from .connector_comparison_scope_types import ConnectorComparisonScopes
from .connector_footprint_peer_anchors import (
    connector_footprint_peer_common_anchor_pin_numbers,
)
from .connector_footprint_peer_groups import (
    complete_connector_footprint_peer_pin_inventory,
    connector_footprint_peer_candidate_groups,
)
from .connector_footprint_peer_pin_types import ConnectorFootprintPeerPinScanSource
from .connector_identity import native_pin_metadata_is_missing, partition_peer_assignments
from .design_lint_connector_footprint_peer_metadata_evidence import (
    ConnectorFootprintPeerMetadataCandidate,
    ConnectorFootprintPeerMetadataEvidence,
)
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .netlist_contract_models import NetlistContract

RULE_ID: DesignLintRuleId = "connector.footprint_peer_pin_metadata_assignment_divergence"


def connector_footprint_peer_pin_metadata_assignment_divergences(
    observed: NetlistContract,
    declared_references: tuple[str, ...] = (),
    peer_assignment_groups: ConnectorComparisonScopes | None = None,
) -> tuple[Candidate, ...]:
    """Review exact net splits on alias pins whose native role metadata differs.

    This is a review-only similarity check. A separate exact common-net pin is
    required as an anchor; the result does not establish that the split nets
    should be connected.
    """
    functions = {pin.casefold(): value for pin, value in observed.pin_functions.items()}
    electrical_types = {
        pin.casefold(): value for pin, value in observed.pin_electrical_types.items()
    }
    source = ConnectorFootprintPeerPinScanSource(
        observed=observed,
        declared_references=declared_references,
        peer_assignment_groups=peer_assignment_groups,
    )
    pin_nets: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin.casefold(), set()).add(net)

    candidates: list[Candidate] = []
    groups = connector_footprint_peer_candidate_groups(observed, declared_references)
    for group in groups:
        inventory = complete_connector_footprint_peer_pin_inventory(
            observed,
            group.references,
        )
        if inventory is None:
            continue
        pin_numbers = inventory.pin_numbers
        displayed_numbers = inventory.displayed_numbers_by_reference
        for pin_number in pin_numbers:
            pin_metadata: dict[str, tuple[str, str, str]] = {}
            for reference in group.references:
                reference_key = reference.casefold()
                displayed_pin = displayed_numbers[reference_key][pin_number.casefold()]
                pin = f"{reference}.{displayed_pin}"
                function = functions.get(pin.casefold())
                electrical_type = electrical_types.get(pin.casefold())
                function_value = function or ""
                electrical_type_value = electrical_type or ""
                if native_pin_metadata_is_missing(function) or native_pin_metadata_is_missing(
                    electrical_type
                ):
                    pin_metadata = {}
                    break
                pin_metadata[reference_key] = (pin, function_value, electrical_type_value)
            if len(pin_metadata) != len(group.references):
                continue

            all_assignments = {
                pin: tuple(sorted(pin_nets.get(pin.casefold(), ())))
                for pin, _, _ in pin_metadata.values()
            }
            for partition in partition_peer_assignments(
                all_assignments,
                peer_assignment_groups,
            ):
                peer_group = partition.peer_assignment_group
                scoped_assignments = partition.assignments_by_pin
                if len(scoped_assignments) < 2 or any(
                    len(nets) != 1 for nets in scoped_assignments.values()
                ):
                    continue
                if len({nets[0] for nets in scoped_assignments.values()}) < 2:
                    continue

                scope_references = tuple(
                    sorted(
                        (pin.rsplit(".", 1)[0] for pin in scoped_assignments),
                        key=lambda item: (item.casefold(), item),
                    )
                )
                scoped_metadata = tuple(
                    pin_metadata[reference.casefold()] for reference in scope_references
                )
                mismatch_fields = tuple(
                    field
                    for field, index in (("pin_function", 1), ("pin_electrical_type", 2))
                    if len({values[index].strip().casefold() for values in scoped_metadata}) > 1
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

                typed_source = ConnectorFootprintPeerMetadataEvidence.from_scan(
                    source=source,
                    group=group,
                    scope=partition,
                    kind="known_split",
                    pin_number=displayed_numbers[group.references[0].casefold()][
                        pin_number.casefold()
                    ],
                    common_anchor_pin_numbers=tuple(anchors),
                    metadata_mismatch_fields=mismatch_fields,
                )
                candidates.append(
                    ConnectorFootprintPeerMetadataCandidate.from_source_evidence(
                        typed_source,
                        subject=(
                            f"{group.value} [{group.footprint}] pin "
                            f"{displayed_numbers[group.references[0].casefold()][pin_number.casefold()]}"
                        ),
                        message=(
                            "Fitted connector aliases with the same value and footprint clues and "
                            "a complete matching pin inventory have different native function or "
                            "electrical-type metadata for this pin. Its assigned nets differ in "
                            "the current peer scope, while another pin has one exact common net. "
                            "Review the symbol pinouts and project requirement; this review prompt "
                            "does not infer that the nets should connect."
                            + (
                                " The comparison is scoped to a source-reviewed peer-assignment group."
                                if peer_group is not None
                                else ""
                            )
                        ),
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
