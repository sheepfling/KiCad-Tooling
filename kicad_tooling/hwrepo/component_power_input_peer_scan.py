"""Source-bound peer scans for component power-input pins."""

from __future__ import annotations

from collections.abc import Mapping

from .component_peer_pin_scan import (
    PeerPinAssignmentOutlier,
    PeerPinAssignmentScan,
    scan_component_peer_pin_assignments,
)
from .connector_identity import (
    connector_candidate_references,
    is_named_supply_function,
    is_return_function,
    pin_function_is_generic,
)
from .models import NetlistContract


def scan_component_peer_power_input_assignments(
    observed: NetlistContract,
    declared_connector_references: tuple[str, ...] = (),
) -> PeerPinAssignmentScan:
    """Compare exact-symbol peers and retain why power-input groups were skipped.

    The scan reports candidate groups only when every fitted peer has a complete
    identical pin inventory, a matching generic function, native ``power_in``
    type, and one assigned net. Its remaining counts distinguish missing peer
    metadata and open pins from a completed common-net comparison.
    """
    connector_references = {
        reference.casefold()
        for reference in connector_candidate_references(observed, declared_connector_references)
    }
    dnp_references = {reference.casefold() for reference in observed.dnp_components}
    known_components = {reference.casefold() for reference in observed.components}
    symbols_by_reference: dict[str, str] = {}
    references_by_symbol: dict[str, list[str]] = {}
    for reference, symbol in observed.component_symbols.items():
        reference_key = reference.casefold()
        if (
            reference_key not in known_components
            or reference_key in dnp_references
            or reference_key in connector_references
            or not symbol.strip()
        ):
            continue
        symbol_key = symbol.casefold()
        symbols_by_reference[reference_key] = symbol
        references_by_symbol.setdefault(symbol_key, []).append(reference)

    peer_groups = tuple(
        (symbol_key, tuple(sorted(references, key=lambda item: (item.casefold(), item))))
        for symbol_key, references in sorted(references_by_symbol.items())
        if len(references) >= 2
    )
    inventories: Mapping[str, tuple[str, ...]] = {
        reference.casefold(): tuple(pin_numbers)
        for reference, pin_numbers in observed.component_pin_numbers.items()
    }
    functions = {pin.casefold(): function for pin, function in observed.pin_functions.items()}
    electrical_types = {
        pin.casefold(): electrical_type.strip().casefold()
        for pin, electrical_type in observed.pin_electrical_types.items()
    }
    pin_nets: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin.casefold(), set()).add(net)

    incomplete_inventory_group_count = 0
    incomplete_inventory_references: set[str] = set()
    complete_inventory_group_count = 0
    comparable_pin_group_count = 0
    matching_type_group_count = 0
    compatible_function_group_count = 0
    ambiguous_assignment_group_count = 0
    unambiguous_assignment_group_count = 0
    open_assignment_group_count = 0
    divergences: list[PeerPinAssignmentOutlier] = []

    for _, peers in peer_groups:
        representative_symbol = symbols_by_reference[peers[0].casefold()]
        peer_inventories = tuple(inventories.get(reference.casefold(), ()) for reference in peers)
        normalized_inventories = tuple(
            tuple(number.casefold() for number in inventory) for inventory in peer_inventories
        )
        if (
            any(not inventory for inventory in peer_inventories)
            or any(len(set(inventory)) != len(inventory) for inventory in normalized_inventories)
            or any(
                inventory != normalized_inventories[0] for inventory in normalized_inventories[1:]
            )
        ):
            incomplete_inventory_group_count += 1
            incomplete_inventory_references.update(peers)
            continue
        complete_inventory_group_count += 1

        for pin_number in sorted(peer_inventories[0], key=lambda item: (item.casefold(), item)):
            comparable_pin_group_count += 1
            pins = tuple(f"{reference}.{pin_number}" for reference in peers)
            pin_keys = tuple(pin.casefold() for pin in pins)
            if any(electrical_types.get(pin) != "power_in" for pin in pin_keys):
                continue
            matching_type_group_count += 1
            peer_functions = tuple(functions.get(pin) for pin in pin_keys)
            if (
                any(not pin_function_is_generic(function) for function in peer_functions)
                or len({(function or "").strip().casefold() for function in peer_functions}) != 1
            ):
                continue
            compatible_function_group_count += 1
            assignments = {
                pin: tuple(
                    sorted(
                        pin_nets.get(pin.casefold(), ()), key=lambda item: (item.casefold(), item)
                    )
                )
                for pin in pins
            }
            if any(len(nets) > 1 for nets in assignments.values()):
                ambiguous_assignment_group_count += 1
                continue
            unambiguous_assignment_group_count += 1
            if any(not nets for nets in assignments.values()):
                open_assignment_group_count += 1
                continue
            if len(set(assignments.values())) < 2:
                continue
            divergences.append(
                PeerPinAssignmentOutlier(
                    symbol=representative_symbol,
                    pin_number=pin_number,
                    electrical_type="power_in",
                    assignments=dict(
                        sorted(assignments.items(), key=lambda item: (item[0].casefold(), item[0]))
                    ),
                    pin_function=peer_functions[0],
                    peer_identity_basis="exact_symbol",
                    peer_identity=representative_symbol,
                    peer_symbols=(representative_symbol,),
                )
            )

    return PeerPinAssignmentScan(
        exact_symbol_peer_group_count=len(peer_groups),
        part_id_peer_group_count=0,
        part_id_candidate_group_count=0,
        part_id_incomplete_component_identity_group_count=0,
        part_id_incomplete_component_identity_references=(),
        incomplete_pin_inventory_group_count=incomplete_inventory_group_count,
        incomplete_pin_inventory_references=tuple(
            sorted(incomplete_inventory_references, key=lambda item: (item.casefold(), item))
        ),
        complete_pin_inventory_group_count=complete_inventory_group_count,
        comparable_pin_group_count=comparable_pin_group_count,
        matching_electrical_type_pin_group_count=matching_type_group_count,
        compatible_function_pin_group_count=compatible_function_group_count,
        ambiguous_assignment_pin_group_count=ambiguous_assignment_group_count,
        unambiguous_assignment_pin_group_count=unambiguous_assignment_group_count,
        open_assignment_pin_group_count=open_assignment_group_count,
        deduplicated_candidate_group_count=0,
        outliers=tuple(
            sorted(
                divergences,
                key=lambda item: (item.symbol.casefold(), item.pin_number.casefold()),
            )
        ),
    )


def _unrecognized_non_generic_power_input_function(
    functions: tuple[str | None, ...],
) -> bool:
    """Select matching native functions not covered by generic or named-pin checks."""
    if not functions or functions[0] is None:
        return False
    function = functions[0]
    return not (
        pin_function_is_generic(function)
        or is_named_supply_function(function)
        or is_return_function(function)
    )


def scan_component_peer_power_input_open_assignments(
    observed: NetlistContract,
    declared_references: tuple[str, ...] = (),
) -> PeerPinAssignmentScan:
    """Find named native power-input pins open on only some comparable peers.

    Generic pin functions and recognized supply/return names remain with their
    existing unconnected-pin rules. This scan asks for review when an otherwise
    unrecognized, matching ``power_in`` function is assigned on at least one
    peer and open on another.
    """
    return scan_component_peer_pin_assignments(
        observed,
        declared_references,
        electrical_types=frozenset({"power_in"}),
        require_pin_functions=True,
        pin_function_selector=_unrecognized_non_generic_power_input_function,
        assignment_pattern="partial_open",
        minimum_peer_count=2,
    )


def scan_component_peer_named_power_input_assignment_divergences(
    observed: NetlistContract,
    declared_references: tuple[str, ...] = (),
) -> PeerPinAssignmentScan:
    """Compare assignments for matching named power-input peer pins.

    Generic functions and recognized supply/return names remain with their
    more specific checks. A differing assignment is a review candidate only;
    the peer identity and named function do not prove that the nets must match.
    """
    return scan_component_peer_pin_assignments(
        observed,
        declared_references,
        electrical_types=frozenset({"power_in"}),
        require_pin_functions=True,
        pin_function_selector=_unrecognized_non_generic_power_input_function,
        assignment_pattern="different_assigned_nets",
        minimum_peer_count=2,
    )


def scan_component_peer_named_power_input_all_open(
    observed: NetlistContract,
    declared_references: tuple[str, ...] = (),
) -> PeerPinAssignmentScan:
    """Find named native power-input pins left open on every comparable peer.

    The all-open state is a review prompt because matching peer identity,
    explicit pin function, and native ``power_in`` type do not prove that a
    pin is required or intended to be connected.
    """
    return scan_component_peer_pin_assignments(
        observed,
        declared_references,
        electrical_types=frozenset({"power_in"}),
        require_pin_functions=True,
        pin_function_selector=_unrecognized_non_generic_power_input_function,
        assignment_pattern="all_open",
        minimum_peer_count=2,
    )
