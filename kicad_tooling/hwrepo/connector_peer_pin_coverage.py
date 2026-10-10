"""Applicability and evidence coverage for connector peer-pin rules."""

from __future__ import annotations

from collections.abc import Mapping

from .connector_identity import (
    connector_candidate_references,
    has_meaningful_pin_function,
    partition_peer_assignments,
    similar_connector_pin_groups,
)
from .connector_peer_pin_models import (
    ConnectorPartIdPeerPinCoverage,
    ConnectorPeerPinHeuristicCoverage,
)
from .connector_peer_pin_scan import (
    scan_connector_part_id_peer_pins,
)
from .models import (
    ConnectorMappedPinEvidence,
    NetlistContract,
)


def connector_peer_pin_heuristic_coverage(
    observed: NetlistContract,
    netlist_sha256: str,
    declared_references: tuple[str, ...] = (),
    reviewed_connector_pins: Mapping[str, ConnectorMappedPinEvidence] | None = None,
    peer_assignment_groups: Mapping[str, tuple[str, str]] | None = None,
    *,
    repeated_function_finding_count: int,
    peer_pin_outlier_finding_count: int,
    peer_pin_divergence_finding_count: int,
    part_id_peer_pin_outlier_finding_count: int = 0,
    part_id_peer_pin_divergence_finding_count: int = 0,
) -> ConnectorPeerPinHeuristicCoverage:
    """Summarize exact-symbol and guarded PART_ID connector comparisons."""
    candidate_references = connector_candidate_references(observed, declared_references)
    unpopulated = {reference.casefold() for reference in observed.dnp_components}
    fitted_references = tuple(
        reference for reference in candidate_references if reference.casefold() not in unpopulated
    )
    symbols_by_reference = {
        reference.casefold(): symbol for reference, symbol in observed.component_symbols.items()
    }
    pin_functions = {pin.casefold(): function for pin, function in observed.pin_functions.items()}
    pin_inventory = {
        reference.casefold(): tuple(pin_numbers)
        for reference, pin_numbers in observed.component_pin_numbers.items()
    }
    pins_by_reference: dict[str, set[str]] = {}
    for reference in fitted_references:
        pins = set(pin_inventory.get(reference.casefold(), ()))
        pins.update(
            pin.rsplit(".", 1)[1]
            for pin in observed.pin_functions
            if pin.rsplit(".", 1)[0].casefold() == reference.casefold()
        )
        pins_by_reference[reference.casefold()] = pins

    references_by_symbol: dict[str, set[str]] = {}
    for reference in fitted_references:
        symbol = symbols_by_reference.get(reference.casefold())
        if symbol is None:
            continue
        symbol_key = symbol.casefold()
        references_by_symbol.setdefault(symbol_key, set()).add(reference)
    exact_symbol_groups = tuple(
        (symbol_key, tuple(sorted(references, key=lambda item: (item.casefold(), item))))
        for symbol_key, references in sorted(references_by_symbol.items())
        if len(references) >= 2
    )
    observed_pin_numbers_by_reference: dict[str, set[str]] = {}
    for pin in observed.pin_functions:
        reference, pin_number = pin.rsplit(".", 1)
        observed_pin_numbers_by_reference.setdefault(reference.casefold(), set()).add(
            pin_number.casefold()
        )
    for assignments in (*observed.nets.values(), *observed.unconnected_nets.values()):
        for pin in assignments:
            reference, pin_number = pin.rsplit(".", 1)
            observed_pin_numbers_by_reference.setdefault(reference.casefold(), set()).add(
                pin_number.casefold()
            )
    incomplete_inventory_reference_set: set[str] = set()
    for _, references in exact_symbol_groups:
        inventories_by_reference = {
            reference: frozenset(
                pin.casefold() for pin in pin_inventory.get(reference.casefold(), ())
            )
            for reference in references
        }
        inventory_counts: dict[frozenset[str], int] = {}
        for inventory in inventories_by_reference.values():
            inventory_counts[inventory] = inventory_counts.get(inventory, 0) + 1
        highest_inventory_count = max(inventory_counts.values(), default=0)
        most_common_inventories = tuple(
            inventory
            for inventory, count in inventory_counts.items()
            if count == highest_inventory_count
        )
        if len(inventory_counts) > 1:
            if len(most_common_inventories) == 1:
                incomplete_inventory_reference_set.update(
                    reference
                    for reference, inventory in inventories_by_reference.items()
                    if inventory != most_common_inventories[0]
                )
            else:
                incomplete_inventory_reference_set.update(references)
        for reference, inventory in inventories_by_reference.items():
            if not inventory or not observed_pin_numbers_by_reference.get(
                reference.casefold(), set()
            ).issubset(inventory):
                incomplete_inventory_reference_set.add(reference)
    incomplete_inventory_references = tuple(
        sorted(incomplete_inventory_reference_set, key=lambda item: (item.casefold(), item))
    )

    pin_nets: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin, set()).add(net)
    peer_pin_group_count = 0
    peer_pin_groups_with_unknown_function_count = 0
    peer_pin_groups_with_meaningful_functions_count = 0
    peer_pin_groups_with_common_assignment_count = 0
    peer_pin_groups_with_different_assignments_count = 0
    peer_pin_groups_all_unassigned_count = 0
    peer_pin_groups_with_open_assignment_count = 0
    for _, references in exact_symbol_groups:
        pin_numbers: set[str] = set()
        for reference in references:
            pin_numbers.update(pins_by_reference[reference.casefold()])
        for pin_number in sorted(pin_numbers, key=lambda item: (item.casefold(), item)):
            assignments = {
                f"{reference}.{pin_number}": tuple(
                    sorted(pin_nets.get(f"{reference}.{pin_number}", ()))
                )
                for reference in references
                if pin_number in pins_by_reference[reference.casefold()]
            }
            for _, scoped_assignments, _ in partition_peer_assignments(
                assignments,
                peer_assignment_groups,
            ):
                if len(scoped_assignments) < 2:
                    continue
                peer_pin_group_count += 1
                unknown_function = any(
                    not has_meaningful_pin_function(pin_functions.get(pin.casefold()))
                    for pin in scoped_assignments
                )
                if unknown_function:
                    peer_pin_groups_with_unknown_function_count += 1
                else:
                    peer_pin_groups_with_meaningful_functions_count += 1
                assignments_by_peer = tuple(scoped_assignments.values())
                if any(not nets for nets in assignments_by_peer):
                    peer_pin_groups_with_open_assignment_count += 1
                if all(not nets for nets in assignments_by_peer):
                    peer_pin_groups_all_unassigned_count += 1
                elif len(set(assignments_by_peer)) > 1:
                    peer_pin_groups_with_different_assignments_count += 1
                else:
                    peer_pin_groups_with_common_assignment_count += 1

    repeated_function_groups = similar_connector_pin_groups(
        observed,
        declared_references,
        reviewed_connector_pins,
        peer_assignment_groups,
        include_consistent=True,
    )
    repeated_function_groups_with_common_assignment_count = 0
    repeated_function_groups_with_different_assignments_count = 0
    repeated_function_groups_all_unassigned_count = 0
    repeated_function_groups_with_open_assignment_count = 0
    for group in repeated_function_groups:
        assignments = tuple(group.pins.values())
        if any(not nets for nets in assignments):
            repeated_function_groups_with_open_assignment_count += 1
        if all(not nets for nets in assignments):
            repeated_function_groups_all_unassigned_count += 1
        elif len(set(assignments)) > 1:
            repeated_function_groups_with_different_assignments_count += 1
        else:
            repeated_function_groups_with_common_assignment_count += 1

    part_id_scan = scan_connector_part_id_peer_pins(
        observed,
        declared_references,
        peer_assignment_groups,
    )
    part_id_unknown_function_count = 0
    part_id_meaningful_function_count = 0
    part_id_ambiguous_assignment_count = 0
    part_id_common_assignment_count = 0
    part_id_different_assignment_count = 0
    part_id_all_unassigned_count = 0
    part_id_open_assignment_count = 0
    for group in part_id_scan.pin_groups:
        if has_meaningful_pin_function(group.pin_function):
            part_id_meaningful_function_count += 1
        else:
            part_id_unknown_function_count += 1
        assignments = tuple(group.assignments.values())
        if any(len(nets) > 1 for nets in assignments):
            part_id_ambiguous_assignment_count += 1
            continue
        if any(not nets for nets in assignments):
            part_id_open_assignment_count += 1
        if all(not nets for nets in assignments):
            part_id_all_unassigned_count += 1
        elif len(set(assignments)) > 1:
            part_id_different_assignment_count += 1
        else:
            part_id_common_assignment_count += 1

    incomplete_part_id_evidence_count = (
        part_id_scan.incomplete_component_identity_group_count
        + part_id_scan.incomplete_pin_inventory_group_count
        + part_id_scan.incomplete_pin_metadata_group_count
    )
    part_id_coverage_status = (
        "NO_CANDIDATES"
        if part_id_scan.candidate_group_count == 0
        else "INCOMPLETE_EVIDENCE"
        if part_id_scan.eligible_peer_group_count == 0
        else "NO_COMPARABLE_PIN_GROUPS"
        if not part_id_scan.pin_groups
        else "PARTIALLY_EVALUATED"
        if incomplete_part_id_evidence_count > 0
        else "EVALUATED"
    )
    part_id_alias_coverage = ConnectorPartIdPeerPinCoverage(
        status=part_id_coverage_status,
        netlist_sha256=netlist_sha256,
        candidate_group_count=part_id_scan.candidate_group_count,
        incomplete_component_identity_group_count=(
            part_id_scan.incomplete_component_identity_group_count
        ),
        incomplete_pin_inventory_group_count=part_id_scan.incomplete_pin_inventory_group_count,
        incomplete_pin_metadata_group_count=part_id_scan.incomplete_pin_metadata_group_count,
        eligible_peer_group_count=part_id_scan.eligible_peer_group_count,
        incomplete_pin_inventory_references=part_id_scan.incomplete_pin_inventory_references,
        compared_pin_group_count=len(part_id_scan.pin_groups),
        unknown_function_pin_group_count=part_id_unknown_function_count,
        meaningful_function_pin_group_count=part_id_meaningful_function_count,
        ambiguous_assignment_pin_group_count=part_id_ambiguous_assignment_count,
        common_assignment_pin_group_count=part_id_common_assignment_count,
        different_assignment_pin_group_count=part_id_different_assignment_count,
        all_unassigned_pin_group_count=part_id_all_unassigned_count,
        open_assignment_pin_group_count=part_id_open_assignment_count,
        outlier_finding_count=part_id_peer_pin_outlier_finding_count,
        divergence_finding_count=part_id_peer_pin_divergence_finding_count,
    )

    if not candidate_references:
        status = "NO_CONNECTOR_CANDIDATES"
    elif not fitted_references:
        status = "NO_FITTED_CONNECTORS"
    elif not exact_symbol_groups:
        status = "NO_EXACT_SYMBOL_PEERS"
    elif incomplete_inventory_references:
        status = "INCOMPLETE_PIN_INVENTORY"
    elif not peer_pin_group_count:
        status = "NO_COMPARABLE_PIN_GROUPS"
    else:
        status = "EVALUATED"
    return ConnectorPeerPinHeuristicCoverage(
        status=status,
        netlist_sha256=netlist_sha256,
        scope=(
            "Named connector functions are compared only by the existing bounded role or exact "
            "symbol/function rules. Generic peer assignments compare exact symbol and pin number; "
            "cross-symbol comparisons require a shared PART_ID plus matching component, inventory, "
            "function, and electrical-type evidence. "
            "Coverage records evaluated evidence; it does not assert that peer nets must match."
        ),
        connector_candidate_count=len(candidate_references),
        fitted_connector_count=len(fitted_references),
        exact_symbol_peer_group_count=len(exact_symbol_groups),
        exact_symbol_pin_group_count=peer_pin_group_count,
        exact_symbol_pin_groups_with_unknown_function_count=(
            peer_pin_groups_with_unknown_function_count
        ),
        exact_symbol_pin_groups_with_meaningful_functions_count=(
            peer_pin_groups_with_meaningful_functions_count
        ),
        exact_symbol_pin_groups_with_common_assignment_count=(
            peer_pin_groups_with_common_assignment_count
        ),
        exact_symbol_pin_groups_with_different_assignments_count=(
            peer_pin_groups_with_different_assignments_count
        ),
        exact_symbol_pin_groups_all_unassigned_count=peer_pin_groups_all_unassigned_count,
        exact_symbol_pin_groups_with_open_assignment_count=(
            peer_pin_groups_with_open_assignment_count
        ),
        part_id_alias_coverage=part_id_alias_coverage,
        incomplete_pin_inventory_references=incomplete_inventory_references,
        repeated_function_group_count=len(repeated_function_groups),
        repeated_function_groups_with_common_assignment_count=(
            repeated_function_groups_with_common_assignment_count
        ),
        repeated_function_groups_with_different_assignments_count=(
            repeated_function_groups_with_different_assignments_count
        ),
        repeated_function_groups_all_unassigned_count=repeated_function_groups_all_unassigned_count,
        repeated_function_groups_with_open_assignment_count=(
            repeated_function_groups_with_open_assignment_count
        ),
        repeated_function_finding_count=repeated_function_finding_count,
        peer_pin_outlier_finding_count=peer_pin_outlier_finding_count,
        peer_pin_divergence_finding_count=peer_pin_divergence_finding_count,
    )
