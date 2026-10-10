"""Connector pin return and unconnected-contact checks."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from .connector_identity import (
    connector_candidate_references,
    is_named_supply_function,
    is_return_function,
    is_shield_function,
    pin_function_is_generic,
)
from .models import ConnectorMappedPinEvidence, NetlistContract


@dataclass(frozen=True)
class ConnectorReturnCoverage:
    reference: str
    symbol: str
    connected_pin_count: int
    pins: dict[str, tuple[str, ...]]


@dataclass(frozen=True)
class UnconnectedNamedConnectorPin:
    pin: str
    function: str
    category: str
    role_source: str = "native_symbol"


@dataclass(frozen=True)
class UnconnectedGenericPowerInputConnectorPin:
    pin: str
    symbol: str
    function: str | None
    electrical_type: str


def unconnected_named_connector_pins(
    observed: NetlistContract,
    declared_references: tuple[str, ...] = (),
    reviewed_connector_pins: Mapping[str, ConnectorMappedPinEvidence] | None = None,
) -> tuple[UnconnectedNamedConnectorPin, ...]:
    """Find unassigned native or project-mapped connector supply/return pins."""
    reviewed_connector_pins = reviewed_connector_pins or {}
    unpopulated = {reference.casefold() for reference in observed.dnp_components}
    connector_references = {
        reference.casefold()
        for reference in connector_candidate_references(observed, declared_references)
    }
    connected = {pin for pins in observed.nets.values() for pin in pins}
    results: list[UnconnectedNamedConnectorPin] = []
    for pin in sorted(set(observed.pin_functions) | set(reviewed_connector_pins)):
        function = observed.pin_functions.get(pin, "")
        reference = pin.rsplit(".", 1)[0]
        if (
            reference.casefold() not in connector_references
            or reference not in observed.component_symbols
            or reference.casefold() in unpopulated
            or pin in connected
        ):
            continue
        category = "return" if is_return_function(function) else None
        if category is None and is_named_supply_function(function):
            category = "supply"
        role_source = "native_symbol"
        mapped = reviewed_connector_pins.get(pin)
        if (
            category is None
            and mapped is not None
            and mapped.role in {"return", "supply"}
            and pin_function_is_generic(function)
        ):
            category = mapped.role
            function = mapped.interface_signal
            role_source = "project_interface"
        if category is not None:
            results.append(
                UnconnectedNamedConnectorPin(
                    pin=pin,
                    function=function,
                    category=category,
                    role_source=role_source,
                )
            )
    return tuple(sorted(results, key=lambda item: (item.category, item.pin, item.function)))


def unconnected_generic_power_input_connector_pins(
    observed: NetlistContract,
    declared_references: tuple[str, ...] = (),
    *,
    excluded_pins: frozenset[str] = frozenset(),
) -> tuple[UnconnectedGenericPowerInputConnectorPin, ...]:
    """Find unassigned generic connector pins with the native ``power_in`` type."""
    connector_references = {
        reference.casefold()
        for reference in connector_candidate_references(observed, declared_references)
    }
    symbols_by_reference = {
        reference.casefold(): (reference, symbol)
        for reference, symbol in observed.component_symbols.items()
    }
    dnp = {reference.casefold() for reference in observed.dnp_components}
    connected = {pin.casefold() for pins in observed.nets.values() for pin in pins}
    pin_functions = {pin.casefold(): function for pin, function in observed.pin_functions.items()}
    excluded = {pin.casefold() for pin in excluded_pins}
    results: list[UnconnectedGenericPowerInputConnectorPin] = []
    for pin, electrical_type in observed.pin_electrical_types.items():
        pin_key = pin.casefold()
        reference = pin.rsplit(".", 1)[0]
        reference_key = reference.casefold()
        function = pin_functions.get(pin_key)
        symbol = symbols_by_reference.get(reference_key)
        if (
            electrical_type.strip().casefold() != "power_in"
            or reference_key not in connector_references
            or reference_key in dnp
            or pin_key in connected
            or pin_key in excluded
            or not pin_function_is_generic(function)
            or symbol is None
        ):
            continue
        results.append(
            UnconnectedGenericPowerInputConnectorPin(
                pin=pin,
                symbol=symbol[1],
                function=function,
                electrical_type="power_in",
            )
        )
    return tuple(sorted(results, key=lambda item: (item.pin.casefold(), item.pin)))


def connectors_without_connected_return(
    observed: NetlistContract,
    declared_references: tuple[str, ...] = (),
    reviewed_connector_pins: Mapping[str, ConnectorMappedPinEvidence] | None = None,
) -> tuple[ConnectorReturnCoverage, ...]:
    """Flag multi-conductor connectors with no connected native or mapped return."""
    reviewed_connector_pins = reviewed_connector_pins or {}
    unpopulated = {reference.casefold() for reference in observed.dnp_components}
    connector_references = {
        reference.casefold()
        for reference in connector_candidate_references(observed, declared_references)
    }
    symbols_by_reference = {
        reference.casefold(): (reference, symbol)
        for reference, symbol in observed.component_symbols.items()
    }
    connected_signal_pins: dict[str, set[str]] = {}
    connected_returns: dict[str, set[str]] = {}
    all_return_pins: dict[str, set[str]] = {}
    pin_nets: dict[str, set[str]] = {}

    for pin in sorted(set(observed.pin_functions) | set(reviewed_connector_pins)):
        function = observed.pin_functions.get(pin, "")
        reference = pin.rsplit(".", 1)[0]
        if reference.casefold() not in connector_references or reference.casefold() in unpopulated:
            continue
        if reference.casefold() not in symbols_by_reference:
            continue
        mapped = reviewed_connector_pins.get(pin)
        if is_return_function(function) or (
            mapped is not None and mapped.role == "return" and pin_function_is_generic(function)
        ):
            all_return_pins.setdefault(reference, set()).add(pin)

    for net, pins in observed.nets.items():
        for pin in pins:
            reference = pin.rsplit(".", 1)[0]
            if (
                reference.casefold() not in connector_references
                or reference.casefold() in unpopulated
            ):
                continue
            if reference.casefold() not in symbols_by_reference:
                continue
            pin_nets.setdefault(pin, set()).add(net)
            function = observed.pin_functions.get(pin, "")
            mapped = reviewed_connector_pins.get(pin)
            if function and is_shield_function(function):
                continue
            connected_signal_pins.setdefault(reference, set()).add(pin)
            if is_return_function(function) or (
                mapped is not None and mapped.role == "return" and pin_function_is_generic(function)
            ):
                connected_returns.setdefault(reference, set()).add(pin)

    results: list[ConnectorReturnCoverage] = []
    for reference, pins in sorted(connected_signal_pins.items()):
        if len(pins) < 3 or connected_returns.get(reference):
            continue
        evidence_pins = pins | all_return_pins.get(reference, set())
        results.append(
            ConnectorReturnCoverage(
                reference=reference,
                symbol=symbols_by_reference[reference.casefold()][1],
                connected_pin_count=len(pins),
                pins={pin: tuple(sorted(pin_nets.get(pin, ()))) for pin in sorted(evidence_pins)},
            )
        )
    return tuple(results)
