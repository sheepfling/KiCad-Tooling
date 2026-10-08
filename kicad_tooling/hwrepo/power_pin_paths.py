"""Conservative review hints for power inputs without a recognized source path."""

from __future__ import annotations

import re
from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TypeVar

from .bus_heuristics import resistance_ohms
from .connector_pins import connector_candidate_references, power_function_key
from .models import NetlistContract
from .return_nets import is_return_like_net_name

_CAPACITOR_SYMBOL = re.compile(
    r"^(?:Device:C(?:_[A-Za-z0-9_]+)?|Device:CP(?:_[A-Za-z0-9_]+)?|"
    r"[^:]+:[^:]*[Cc]apacitor[^:]*)$"
)
_RESISTOR_SYMBOL = re.compile(r"^Device:R(?:_[A-Za-z0-9_]+)?$", re.IGNORECASE)
_INDUCTOR_SYMBOL = re.compile(r"^Device:L(?:_[A-Za-z0-9_]+)?$", re.IGNORECASE)
_SUPPORTED_FIXED_PATH_SYMBOLS = frozenset(
    {
        "device:ferritebead",
        "device:fuse",
        "device:polyfuse",
    }
)
_BRIDGED_JUMPER_TOPOLOGIES: dict[str, tuple[dict[str, str], tuple[tuple[str, ...], ...]]] = {
    "jumper:solderjumper_2_bridged": (
        {"1": "a", "2": "b"},
        (("1", "2"),),
    ),
    "jumper:solderjumper_3_bridged12": (
        {"1": "a", "2": "c", "3": "b"},
        (("1", "2"),),
    ),
    "jumper:solderjumper_3_bridged123": (
        {"1": "a", "2": "c", "3": "b"},
        (("1", "2", "3"),),
    ),
}
_SUPPORTED_DIRECTIONAL_PATH_SYMBOLS = frozenset({"device:d", "device:d_schottky"})
_Value = TypeVar("_Value")


@dataclass(frozen=True)
class PowerInputSourcePathGap:
    """A decoupled power input without a recognized source anchor or bounded path."""

    net: str
    input_pins: tuple[str, ...]
    capacitor_references: tuple[str, ...]
    source_nets: tuple[str, ...]


def _casefold_lookup(mapping: Mapping[str, _Value], key: str) -> _Value | None:
    matches = [
        value for candidate, value in mapping.items() if candidate.casefold() == key.casefold()
    ]
    return matches[0] if len(matches) == 1 else None


def _is_return_net(observed: NetlistContract, net: str) -> bool:
    return is_return_like_net_name(net) or any(
        is_return_like_net_name(observed.pin_functions.get(pin, ""))
        for pin in observed.nets.get(net, ())
    )


def _native_two_pin_nets(
    observed: NetlistContract,
    reference: str,
    nets_by_pin: dict[str, set[str]],
) -> tuple[str, str] | None:
    numbers = _casefold_lookup(observed.component_pin_numbers, reference)
    if not isinstance(numbers, tuple) or len(numbers) != 2 or len(set(numbers)) != 2:
        return None
    assigned = [nets_by_pin.get(f"{reference}.{number}".casefold(), set()) for number in numbers]
    if any(len(item) != 1 for item in assigned):
        return None
    first, second = (next(iter(item)) for item in assigned)
    if first == second:
        return None
    return first, second


def _fitted_capacitors_to_return(
    observed: NetlistContract,
    nets_by_pin: dict[str, set[str]],
) -> dict[str, set[str]]:
    dnp = {reference.casefold() for reference in observed.dnp_components}
    capacitors_by_supply_net: dict[str, set[str]] = {}
    for reference, symbol in observed.component_symbols.items():
        if reference.casefold() in dnp or _CAPACITOR_SYMBOL.fullmatch(symbol) is None:
            continue
        if _casefold_lookup(observed.components, reference) is None:
            continue
        endpoints = _native_two_pin_nets(observed, reference, nets_by_pin)
        if endpoints is None:
            continue
        return_nets = {net for net in endpoints if _is_return_net(observed, net)}
        if len(return_nets) != 1:
            continue
        supply_net = next(iter(set(endpoints) - return_nets))
        capacitors_by_supply_net.setdefault(supply_net, set()).add(reference)
    return capacitors_by_supply_net


def _supported_path_edges(
    observed: NetlistContract,
    nets_by_pin: dict[str, set[str]],
) -> dict[str, set[str]]:
    dnp = {reference.casefold() for reference in observed.dnp_components}
    adjacent: dict[str, set[str]] = {}
    for reference, symbol in observed.component_symbols.items():
        if reference.casefold() in dnp:
            continue
        component = _casefold_lookup(observed.components, reference)
        if component is None:
            continue
        symbol_key = symbol.casefold()
        jumper_topology = _BRIDGED_JUMPER_TOPOLOGIES.get(symbol_key)
        if jumper_topology is not None:
            expected_roles, bridged_pin_groups = jumper_topology
            pin_numbers = _casefold_lookup(observed.component_pin_numbers, reference)
            if (
                not isinstance(pin_numbers, tuple)
                or len(pin_numbers) != len(expected_roles)
                or {number.casefold() for number in pin_numbers} != set(expected_roles)
            ):
                continue
            nets_by_pin_number: dict[str, str] = {}
            for number in pin_numbers:
                pin = f"{reference}.{number}"
                function = _casefold_lookup(observed.pin_functions, pin)
                function_key = function.strip().casefold() if isinstance(function, str) else ""
                number_key = number.casefold()
                if expected_roles.get(number_key) != function_key:
                    break
                assigned = nets_by_pin.get(pin.casefold(), set())
                if len(assigned) != 1:
                    break
                nets_by_pin_number[number_key] = next(iter(assigned))
            else:
                for group in bridged_pin_groups:
                    group_nets = tuple(nets_by_pin_number[number] for number in group)
                    for index, first in enumerate(group_nets):
                        for second in group_nets[index + 1 :]:
                            if first == second:
                                continue
                            adjacent.setdefault(first, set()).add(second)
                            adjacent.setdefault(second, set()).add(first)
            continue
        if symbol_key in _SUPPORTED_DIRECTIONAL_PATH_SYMBOLS:
            pin_numbers = _casefold_lookup(observed.component_pin_numbers, reference)
            if (
                not isinstance(pin_numbers, tuple)
                or len(pin_numbers) != 2
                or len({number.casefold() for number in pin_numbers}) != 2
            ):
                continue
            nets_by_role: dict[str, set[str]] = {"a": set(), "k": set()}
            for number in pin_numbers:
                pin = f"{reference}.{number}"
                function = _casefold_lookup(observed.pin_functions, pin)
                function_key = function.strip().casefold() if isinstance(function, str) else ""
                if function_key not in nets_by_role:
                    break
                assigned = nets_by_pin.get(pin.casefold(), set())
                if len(assigned) != 1:
                    break
                nets_by_role[function_key].update(assigned)
            else:
                anode_nets = nets_by_role["a"]
                cathode_nets = nets_by_role["k"]
                if len(anode_nets) == 1 and len(cathode_nets) == 1 and anode_nets != cathode_nets:
                    # Search starts at the load and walks upstream toward a source.
                    # A conducting diode therefore permits cathode -> anode only.
                    cathode_net = next(iter(cathode_nets))
                    anode_net = next(iter(anode_nets))
                    adjacent.setdefault(cathode_net, set()).add(anode_net)
            continue
        if _RESISTOR_SYMBOL.fullmatch(symbol):
            resistance = resistance_ohms(component.value)
            if resistance is None or resistance > 1.0:
                continue
        elif not (
            _INDUCTOR_SYMBOL.fullmatch(symbol) or symbol.casefold() in _SUPPORTED_FIXED_PATH_SYMBOLS
        ):
            continue
        endpoints = _native_two_pin_nets(observed, reference, nets_by_pin)
        if endpoints is None:
            continue
        first, second = endpoints
        adjacent.setdefault(first, set()).add(second)
        adjacent.setdefault(second, set()).add(first)
    return adjacent


def _reaches_any_source(
    start: str,
    source_nets: set[str],
    adjacent: dict[str, set[str]],
) -> bool:
    pending = deque((start,))
    visited = {start}
    while pending:
        net = pending.popleft()
        if net in source_nets:
            return True
        for candidate in sorted(adjacent.get(net, ())):
            if candidate not in visited:
                visited.add(candidate)
                pending.append(candidate)
    return False


def power_inputs_without_supported_source_paths(
    observed: NetlistContract,
    *,
    covered_input_pins: frozenset[str] = frozenset(),
    declared_connector_references: tuple[str, ...] = (),
) -> tuple[PowerInputSourcePathGap, ...]:
    """Find bounded source-path review candidates from native netlist evidence.

    A candidate must be a fitted internal ``power_in`` pin on a net with a
    fitted two-terminal capacitor to a recognized return. It is reported when
    no recognized positive-rail or fitted ``power_out`` source anchor exists,
    or when an anchor exists but no bounded path reaches it. Paths count only
    through fitted, exactly inventoried two-pin resistors at or below 1 ohm,
    inductors, ferrite beads, fuses, polyfuses, or exact bridged solder-jumper
    identities with their native pin roles. Three-terminal jumpers are limited
    to the exact ``Bridged12`` and ``Bridged123`` variants. Exact
    ``Device:D`` and ``Device:D_Schottky`` symbols count only when native pin
    functions uniquely identify anode and cathode; the search follows the
    conducting direction. This is a review heuristic, not a proof that a
    particular path is required.
    """
    dnp = {reference.casefold() for reference in observed.dnp_components}
    connector_references = {
        reference.casefold()
        for reference in connector_candidate_references(observed, declared_connector_references)
    }
    nets_by_pin: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            nets_by_pin.setdefault(pin.casefold(), set()).add(net)

    source_nets: set[str] = set()
    for net, pins in observed.nets.items():
        if _is_return_net(observed, net):
            continue
        if power_function_key(net) is not None or any(
            observed.pin_electrical_types.get(pin, "").casefold() == "power_out"
            and pin.rsplit(".", 1)[0].casefold() not in dnp
            for pin in pins
        ):
            source_nets.add(net)
    capacitors_by_supply_net = _fitted_capacitors_to_return(observed, nets_by_pin)
    if not capacitors_by_supply_net:
        return ()
    adjacent = _supported_path_edges(observed, nets_by_pin)
    covered = {pin.casefold() for pin in covered_input_pins}
    pins_by_net: dict[str, set[str]] = {}
    for pin, electrical_type in observed.pin_electrical_types.items():
        if electrical_type.casefold() != "power_in" or pin.casefold() in covered:
            continue
        reference = pin.rsplit(".", 1)[0]
        if reference.casefold() in dnp or reference.casefold() in connector_references:
            continue
        assigned_nets = nets_by_pin.get(pin.casefold(), set())
        if len(assigned_nets) != 1:
            continue
        net = next(iter(assigned_nets))
        if _is_return_net(observed, net) or net not in capacitors_by_supply_net:
            continue
        if net in source_nets or _reaches_any_source(net, source_nets, adjacent):
            continue
        pins_by_net.setdefault(net, set()).add(pin)

    return tuple(
        PowerInputSourcePathGap(
            net=net,
            input_pins=tuple(sorted(pins)),
            capacitor_references=tuple(sorted(capacitors_by_supply_net[net])),
            source_nets=tuple(sorted(source_nets)),
        )
        for net, pins in sorted(pins_by_net.items())
    )
