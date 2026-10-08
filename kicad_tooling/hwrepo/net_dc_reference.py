"""Review nets whose fitted schematic pins are only connectors and capacitors."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .connector_pins import connector_candidate_references
from .models import NetlistContract
from .return_nets import is_return_like_net_name

_CAPACITOR_SYMBOL = re.compile(
    r"^(?:Device:C(?:_[A-Za-z0-9_]+)?|Device:CP(?:_[A-Za-z0-9_]+)?|"
    r"[^:]+:[^:]*[Cc]apacitor[^:]*)$"
)


@dataclass(frozen=True)
class ConnectorCapacitorOnlyNet:
    """A net whose fitted assigned pins are all recognized connectors or capacitors."""

    net: str
    connector_pins: tuple[str, ...]
    capacitor_pins: tuple[str, ...]
    component_symbols: tuple[str, ...]


def connector_capacitor_only_nets(
    observed: NetlistContract,
    declared_references: tuple[str, ...] = (),
) -> tuple[ConnectorCapacitorOnlyNet, ...]:
    """Return bounded candidates for nets without a visible local DC anchor.

    A candidate needs at least one fitted connector pin and one fitted pin from
    an exactly recognized capacitor symbol. Every other fitted pin assigned to
    that net must also belong to one of those two classes. Return-like nets,
    ambiguous pin assignments, unknown symbols, and DNP components are not
    treated as evidence. This does not trace a DC path or establish intent.
    """
    dnp = {reference.casefold() for reference in observed.dnp_components}
    symbols_by_reference: dict[str, str] = {}
    ambiguous_symbols: set[str] = set()
    for reference, symbol in observed.component_symbols.items():
        key = reference.casefold()
        if key in symbols_by_reference and symbols_by_reference[key] != symbol:
            ambiguous_symbols.add(key)
        symbols_by_reference[key] = symbol

    explicit_connectors = {reference.casefold() for reference in declared_references}
    connector_references = {
        reference.casefold()
        for reference in connector_candidate_references(observed, declared_references)
    } - dnp
    capacitors = {
        reference.casefold(): reference
        for reference, symbol in observed.component_symbols.items()
        if reference.casefold() not in dnp
        and reference.casefold() not in ambiguous_symbols
        and _CAPACITOR_SYMBOL.fullmatch(symbol) is not None
    }

    nets_by_pin: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            nets_by_pin.setdefault(pin.casefold(), set()).add(net)
    ambiguous_assignments = {
        pin for pin, assigned_nets in nets_by_pin.items() if len(assigned_nets) != 1
    }

    findings: list[ConnectorCapacitorOnlyNet] = []
    for net, raw_pins in sorted(
        observed.nets.items(), key=lambda item: (item[0].casefold(), item[0])
    ):
        if is_return_like_net_name(net):
            continue
        pins = tuple(sorted(set(raw_pins), key=lambda value: (value.casefold(), value)))
        if not pins or any(pin.casefold() in ambiguous_assignments for pin in pins):
            continue
        if any(is_return_like_net_name(observed.pin_functions.get(pin, "")) for pin in pins):
            continue

        connector_pins: list[str] = []
        capacitor_pins: list[str] = []
        component_symbols: set[str] = set()
        unsupported_pin = False
        for pin in pins:
            reference, separator, _pin_number = pin.rpartition(".")
            if not separator or not reference:
                unsupported_pin = True
                break
            key = reference.casefold()
            if key in dnp or key in ambiguous_symbols:
                continue
            symbol = symbols_by_reference.get(key)
            if symbol is None:
                unsupported_pin = True
                break
            if key in capacitors:
                capacitor_pins.append(pin)
                component_symbols.add(f"{reference}={symbol}")
            elif key in connector_references and (
                key in explicit_connectors or _is_connector_symbol(symbol)
            ):
                connector_pins.append(pin)
                component_symbols.add(f"{reference}={symbol}")
            else:
                unsupported_pin = True
                break

        if unsupported_pin or not connector_pins or not capacitor_pins:
            continue
        findings.append(
            ConnectorCapacitorOnlyNet(
                net=net,
                connector_pins=tuple(connector_pins),
                capacitor_pins=tuple(capacitor_pins),
                component_symbols=tuple(sorted(component_symbols, key=str.casefold)),
            )
        )
    return tuple(findings)


def _is_connector_symbol(symbol: str) -> bool:
    """Reject explicit non-connector Device symbols even on J/P/X/CN references."""
    library, separator, name = symbol.partition(":")
    if not separator:
        return False
    normalized_library = library.casefold()
    normalized_name = re.sub(r"[^a-z0-9]+", "", name.casefold())
    if normalized_library == "connector":
        return not normalized_name.startswith("testpoint")
    if normalized_library.startswith("connector_"):
        return True
    return normalized_library != "device"
