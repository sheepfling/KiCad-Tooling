"""Recognize JTAG signal roles on complete, fitted native endpoints."""

from __future__ import annotations

import re
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass

from .casefold_mapping_lookup import casefolded_unique_index
from .connector_pin_metadata import connector_pin_metadata_matches_inventory
from .netlist_contract_models import ComponentContract, NetlistContract
from .netlist_pin_assignments import netlist_pin_net_index

_FUNCTION_TOKENS = re.compile(r"[A-Z0-9]+", re.IGNORECASE)
_SIGNAL_ROLE_TOKENS = {
    "tck": "test_clock",
    "tms": "test_mode_select",
    "tdi": "test_data_in",
    "tdo": "test_data_out",
    "trst": "test_reset",
    "trstn": "test_reset",
    "ntrst": "test_reset",
    "rtck": "return_clock",
}


def jtag_signal_roles(function: str) -> frozenset[str]:
    """Classify bounded JTAG native pin-function tokens."""
    tokens = {token.casefold() for token in _FUNCTION_TOKENS.findall(function)}
    return frozenset(role for token, role in _SIGNAL_ROLE_TOKENS.items() if token in tokens)


@dataclass(frozen=True, slots=True)
class JtagNamedRailSignalPin:
    """One complete fitted endpoint pin with a bounded JTAG signal role."""

    pin: str
    function: str
    role: str
    identity_basis: str


@dataclass(frozen=True, slots=True)
class JtagEndpointInventory:
    """Native pin metadata and assignments for fitted JTAG ICs and connectors."""

    symbols: Mapping[str, str]
    reference_spellings: Mapping[str, str]
    components: Mapping[str, ComponentContract]
    inventories: Mapping[str, tuple[str, ...]]
    functions: Mapping[str, str]
    electrical_types: Mapping[str, str]
    assignments: Mapping[str, AbstractSet[str]]
    dnp_references: AbstractSet[str]

    @classmethod
    def from_netlist(cls, observed: NetlistContract) -> JtagEndpointInventory:
        """Build case-folded indexes from a normalized native netlist."""
        return cls(
            symbols=casefolded_unique_index(observed.component_symbols),
            reference_spellings=casefolded_unique_index(
                {reference: reference for reference in observed.component_symbols}
            ),
            components=casefolded_unique_index(observed.components),
            inventories=casefolded_unique_index(observed.component_pin_numbers),
            functions=casefolded_unique_index(observed.pin_functions),
            electrical_types=casefolded_unique_index(observed.pin_electrical_types),
            assignments=netlist_pin_net_index(observed),
            dnp_references=frozenset(reference.casefold() for reference in observed.dnp_components),
        )

    def named_rail_signal_pins(self, reference: str) -> tuple[JtagNamedRailSignalPin, ...]:
        """Return roles only when explicit JTAG text or a complete TCK/TMS pair exists."""
        return jtag_named_rail_signal_pins(self, reference)


def jtag_named_rail_signal_pins(
    inventory: JtagEndpointInventory, reference: str
) -> tuple[JtagNamedRailSignalPin, ...]:
    """Recognize one endpoint's unique JTAG roles from complete native evidence."""
    key = reference.casefold()
    native_reference = inventory.reference_spellings.get(key)
    numbers = inventory.inventories.get(key)
    if (
        native_reference is None
        or key not in inventory.components
        or key in inventory.dnp_references
        or not numbers
        or len({number.casefold() for number in numbers}) != len(numbers)
        or not connector_pin_metadata_matches_inventory(
            key, numbers, inventory.functions, inventory.electrical_types
        )
    ):
        return ()

    functions_by_pin = {
        f"{native_reference}.{number}": inventory.functions[f"{key}.{number.casefold()}"]
        for number in numbers
    }
    explicit_jtag = any(
        "jtag" in {token.casefold() for token in _FUNCTION_TOKENS.findall(function)}
        and jtag_signal_roles(function)
        for function in functions_by_pin.values()
    )
    tck_pins = tuple(
        pin
        for pin, function in functions_by_pin.items()
        if jtag_signal_roles(function) == frozenset({"test_clock"})
        and len(inventory.assignments.get(pin.casefold(), frozenset())) == 1
    )
    tms_pins = tuple(
        pin
        for pin, function in functions_by_pin.items()
        if jtag_signal_roles(function) == frozenset({"test_mode_select"})
        and len(inventory.assignments.get(pin.casefold(), frozenset())) == 1
    )
    paired_jtag = len(tck_pins) == 1 and len(tms_pins) == 1
    if not explicit_jtag and not paired_jtag:
        return ()

    identity_basis = (
        "explicit JTAG pin-function metadata"
        if explicit_jtag
        else "unique assigned native TCK/TMS pair"
    )
    role_counts: dict[str, int] = {}
    for function in functions_by_pin.values():
        for role in jtag_signal_roles(function):
            role_counts[role] = role_counts.get(role, 0) + 1
    signal_pins = tuple(
        JtagNamedRailSignalPin(
            pin=pin,
            function=function,
            role=next(iter(roles)),
            identity_basis=identity_basis,
        )
        for pin, function in functions_by_pin.items()
        if len(roles := jtag_signal_roles(function)) == 1 and role_counts[next(iter(roles))] == 1
    )
    return tuple(sorted(signal_pins, key=lambda item: (item.pin.casefold(), item.pin)))
