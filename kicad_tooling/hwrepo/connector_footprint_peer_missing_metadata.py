"""Review split connector-alias assignments when native pin metadata is missing."""

from __future__ import annotations

from collections.abc import Mapping

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

RULE_ID: DesignLintRuleId = "connector.footprint_peer_pin_missing_metadata_assignment_divergence"


def connector_footprint_peer_pin_missing_metadata_assignment_divergences(
    observed: NetlistContract,
    declared_references: tuple[str, ...] = (),
    peer_assignment_groups: Mapping[str, tuple[str, str]] | None = None,
) -> tuple[Candidate, ...]:
    """Review a split pin when a fitted footprint-alias peer lacks its role metadata."""
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
    for group in connector_footprint_peer_candidate_groups(
        observed,
        declared_references,
        include_part_id_peers=True,
    ):
        inventory = complete_connector_footprint_peer_pin_inventory(observed, group.references)
        if inventory is None:
            continue
        pin_numbers = inventory.pin_numbers
        displayed_numbers = inventory.displayed_numbers_by_reference
        for pin_number in pin_numbers:
            missing_by_reference: dict[str, tuple[str, ...]] = {}
            metadata_by_reference: dict[str, tuple[str, str, str]] = {}
            assignments_by_pin: dict[str, tuple[str, ...]] = {}
            for reference in group.references:
                reference_key = reference.casefold()
                displayed_pin = displayed_numbers[reference_key][pin_number.casefold()]
                pin = f"{reference}.{displayed_pin}"
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
                assignments_by_pin[pin] = tuple(sorted(pin_nets.get(pin.casefold(), ())))

            if not missing_by_reference:
                continue

            for partition in partition_peer_assignments(
                assignments_by_pin,
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
                scope_missing = tuple(
                    f"{metadata_by_reference[reference.casefold()][0]}: {field}"
                    for reference in scope_references
                    for field in missing_by_reference.get(reference.casefold(), ())
                )
                if not scope_missing:
                    continue

                anchors: list[str] = []
                for anchor_number in pin_numbers:
                    if anchor_number.casefold() == pin_number.casefold():
                        continue
                    anchor_assignments = tuple(
                        tuple(
                            sorted(
                                pin_nets.get(
                                    (
                                        f"{reference}.{displayed_numbers[reference.casefold()][anchor_number.casefold()]}"
                                    ).casefold(),
                                    (),
                                )
                            )
                        )
                        for reference in scope_references
                    )
                    if (
                        anchor_assignments
                        and all(len(nets) == 1 for nets in anchor_assignments)
                        and len({nets[0] for nets in anchor_assignments}) == 1
                    ):
                        anchors.append(anchor_number)
                if not anchors:
                    continue

                displayed_target = displayed_numbers[group.references[0].casefold()][
                    pin_number.casefold()
                ]
                typed_source = ConnectorFootprintPeerMetadataEvidence.from_scan(
                    source=source,
                    group=group,
                    scope=partition,
                    kind="missing_split",
                    pin_number=displayed_target,
                    common_anchor_pin_numbers=tuple(anchors),
                )
                candidates.append(
                    ConnectorFootprintPeerMetadataCandidate.from_source_evidence(
                        typed_source,
                        subject=f"{group.value} [{group.footprint}] pin {displayed_target}",
                        message=(
                            "Fitted connector aliases with the same value and footprint clues"
                            + (" and PART_ID" if group.part_id is not None else "")
                            + " and a complete matching pin inventory have missing or unnamed native "
                            "function or electrical-type metadata for this pin. Its assigned nets "
                            "differ in the current peer scope, while another pin has one exact "
                            "common net. Review the symbol pinouts and project requirement; this "
                            "prompt does not establish a shared electrical role or instruct that "
                            "the nets be joined."
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
                tuple(item.evidence["missing_metadata"]),
            ),
        )
    )
