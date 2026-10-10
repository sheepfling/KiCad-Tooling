"""Review findings for component peer-pin assignment differences."""

from __future__ import annotations

from typing import Literal

from .component_peer_pin_scan import (
    PeerPinAssignmentOutlier,
    PeerPowerPinAssignmentDivergence,
    scan_component_peer_pin_assignments,
)
from .connector_identity import (
    connector_candidate_references,
    is_return_function,
    power_function_key,
)
from .models import NetlistContract


def _component_peer_pin_assignment_outliers(
    observed: NetlistContract,
    declared_references: tuple[str, ...] = (),
    *,
    electrical_types: frozenset[str],
    require_pin_functions: bool = False,
) -> tuple[PeerPinAssignmentOutlier, ...]:
    """Return only findings from the shared source-bound peer-pin scan."""
    return scan_component_peer_pin_assignments(
        observed,
        declared_references,
        electrical_types=electrical_types,
        require_pin_functions=require_pin_functions,
    ).outliers


def component_peer_power_output_pin_outliers(
    observed: NetlistContract,
    declared_references: tuple[str, ...] = (),
) -> tuple[PeerPinAssignmentOutlier, ...]:
    """Find an open native power-output pin among exact-symbol fitted peers."""
    return _component_peer_pin_assignment_outliers(
        observed,
        declared_references,
        electrical_types=frozenset({"power_out"}),
    )


def component_peer_signal_output_pin_outliers(
    observed: NetlistContract,
    declared_references: tuple[str, ...] = (),
) -> tuple[PeerPinAssignmentOutlier, ...]:
    """Find an open native signal-output pin among exact-symbol fitted peers."""
    return _component_peer_pin_assignment_outliers(
        observed,
        declared_references,
        electrical_types=frozenset({"output"}),
    )


def component_peer_signal_input_pin_outliers(
    observed: NetlistContract,
    declared_references: tuple[str, ...] = (),
) -> tuple[PeerPinAssignmentOutlier, ...]:
    """Find an open native signal-input pin among exact-symbol fitted peers."""
    return _component_peer_pin_assignment_outliers(
        observed,
        declared_references,
        electrical_types=frozenset({"input", "input_low"}),
        require_pin_functions=True,
    )


def component_peer_bidirectional_pin_outliers(
    observed: NetlistContract,
    declared_references: tuple[str, ...] = (),
) -> tuple[PeerPinAssignmentOutlier, ...]:
    """Find an open native bidirectional pin among exact-symbol fitted peers."""
    return _component_peer_pin_assignment_outliers(
        observed,
        declared_references,
        electrical_types=frozenset({"bidirectional"}),
        require_pin_functions=True,
    )


def component_peer_power_pin_assignment_divergences(
    observed: NetlistContract,
    declared_references: tuple[str, ...] = (),
) -> tuple[PeerPowerPinAssignmentDivergence, ...]:
    """Find split recognized power pins across comparable fitted peers.

    Exact symbol peers use the legacy pin-number and recognized-function
    comparison. Cross-symbol peers require a shared PART_ID, matching value and
    footprint, complete identical pin inventories, and identical native pin
    function and electrical-type metadata for every pin. Neither identity basis
    establishes that the peers must use a common electrical domain.
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

    functions_by_pin: dict[str, str] = {
        pin.casefold(): function for pin, function in observed.pin_functions.items()
    }
    pin_numbers_by_reference: dict[str, set[str]] = {
        reference.casefold(): set(pin_numbers)
        for reference, pin_numbers in observed.component_pin_numbers.items()
    }
    for pin in observed.pin_functions:
        if "." not in pin:
            continue
        reference, pin_number = pin.rsplit(".", 1)
        pin_numbers_by_reference.setdefault(reference.casefold(), set()).add(pin_number)

    exact_symbol_groups: list[tuple[str, tuple[str, ...]]] = []
    references_by_symbol: dict[str, list[str]] = {}
    symbol_names: dict[str, str] = {}
    known_components = {reference.casefold() for reference in observed.components}
    for reference, symbol in observed.component_symbols.items():
        if (
            reference.casefold() not in known_components
            or reference.casefold() in unpopulated
            or reference.casefold() in connector_references
        ):
            continue
        references_by_symbol.setdefault(symbol.casefold(), []).append(reference)
        symbol_names[symbol.casefold()] = symbol

    for symbol_key, references in sorted(references_by_symbol.items()):
        peers = tuple(sorted(references, key=lambda item: (item.casefold(), item)))
        if len(peers) >= 2:
            exact_symbol_groups.append((symbol_names[symbol_key], peers))

    components_by_reference = {
        reference.casefold(): component for reference, component in observed.components.items()
    }
    references_by_part_id: dict[str, list[str]] = {}
    part_ids_by_key: dict[str, list[str]] = {}
    for references in references_by_symbol.values():
        for reference in references:
            component = components_by_reference.get(reference.casefold())
            part_id = None if component is None else component.part_id
            if part_id is None or not part_id.strip():
                continue
            normalized_part_id = part_id.strip()
            part_key = normalized_part_id.casefold()
            references_by_part_id.setdefault(part_key, []).append(reference)
            part_ids_by_key.setdefault(part_key, []).append(normalized_part_id)

    pin_types_by_pin = {
        pin.casefold(): electrical_type.strip().casefold()
        for pin, electrical_type in observed.pin_electrical_types.items()
    }
    normalized_functions_by_pin = {
        pin.casefold(): function.strip().casefold()
        for pin, function in observed.pin_functions.items()
    }
    inventories_by_reference = {
        reference.casefold(): tuple(numbers)
        for reference, numbers in observed.component_pin_numbers.items()
    }
    part_id_groups: list[tuple[str, tuple[str, ...], tuple[str, ...]]] = []
    for part_key, references in sorted(references_by_part_id.items()):
        peers = tuple(sorted(set(references), key=lambda item: (item.casefold(), item)))
        peer_symbols = tuple(
            sorted(
                {observed.component_symbols[reference] for reference in peers},
                key=lambda item: (item.casefold(), item),
            )
        )
        if len(peers) < 2 or len({symbol.casefold() for symbol in peer_symbols}) < 2:
            continue
        peer_components = tuple(
            components_by_reference[reference.casefold()] for reference in peers
        )
        values = {component.value.strip().casefold() for component in peer_components}
        footprints = {component.footprint.strip().casefold() for component in peer_components}
        if len(values) != 1 or "" in values or len(footprints) != 1 or "" in footprints:
            continue

        inventories = tuple(
            inventories_by_reference.get(reference.casefold(), ()) for reference in peers
        )
        if (
            not inventories[0]
            or any(not inventory for inventory in inventories)
            or any(
                {number.casefold() for number in inventory}
                != {number.casefold() for number in inventories[0]}
                for inventory in inventories[1:]
            )
            or len({number.casefold() for number in inventories[0]}) != len(inventories[0])
        ):
            continue
        pin_numbers = tuple(sorted(inventories[0], key=lambda item: (item.casefold(), item)))
        complete_metadata = True
        for pin_number in pin_numbers:
            pins = tuple(f"{reference}.{pin_number}".casefold() for reference in peers)
            peer_functions = tuple(normalized_functions_by_pin.get(pin) for pin in pins)
            peer_types = tuple(pin_types_by_pin.get(pin) for pin in pins)
            if (
                any(function is None or not function for function in peer_functions)
                or len(set(peer_functions)) != 1
                or any(
                    electrical_type is None or not electrical_type for electrical_type in peer_types
                )
                or len(set(peer_types)) != 1
            ):
                complete_metadata = False
                break
        if not complete_metadata:
            continue
        representative_part_id = min(
            part_ids_by_key[part_key], key=lambda item: (item.casefold(), item)
        )
        part_id_groups.append((representative_part_id, peers, peer_symbols))

    # A valid PART_ID group contains the same identity proof plus every matching
    # symbol alias, so avoid emitting subset findings for its exact-symbol peers.
    covered_exact_groups = tuple(set(peers) for _, peers, _ in part_id_groups)
    comparable_groups: list[
        tuple[Literal["exact_symbol", "part_id"], str, tuple[str, ...], tuple[str, ...]]
    ] = [("part_id", part_id, peers, symbols) for part_id, peers, symbols in part_id_groups]
    comparable_groups.extend(
        ("exact_symbol", symbol, peers, (symbol,))
        for symbol, peers in exact_symbol_groups
        if not any(set(peers) <= covered for covered in covered_exact_groups)
    )

    results: list[PeerPowerPinAssignmentDivergence] = []
    for identity_basis, identity, peer_references, peer_symbols in comparable_groups:
        if identity_basis == "part_id":
            shared_pin_numbers = set(inventories_by_reference[peer_references[0].casefold()])
        else:
            shared_pin_numbers = set(
                pin_numbers_by_reference.get(peer_references[0].casefold(), set())
            )
            for reference in peer_references[1:]:
                shared_pin_numbers.intersection_update(
                    pin_numbers_by_reference.get(reference.casefold(), set())
                )
        for pin_number in sorted(shared_pin_numbers, key=lambda item: (item.casefold(), item)):
            pins = tuple(f"{reference}.{pin_number}" for reference in peer_references)
            functions: tuple[str | None, ...] = tuple(
                functions_by_pin.get(pin.casefold()) for pin in pins
            )
            if any(function is None for function in functions):
                continue
            typed_functions: tuple[str, ...] = tuple(
                function for function in functions if function is not None
            )
            if all(is_return_function(function) for function in typed_functions):
                role = "ground/return"
            else:
                supply_keys: tuple[str | None, ...] = tuple(
                    power_function_key(function) for function in typed_functions
                )
                if any(key is None for key in supply_keys) or len(set(supply_keys)) != 1:
                    continue
                role = "supply"
            assignments: dict[str, tuple[str, ...]] = {
                pin: tuple(sorted(pin_nets.get(pin.casefold(), ()))) for pin in pins
            }
            if any(len(nets) != 1 for nets in assignments.values()):
                continue
            if len(set(assignments.values())) < 2:
                continue
            results.append(
                PeerPowerPinAssignmentDivergence(
                    symbol=peer_symbols[0],
                    pin_number=pin_number,
                    function=typed_functions[0],
                    role=role,
                    assignments=dict(
                        sorted(assignments.items(), key=lambda item: item[0].casefold())
                    ),
                    peer_identity_basis=identity_basis,
                    peer_identity=identity,
                    peer_symbols=peer_symbols,
                )
            )
    return tuple(
        sorted(
            results,
            key=lambda item: (
                item.peer_identity_basis,
                item.peer_identity.casefold(),
                item.pin_number.casefold(),
                item.role,
            ),
        )
    )
