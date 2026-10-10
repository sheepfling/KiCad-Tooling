"""Unconnected and repeated component pin checks."""

from __future__ import annotations

from dataclasses import dataclass

from .connector_identity import (
    connector_candidate_references,
    is_named_supply_function,
    is_return_function,
    pin_function_is_generic,
    power_function_key,
)
from .models import NetlistContract


@dataclass(frozen=True)
class UnconnectedGenericPowerInputComponentPin:
    pin: str
    symbol: str
    function: str | None
    electrical_type: str


def unconnected_generic_power_input_component_pins(
    observed: NetlistContract,
    declared_connector_references: tuple[str, ...] = (),
) -> tuple[UnconnectedGenericPowerInputComponentPin, ...]:
    """Find unassigned generic ``power_in`` pins on fitted non-connectors."""
    connector_references = {
        reference.casefold()
        for reference in connector_candidate_references(observed, declared_connector_references)
    }
    symbols = {
        reference.casefold(): symbol for reference, symbol in observed.component_symbols.items()
    }
    component_references = {reference.casefold() for reference in observed.components}
    unpopulated = {reference.casefold() for reference in observed.dnp_components}
    connected = {pin.casefold() for pins in observed.nets.values() for pin in pins}
    functions = {pin.casefold(): function for pin, function in observed.pin_functions.items()}
    results: list[UnconnectedGenericPowerInputComponentPin] = []
    for pin, electrical_type in observed.pin_electrical_types.items():
        pin_key = pin.casefold()
        reference = pin.rsplit(".", 1)[0]
        reference_key = reference.casefold()
        symbol = symbols.get(reference_key)
        if (
            "." not in pin
            or electrical_type.strip().casefold() != "power_in"
            or reference_key not in component_references
            or reference_key in connector_references
            or reference_key in unpopulated
            or pin_key in connected
            or not pin_function_is_generic(functions.get(pin_key))
            or symbol is None
        ):
            continue
        results.append(
            UnconnectedGenericPowerInputComponentPin(
                pin=pin,
                symbol=symbol,
                function=functions.get(pin_key),
                electrical_type="power_in",
            )
        )
    return tuple(sorted(results, key=lambda item: (item.pin.casefold(), item.pin)))


@dataclass(frozen=True)
class UnconnectedNamedComponentPin:
    pin: str
    function: str
    category: str


def unconnected_named_component_pins(
    observed: NetlistContract,
    declared_references: tuple[str, ...] = (),
) -> tuple[UnconnectedNamedComponentPin, ...]:
    """Find named supply/return pins on non-connector parts with no net."""
    connected = {pin for pins in observed.nets.values() for pin in pins}
    connector_references = {
        reference.casefold()
        for reference in connector_candidate_references(observed, declared_references)
    }
    results: list[UnconnectedNamedComponentPin] = []
    for pin, function in observed.pin_functions.items():
        reference = pin.rsplit(".", 1)[0]
        if (
            reference not in observed.components
            or reference.casefold() in connector_references
            or pin in connected
        ):
            continue
        category = "return" if is_return_function(function) else None
        if category is None and is_named_supply_function(function):
            category = "supply"
        if category is not None:
            results.append(
                UnconnectedNamedComponentPin(
                    pin=pin,
                    function=function,
                    category=category,
                )
            )
    return tuple(sorted(results, key=lambda item: (item.category, item.pin, item.function)))


@dataclass(frozen=True)
class RepeatedComponentSupplyPins:
    reference: str
    symbol: str
    function: str
    pins: dict[str, tuple[str, ...]]


def component_supply_pins_on_different_nets(
    observed: NetlistContract,
    declared_references: tuple[str, ...] = (),
) -> tuple[RepeatedComponentSupplyPins, ...]:
    """Find same-component supply pins with matching roles but distinct nets."""
    pin_nets: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin, set()).add(net)

    unpopulated = {reference.casefold() for reference in observed.dnp_components}
    connector_references = {
        reference.casefold()
        for reference in connector_candidate_references(observed, declared_references)
    }
    grouped: dict[tuple[str, str], list[tuple[str, str, str, tuple[str, ...]]]] = {}
    for pin, function in observed.pin_functions.items():
        if "." not in pin:
            continue
        reference = pin.rsplit(".", 1)[0]
        symbol = observed.component_symbols.get(reference)
        if (
            symbol is None
            or reference not in observed.components
            or reference.casefold() in unpopulated
            or reference.casefold() in connector_references
        ):
            continue
        supply_key = power_function_key(function)
        if supply_key is None:
            continue
        grouped.setdefault((reference.casefold(), supply_key), []).append(
            (pin, reference, function, tuple(sorted(pin_nets.get(pin, ()))))
        )

    results: list[RepeatedComponentSupplyPins] = []
    for entries in grouped.values():
        # Open pins have a more specific existing finding. Keep this rule for
        # assigned-but-disagreeing rails, where native ERC may have no conflict.
        if len(entries) < 2 or any(not nets for _, _, _, nets in entries):
            continue
        if len({nets for _, _, _, nets in entries}) == 1 and all(
            len(nets) == 1 for _, _, _, nets in entries
        ):
            continue
        entries.sort()
        _, reference, function, _ = entries[0]
        symbol = observed.component_symbols[reference]
        results.append(
            RepeatedComponentSupplyPins(
                reference=reference,
                symbol=symbol,
                function=function,
                pins={pin: nets for pin, _, _, nets in entries},
            )
        )
    return tuple(sorted(results, key=lambda item: (item.reference, item.function)))
