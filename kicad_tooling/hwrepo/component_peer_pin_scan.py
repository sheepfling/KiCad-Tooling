"""Source-bound scans for comparable component peer pins."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .connector_identity import (
    connector_candidate_references,
    is_named_supply_function,
    is_return_function,
)
from .models import NetlistContract


@dataclass(frozen=True)
class PeerPowerPinAssignmentDivergence:
    symbol: str
    pin_number: str
    function: str
    role: str
    assignments: dict[str, tuple[str, ...]]
    peer_identity_basis: Literal["exact_symbol", "part_id"] = "exact_symbol"
    peer_identity: str = ""
    peer_symbols: tuple[str, ...] = ()


@dataclass(frozen=True)
class PeerPinAssignmentOutlier:
    symbol: str
    pin_number: str
    electrical_type: str
    assignments: dict[str, tuple[str, ...]]
    pin_function: str | None = None
    peer_identity_basis: Literal["exact_symbol", "part_id"] = "exact_symbol"
    peer_identity: str = ""
    peer_symbols: tuple[str, ...] = ()


@dataclass(frozen=True)
class PeerPinAssignmentScan:
    exact_symbol_peer_group_count: int
    part_id_peer_group_count: int
    part_id_candidate_group_count: int
    part_id_incomplete_component_identity_group_count: int
    part_id_incomplete_component_identity_references: tuple[str, ...]
    incomplete_pin_inventory_group_count: int
    incomplete_pin_inventory_references: tuple[str, ...]
    complete_pin_inventory_group_count: int
    comparable_pin_group_count: int
    matching_electrical_type_pin_group_count: int
    compatible_function_pin_group_count: int
    ambiguous_assignment_pin_group_count: int
    unambiguous_assignment_pin_group_count: int
    deduplicated_candidate_group_count: int
    outliers: tuple[PeerPinAssignmentOutlier, ...]


@dataclass(frozen=True)
class ComponentPeerPinAssignmentScans:
    power_output: PeerPinAssignmentScan
    signal_output: PeerPinAssignmentScan
    signal_input: PeerPinAssignmentScan
    bidirectional: PeerPinAssignmentScan


def scan_component_peer_pin_assignments(
    observed: NetlistContract,
    declared_references: tuple[str, ...] = (),
    *,
    electrical_types: frozenset[str],
    require_pin_functions: bool = False,
) -> PeerPinAssignmentScan:
    """Scan assignment coverage among exact-symbol and exact-part peers.

    Same-symbol and same-PART_ID, same-pin assignments are review clues only.
    The other instances may intentionally use that pin differently or leave it
    open. Cross-symbol PART_ID groups require matching component value,
    footprint, complete pin inventories, native types, and present, identical
    per-pin function metadata. Identical generic placeholders are accepted as
    a structural match only; they do not identify the pin's electrical role.
    """
    accepted_types = {value.strip().casefold() for value in electrical_types}
    unpopulated = {reference.casefold() for reference in observed.dnp_components}
    connector_references = {
        reference.casefold()
        for reference in connector_candidate_references(observed, declared_references)
    }
    known_components = {reference.casefold() for reference in observed.components}
    references_by_symbol: dict[str, list[str]] = {}
    symbols_by_key: dict[str, str] = {}
    components_by_key = {
        reference.casefold(): component for reference, component in observed.components.items()
    }
    eligible_references: list[str] = []
    for reference, symbol in observed.component_symbols.items():
        reference_key = reference.casefold()
        if (
            reference_key not in known_components
            or reference_key in unpopulated
            or reference_key in connector_references
        ):
            continue
        eligible_references.append(reference)
        symbol_key = symbol.casefold()
        references_by_symbol.setdefault(symbol_key, []).append(reference)
        symbols_by_key[symbol_key] = symbol

    peer_groups: list[tuple[Literal["exact_symbol", "part_id"], str, tuple[str, ...]]] = []
    for symbol_key, references in sorted(references_by_symbol.items()):
        peers = tuple(sorted(references, key=str.casefold))
        if len(peers) >= 2:
            peer_groups.append(("exact_symbol", symbols_by_key[symbol_key], peers))

    references_by_part_id: dict[str, list[str]] = {}
    part_ids_by_key: dict[str, str] = {}
    for reference in eligible_references:
        component = components_by_key.get(reference.casefold())
        part_id = None if component is None else component.part_id
        if part_id is None or not part_id.strip():
            continue
        part_id = part_id.strip()
        part_key = part_id.casefold()
        references_by_part_id.setdefault(part_key, []).append(reference)
        previous = part_ids_by_key.get(part_key)
        if previous is None or (part_id.casefold(), part_id) < (
            previous.casefold(),
            previous,
        ):
            part_ids_by_key[part_key] = part_id
    part_id_candidate_group_count = 0
    part_id_incomplete_component_identity_group_count = 0
    part_id_incomplete_component_identity_references: set[str] = set()
    for part_key, references in sorted(references_by_part_id.items()):
        peers = tuple(sorted(references, key=str.casefold))
        peer_symbols = {observed.component_symbols[reference].casefold() for reference in peers}
        if len(peers) < 2 or len(peer_symbols) < 2:
            continue
        part_id_candidate_group_count += 1
        peer_components = tuple(components_by_key[reference.casefold()] for reference in peers)
        values = {component.value.strip().casefold() for component in peer_components}
        footprints = {component.footprint.strip().casefold() for component in peer_components}
        if len(values) != 1 or "" in values or len(footprints) != 1 or "" in footprints:
            part_id_incomplete_component_identity_group_count += 1
            part_id_incomplete_component_identity_references.update(peers)
            continue
        peer_groups.append(("part_id", part_ids_by_key[part_key], peers))

    inventories = {
        reference.casefold(): tuple(sorted(numbers, key=str.casefold))
        for reference, numbers in observed.component_pin_numbers.items()
    }
    pin_electrical_types = {
        pin.casefold(): electrical_type.strip().casefold()
        for pin, electrical_type in observed.pin_electrical_types.items()
    }
    functions = {pin.casefold(): function for pin, function in observed.pin_functions.items()}
    pin_nets: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin.casefold(), set()).add(net)

    results: list[PeerPinAssignmentOutlier] = []
    exact_symbol_peer_group_count = 0
    part_id_peer_group_count = 0
    incomplete_pin_inventory_group_count = 0
    incomplete_pin_inventory_references: set[str] = set()
    complete_pin_inventory_group_count = 0
    comparable_pin_group_count = 0
    matching_electrical_type_pin_group_count = 0
    compatible_function_pin_group_count = 0
    ambiguous_assignment_pin_group_count = 0
    unambiguous_assignment_pin_group_count = 0
    deduplicated_candidate_group_count = 0
    candidate_keys: set[tuple[str, tuple[str, ...]]] = set()
    peer_groups.sort(key=lambda item: (item[0], item[1].casefold(), item[1]))
    for peer_identity_basis, peer_identity, peers in peer_groups:
        if peer_identity_basis == "exact_symbol":
            exact_symbol_peer_group_count += 1
        else:
            part_id_peer_group_count += 1
        peer_inventories = tuple(inventories.get(reference.casefold(), ()) for reference in peers)
        if (
            not peer_inventories[0]
            or any(not numbers for numbers in peer_inventories)
            or any(
                {number.casefold() for number in numbers}
                != {number.casefold() for number in peer_inventories[0]}
                for numbers in peer_inventories[1:]
            )
            or len({number.casefold() for number in peer_inventories[0]})
            != len(peer_inventories[0])
        ):
            incomplete_pin_inventory_group_count += 1
            incomplete_pin_inventory_references.update(peers)
            continue
        complete_pin_inventory_group_count += 1

        for pin_number in peer_inventories[0]:
            comparable_pin_group_count += 1
            pins = tuple(f"{reference}.{pin_number}" for reference in peers)
            peer_types = tuple(pin_electrical_types.get(pin.casefold()) for pin in pins)
            if (
                any(electrical_type not in accepted_types for electrical_type in peer_types)
                or len(set(peer_types)) != 1
            ):
                continue
            matching_electrical_type_pin_group_count += 1
            peer_functions = tuple(functions.get(pin.casefold()) for pin in pins)
            if (
                (require_pin_functions or peer_identity_basis == "part_id")
                and any(function is None or not function.strip() for function in peer_functions)
            ) or len(
                {
                    function.casefold() if function is not None else None
                    for function in peer_functions
                }
            ) > 1:
                continue
            compatible_function_pin_group_count += 1
            assignments = {
                pin: tuple(sorted(pin_nets.get(pin.casefold(), ()), key=str.casefold))
                for pin in pins
            }
            if any(len(nets) > 1 for nets in assignments.values()):
                ambiguous_assignment_pin_group_count += 1
                continue
            unambiguous_assignment_pin_group_count += 1
            open_pins = tuple(pin for pin, nets in assignments.items() if not nets)
            assigned_pins = tuple(pin for pin, nets in assignments.items() if nets)
            if not open_pins or not assigned_pins:
                continue
            if any(
                function is not None
                and (is_named_supply_function(function) or is_return_function(function))
                for pin in open_pins
                for function in (functions.get(pin.casefold()),)
            ):
                # Preserve the more specific existing named supply/return prompt.
                continue
            candidate_key = (
                pin_number.casefold(),
                tuple(sorted(open_pins, key=lambda pin: (pin.casefold(), pin))),
            )
            if candidate_key in candidate_keys:
                deduplicated_candidate_group_count += 1
                continue
            candidate_keys.add(candidate_key)
            peer_symbols = tuple(
                sorted(
                    {observed.component_symbols[reference] for reference in peers},
                    key=lambda item: (item.casefold(), item),
                )
            )
            results.append(
                PeerPinAssignmentOutlier(
                    symbol=(
                        peer_identity if peer_identity_basis == "exact_symbol" else peer_symbols[0]
                    ),
                    pin_number=pin_number,
                    electrical_type=peer_types[0] or "",
                    assignments=dict(
                        sorted(assignments.items(), key=lambda item: item[0].casefold())
                    ),
                    pin_function=peer_functions[0],
                    peer_identity_basis=peer_identity_basis,
                    peer_identity=peer_identity,
                    peer_symbols=peer_symbols,
                )
            )
    outliers = tuple(
        sorted(
            results,
            key=lambda item: (
                item.peer_identity_basis,
                item.peer_identity.casefold(),
                item.pin_number.casefold(),
            ),
        )
    )
    return PeerPinAssignmentScan(
        exact_symbol_peer_group_count=exact_symbol_peer_group_count,
        part_id_peer_group_count=part_id_peer_group_count,
        part_id_candidate_group_count=part_id_candidate_group_count,
        part_id_incomplete_component_identity_group_count=(
            part_id_incomplete_component_identity_group_count
        ),
        part_id_incomplete_component_identity_references=tuple(
            sorted(part_id_incomplete_component_identity_references, key=str.casefold)
        ),
        incomplete_pin_inventory_group_count=incomplete_pin_inventory_group_count,
        incomplete_pin_inventory_references=tuple(
            sorted(incomplete_pin_inventory_references, key=str.casefold)
        ),
        complete_pin_inventory_group_count=complete_pin_inventory_group_count,
        comparable_pin_group_count=comparable_pin_group_count,
        matching_electrical_type_pin_group_count=matching_electrical_type_pin_group_count,
        compatible_function_pin_group_count=compatible_function_pin_group_count,
        ambiguous_assignment_pin_group_count=ambiguous_assignment_pin_group_count,
        unambiguous_assignment_pin_group_count=unambiguous_assignment_pin_group_count,
        deduplicated_candidate_group_count=deduplicated_candidate_group_count,
        outliers=outliers,
    )


def component_peer_pin_assignment_scans(
    observed: NetlistContract,
    declared_references: tuple[str, ...] = (),
) -> ComponentPeerPinAssignmentScans:
    """Return bounded applicability scans for all native peer-pin checks."""
    return ComponentPeerPinAssignmentScans(
        power_output=scan_component_peer_pin_assignments(
            observed,
            declared_references,
            electrical_types=frozenset({"power_out"}),
        ),
        signal_output=scan_component_peer_pin_assignments(
            observed,
            declared_references,
            electrical_types=frozenset({"output"}),
        ),
        signal_input=scan_component_peer_pin_assignments(
            observed,
            declared_references,
            electrical_types=frozenset({"input", "input_low"}),
            require_pin_functions=True,
        ),
        bidirectional=scan_component_peer_pin_assignments(
            observed,
            declared_references,
            electrical_types=frozenset({"bidirectional"}),
            require_pin_functions=True,
        ),
    )
