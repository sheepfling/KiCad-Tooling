"""Review findings for connector peer-pin assignment differences."""

from __future__ import annotations

from collections.abc import Mapping

from .connector_identity import (
    connector_candidate_references,
    has_meaningful_pin_function,
    partition_peer_assignments,
)
from .connector_peer_pin_scan import (
    ConnectorPeerPinAssignmentDivergence,
    ConnectorPeerPinAssignmentOutlier,
    scan_connector_part_id_peer_pins,
    unique_peer_pin_majority,
)
from .models import NetlistContract


def connector_peer_pin_assignment_outliers(
    observed: NetlistContract,
    declared_references: tuple[str, ...] = (),
    peer_assignment_groups: Mapping[str, tuple[str, str]] | None = None,
) -> tuple[ConnectorPeerPinAssignmentOutlier, ...]:
    """Find comparable connector peer pins with incomplete or minority assignments.

    This rule is reserved for pins whose function metadata is absent or only
    contains a generic Pin_N placeholder, since the named-function comparison
    already covers pins with meaningful roles. Cross-symbol peers must share a
    native PART_ID and match value, footprint, complete pin inventory, pin
    functions, and electrical types. These identities identify review
    candidates; they do not establish that their nets must be common.
    """
    unpopulated = {reference.casefold() for reference in observed.dnp_components}
    connector_references = {
        reference.casefold()
        for reference in connector_candidate_references(observed, declared_references)
    }
    pin_nets: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin, set()).add(net)

    grouped: dict[tuple[str, str], dict[str, tuple[str, ...]]] = {}
    symbols: dict[str, str] = {}
    functions_by_pin = {pin.casefold(): value for pin, value in observed.pin_functions.items()}
    for reference, symbol in observed.component_symbols.items():
        if reference.casefold() not in connector_references or reference.casefold() in unpopulated:
            continue
        pin_numbers = set(observed.component_pin_numbers.get(reference, ()))
        pin_numbers.update(
            pin.rsplit(".", 1)[1]
            for pin in observed.pin_functions
            if pin.rsplit(".", 1)[0].casefold() == reference.casefold()
        )
        for pin_number in pin_numbers:
            pin = f"{reference}.{pin_number}"
            grouped.setdefault((symbol.casefold(), pin_number), {})[pin] = tuple(
                sorted(pin_nets.get(pin, ()))
            )
            symbols[symbol.casefold()] = symbol

    exact_results: list[ConnectorPeerPinAssignmentOutlier] = []
    for (symbol_key, pin_number), assignments in sorted(grouped.items()):
        for peer_group, scoped_assignments, peer_review in partition_peer_assignments(
            assignments,
            peer_assignment_groups,
        ):
            if len(scoped_assignments) < 2 or len(set(scoped_assignments.values())) == 1:
                continue
            # A named-function comparison is more direct and already reports these
            # mismatches. This check fills the gap where at least one peer function
            # is absent or only has a generic Pin_N placeholder.
            if all(
                has_meaningful_pin_function(functions_by_pin.get(pin.casefold()))
                for pin in scoped_assignments
            ):
                continue

            signatures = list(scoped_assignments.values())
            if any(not signature for signature in signatures):
                if not any(signature for signature in signatures):
                    continue
                outlier_pins = tuple(
                    sorted(pin for pin, nets in scoped_assignments.items() if not nets)
                )
            else:
                majority = unique_peer_pin_majority(scoped_assignments)
                if majority is None:
                    continue
                outlier_pins = tuple(
                    sorted(pin for pin, nets in scoped_assignments.items() if nets != majority)
                )
            if not outlier_pins:
                continue
            exact_results.append(
                ConnectorPeerPinAssignmentOutlier(
                    symbol=symbols[symbol_key],
                    pin_number=pin_number,
                    assignments=dict(sorted(scoped_assignments.items())),
                    outlier_pins=outlier_pins,
                    peer_assignment_group=peer_group,
                    peer_assignment_basis=peer_review,
                )
            )

    part_id_results: list[ConnectorPeerPinAssignmentOutlier] = []
    part_id_scan = scan_connector_part_id_peer_pins(
        observed,
        declared_references,
        peer_assignment_groups,
    )
    for group in part_id_scan.pin_groups:
        if any(len(nets) > 1 for nets in group.assignments.values()):
            continue
        if has_meaningful_pin_function(group.pin_function):
            continue
        signatures = tuple(group.assignments.values())
        if len(set(signatures)) == 1:
            continue
        if any(not signature for signature in signatures):
            if not any(signatures):
                continue
            outlier_pins = tuple(
                sorted(
                    (pin for pin, nets in group.assignments.items() if not nets),
                    key=lambda item: (item.casefold(), item),
                )
            )
        else:
            majority = unique_peer_pin_majority(group.assignments)
            if majority is None:
                continue
            outlier_pins = tuple(
                sorted(
                    (pin for pin, nets in group.assignments.items() if nets != majority),
                    key=lambda item: (item.casefold(), item),
                )
            )
        if not outlier_pins:
            continue
        part_id_results.append(
            ConnectorPeerPinAssignmentOutlier(
                symbol="multiple connector symbols",
                pin_number=group.pin_number,
                assignments=group.assignments,
                outlier_pins=outlier_pins,
                peer_assignment_group=group.peer_assignment_group,
                peer_assignment_basis=group.peer_assignment_basis,
                peer_identity_basis="part_id",
                peer_identity=group.part_id,
                peer_symbols=group.symbols,
            )
        )

    def is_subsumed_by_part_id(
        exact: ConnectorPeerPinAssignmentOutlier,
        aliases: tuple[ConnectorPeerPinAssignmentOutlier, ...],
    ) -> bool:
        exact_assignments = {pin.casefold(): nets for pin, nets in exact.assignments.items()}
        exact_outliers = {pin.casefold() for pin in exact.outlier_pins}
        for alias in aliases:
            if exact.pin_number.casefold() != alias.pin_number.casefold():
                continue
            alias_assignments = {pin.casefold(): nets for pin, nets in alias.assignments.items()}
            alias_outliers = {pin.casefold() for pin in alias.outlier_pins}
            if (
                exact_assignments.keys() <= alias_assignments.keys()
                and all(alias_assignments[pin] == nets for pin, nets in exact_assignments.items())
                and exact_outliers <= alias_outliers
            ):
                return True
        return False

    results = [
        *part_id_results,
        *(
            item
            for item in exact_results
            if not is_subsumed_by_part_id(item, tuple(part_id_results))
        ),
    ]
    return tuple(
        sorted(
            results,
            key=lambda item: (
                0 if item.peer_identity_basis == "part_id" else 1,
                item.peer_identity.casefold(),
                item.symbol.casefold(),
                item.pin_number.casefold(),
                tuple(pin.casefold() for pin in item.outlier_pins),
            ),
        )
    )


def connector_peer_pin_assignment_divergences(
    observed: NetlistContract,
    declared_references: tuple[str, ...] = (),
    peer_assignment_groups: Mapping[str, tuple[str, str]] | None = None,
) -> tuple[ConnectorPeerPinAssignmentDivergence, ...]:
    """Review comparable assigned peer contacts that differ with unknown roles.

    The outlier rule above needs a majority assignment to identify a minority
    peer. This lower-confidence check reports fully assigned groups with
    conflicting nets and absent or generic pin-function metadata. Cross-symbol
    peers must pass the same native PART_ID, component identity, inventory, and
    pin-metadata checks as the outlier rule. It does not infer a required
    connection.
    """
    unpopulated = {reference.casefold() for reference in observed.dnp_components}
    connector_references = {
        reference.casefold()
        for reference in connector_candidate_references(observed, declared_references)
    }
    pin_nets: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin.casefold(), set()).add(net)

    grouped: dict[tuple[str, str], dict[str, tuple[str, ...]]] = {}
    symbols: dict[str, str] = {}
    pin_functions = {pin.casefold(): function for pin, function in observed.pin_functions.items()}
    for reference, symbol in observed.component_symbols.items():
        if reference.casefold() not in connector_references or reference.casefold() in unpopulated:
            continue
        pin_numbers = set(observed.component_pin_numbers.get(reference, ()))
        pin_numbers.update(
            pin.rsplit(".", 1)[1]
            for pin in observed.pin_functions
            if pin.rsplit(".", 1)[0].casefold() == reference.casefold()
        )
        for pin_number in pin_numbers:
            pin = f"{reference}.{pin_number}"
            grouped.setdefault((symbol.casefold(), pin_number.casefold()), {})[pin] = tuple(
                sorted(pin_nets.get(pin.casefold(), ()))
            )
            symbols[symbol.casefold()] = symbol

    results: list[ConnectorPeerPinAssignmentDivergence] = []
    for (symbol_key, pin_number_key), assignments in sorted(grouped.items()):
        for peer_group, scoped_assignments, peer_review in partition_peer_assignments(
            assignments,
            peer_assignment_groups,
        ):
            if len(scoped_assignments) < 2 or any(not nets for nets in scoped_assignments.values()):
                continue
            if len(set(scoped_assignments.values())) == 1:
                continue
            if unique_peer_pin_majority(scoped_assignments) is not None:
                continue
            missing_function_pins = tuple(
                sorted(
                    pin
                    for pin in scoped_assignments
                    if not has_meaningful_pin_function(pin_functions.get(pin.casefold()))
                )
            )
            if (
                len(missing_function_pins) < 1
                or len(scoped_assignments) - len(missing_function_pins) >= 2
            ):
                continue
            pin_number = next(
                pin.rsplit(".", 1)[1]
                for pin in scoped_assignments
                if pin.rsplit(".", 1)[1].casefold() == pin_number_key
            )
            results.append(
                ConnectorPeerPinAssignmentDivergence(
                    symbol=symbols[symbol_key],
                    pin_number=pin_number,
                    assignments=dict(sorted(scoped_assignments.items())),
                    missing_function_pins=missing_function_pins,
                    peer_assignment_group=peer_group,
                    peer_assignment_basis=peer_review,
                )
            )
    exact_results = tuple(results)
    part_id_results: list[ConnectorPeerPinAssignmentDivergence] = []
    part_id_scan = scan_connector_part_id_peer_pins(
        observed,
        declared_references,
        peer_assignment_groups,
    )
    for group in part_id_scan.pin_groups:
        assignments = group.assignments
        if any(len(nets) != 1 for nets in assignments.values()):
            continue
        if len(set(assignments.values())) < 2 or unique_peer_pin_majority(assignments) is not None:
            continue
        if has_meaningful_pin_function(group.pin_function):
            continue
        missing_function_pins = tuple(sorted(assignments, key=lambda item: (item.casefold(), item)))
        part_id_results.append(
            ConnectorPeerPinAssignmentDivergence(
                symbol="multiple connector symbols",
                pin_number=group.pin_number,
                assignments=assignments,
                missing_function_pins=missing_function_pins,
                peer_assignment_group=group.peer_assignment_group,
                peer_assignment_basis=group.peer_assignment_basis,
                peer_identity_basis="part_id",
                peer_identity=group.part_id,
                peer_symbols=group.symbols,
            )
        )

    def is_subsumed_by_part_id(
        exact: ConnectorPeerPinAssignmentDivergence,
        aliases: tuple[ConnectorPeerPinAssignmentDivergence, ...],
    ) -> bool:
        exact_assignments = {pin.casefold(): nets for pin, nets in exact.assignments.items()}
        exact_missing_functions = {pin.casefold() for pin in exact.missing_function_pins}
        for alias in aliases:
            if exact.pin_number.casefold() != alias.pin_number.casefold():
                continue
            alias_assignments = {pin.casefold(): nets for pin, nets in alias.assignments.items()}
            alias_missing_functions = {pin.casefold() for pin in alias.missing_function_pins}
            if (
                exact_assignments.keys() <= alias_assignments.keys()
                and all(alias_assignments[pin] == nets for pin, nets in exact_assignments.items())
                and exact_missing_functions <= alias_missing_functions
            ):
                return True
        return False

    combined = [
        *part_id_results,
        *(
            item
            for item in exact_results
            if not is_subsumed_by_part_id(item, tuple(part_id_results))
        ),
    ]
    return tuple(
        sorted(
            combined,
            key=lambda item: (
                0 if item.peer_identity_basis == "part_id" else 1,
                item.peer_identity.casefold(),
                item.symbol.casefold(),
                item.pin_number.casefold(),
                tuple(pin.casefold() for pin in item.missing_function_pins),
            ),
        )
    )
