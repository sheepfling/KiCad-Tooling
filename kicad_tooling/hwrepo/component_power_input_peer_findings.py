"""Peer comparison for generic component power-input assignments."""

from __future__ import annotations

from dataclasses import dataclass

from .connector_identity import connector_candidate_references, pin_function_is_generic
from .models import NetlistContract


@dataclass(frozen=True)
class ComponentPeerPowerInputAssignmentDivergence:
    """One exact-symbol generic power-input pin assigned to distinct nets."""

    symbol: str
    pin_number: str
    functions: dict[str, str]
    assignments: dict[str, tuple[str, ...]]


def component_peer_power_input_assignment_divergences(
    observed: NetlistContract,
    declared_connector_references: tuple[str, ...] = (),
) -> tuple[ComponentPeerPowerInputAssignmentDivergence, ...]:
    """Find exact-symbol peers whose generic native power-input pins split nets.

    This is a review candidate only. It requires a complete, matching native pin
    inventory and complete generic-function/power_in evidence for each peer.
    Named power and return functions remain with the existing role-aware rule.
    """
    connectors = {
        reference.casefold()
        for reference in connector_candidate_references(observed, declared_connector_references)
    }
    dnp = {reference.casefold() for reference in observed.dnp_components}
    components = {reference.casefold() for reference in observed.components}
    component_symbols = {
        reference.casefold(): (reference, symbol)
        for reference, symbol in observed.component_symbols.items()
    }
    inventories = {
        reference.casefold(): tuple(numbers)
        for reference, numbers in observed.component_pin_numbers.items()
    }
    functions = {pin.casefold(): name for pin, name in observed.pin_functions.items()}
    electrical_types = {
        pin.casefold(): electrical_type.strip().casefold()
        for pin, electrical_type in observed.pin_electrical_types.items()
    }
    pin_nets: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin.casefold(), set()).add(net)

    peers_by_symbol: dict[str, list[tuple[str, str]]] = {}
    for reference_key, (reference, symbol) in component_symbols.items():
        if (
            reference_key not in components
            or reference_key in dnp
            or reference_key in connectors
            or not symbol.strip()
        ):
            continue
        peers_by_symbol.setdefault(symbol.casefold(), []).append((reference, symbol))

    findings: list[ComponentPeerPowerInputAssignmentDivergence] = []
    for peers in peers_by_symbol.values():
        peers.sort(key=lambda item: (item[0].casefold(), item[0]))
        if len(peers) < 2:
            continue
        peer_keys = tuple(reference.casefold() for reference, _ in peers)
        peer_inventories = tuple(inventories.get(reference, ()) for reference in peer_keys)
        if (
            any(not inventory for inventory in peer_inventories)
            or any(
                {number.casefold() for number in inventory}
                != {number.casefold() for number in peer_inventories[0]}
                for inventory in peer_inventories[1:]
            )
            or any(
                len({number.casefold() for number in inventory}) != len(inventory)
                for inventory in peer_inventories
            )
        ):
            continue

        symbol = peers[0][1]
        for pin_number in sorted(peer_inventories[0], key=lambda item: (item.casefold(), item)):
            pins = tuple(f"{reference}.{pin_number}" for reference, _ in peers)
            pin_keys = tuple(pin.casefold() for pin in pins)
            if any(electrical_types.get(pin) != "power_in" for pin in pin_keys):
                continue
            pin_functions = tuple(functions.get(pin) for pin in pin_keys)
            if (
                any(not pin_function_is_generic(function) for function in pin_functions)
                or len({(function or "").strip().casefold() for function in pin_functions}) != 1
            ):
                continue

            assignments = {pin: tuple(sorted(pin_nets.get(pin.casefold(), ()))) for pin in pins}
            if any(len(nets) != 1 for nets in assignments.values()):
                continue
            if len(set(assignments.values())) < 2:
                continue
            findings.append(
                ComponentPeerPowerInputAssignmentDivergence(
                    symbol=symbol,
                    pin_number=pin_number,
                    functions={
                        pin: function or ""
                        for pin, function in zip(pins, pin_functions, strict=True)
                    },
                    assignments=dict(
                        sorted(assignments.items(), key=lambda item: (item[0].casefold(), item[0]))
                    ),
                )
            )

    return tuple(
        sorted(
            findings,
            key=lambda item: (
                item.symbol.casefold(),
                item.pin_number.casefold(),
                tuple(item.assignments),
            ),
        )
    )
