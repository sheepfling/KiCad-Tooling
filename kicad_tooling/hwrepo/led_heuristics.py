"""Narrow LED topology review hints from native KiCad netlist evidence."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass

from .bus_heuristics import direct_resistors
from .connector_pins import power_function_key
from .models import ComponentRoleBinding, ComponentRoleMap, NetlistContract
from .return_nets import is_return_like_net_name

_SUPPORTED_LED_SYMBOLS = frozenset({"device:led"})
_OUTPUT_PIN_TYPES = frozenset(
    {"output", "bidirectional", "tri_state", "open_collector", "open_emitter"}
)
_CANONICAL_RETURN_NET_NAMES = frozenset(
    {"0v", "gnd", "agnd", "dgnd", "pgnd", "vss", "vssa", "vssd", "vssp", "rtn", "return"}
)


@dataclass(frozen=True)
class DirectLedRailBridge:
    reference: str
    symbol: str
    pins: tuple[str, str]
    positive_net: str
    return_net: str


@dataclass(frozen=True)
class LedOutputWithoutVisibleSeriesResistor:
    """A fitted LED shares a rail-spanning path directly with an output pin."""

    reference: str
    symbol: str
    led_pins: tuple[str, str]
    output_pins: tuple[str, ...]
    output_pin_types: tuple[str, ...]
    driven_net: str
    opposite_net: str
    opposite_net_role: str
    role_binding: ComponentRoleBinding | None = None
    role_binding_sha256: str | None = None


@dataclass(frozen=True)
class ComponentRoleResolution:
    """Exact mapped component identities and any stale project declarations."""

    by_reference: Mapping[str, ComponentRoleBinding]
    issues: tuple[str, ...]


def _role_binding_digest(binding: ComponentRoleBinding) -> str:
    payload = binding.model_dump(mode="json")
    payload["pins"] = sorted(
        payload["pins"], key=lambda item: (item["number"].casefold(), item["number"])
    )
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def resolve_component_role_map(
    observed: NetlistContract, role_map: ComponentRoleMap | None
) -> ComponentRoleResolution:
    """Resolve only exact project-authored part, symbol, footprint and pin identities."""
    if role_map is None:
        return ComponentRoleResolution(by_reference={}, issues=())

    components = {reference.casefold(): item for reference, item in observed.components.items()}
    references_by_part_id: dict[str, list[str]] = {}
    for reference, component in observed.components.items():
        if component.part_id is not None:
            references_by_part_id.setdefault(component.part_id, []).append(reference)
    symbols = {
        reference.casefold(): value for reference, value in observed.component_symbols.items()
    }
    inventories = {
        reference.casefold(): tuple(numbers)
        for reference, numbers in observed.component_pin_numbers.items()
    }
    pin_functions = {pin.casefold(): value for pin, value in observed.pin_functions.items()}
    pin_types = {pin.casefold(): value for pin, value in observed.pin_electrical_types.items()}

    resolved: dict[str, ComponentRoleBinding] = {}
    issues: list[str] = []
    for binding in sorted(
        role_map.entries, key=lambda item: (item.part_id.casefold(), item.part_id)
    ):
        references = tuple(
            sorted(
                references_by_part_id.get(binding.part_id, ()),
                key=lambda item: (item.casefold(), item),
            )
        )
        if not references:
            issues.append(
                f"Component role map for PART_ID {binding.part_id!r} is stale: "
                "no native component uses this exact PART_ID."
            )
            continue

        expected_pins = tuple(
            sorted(binding.pins, key=lambda item: (item.number.casefold(), item.number))
        )
        for reference in references:
            key = reference.casefold()
            component = components[key]
            actual_symbol = symbols.get(key)
            if actual_symbol != binding.symbol:
                issues.append(
                    f"Component role map for PART_ID {binding.part_id!r} is stale at {reference}: "
                    f"native symbol is {actual_symbol or '<missing>'!r}, "
                    f"expected {binding.symbol!r}."
                )
                continue
            if component.footprint != binding.footprint:
                issues.append(
                    f"Component role map for PART_ID {binding.part_id!r} is stale at {reference}: "
                    f"native footprint is {component.footprint or '<missing>'!r}, "
                    f"expected {binding.footprint!r}."
                )
                continue

            actual_numbers = inventories.get(key, ())
            actual_pins = tuple(
                (
                    number,
                    pin_functions.get(f"{reference}.{number}".casefold()),
                    pin_types.get(f"{reference}.{number}".casefold()),
                )
                for number in actual_numbers
            )
            expected_signature = tuple(
                (item.number, item.function, item.electrical_type.casefold())
                for item in expected_pins
            )
            actual_signature = tuple(
                (number, function, electrical_type.casefold() if electrical_type else None)
                for number, function, electrical_type in sorted(
                    actual_pins, key=lambda item: (item[0].casefold(), item[0])
                )
            )
            if actual_signature != expected_signature:
                issues.append(
                    f"Component role map for PART_ID {binding.part_id!r} is stale at {reference}: "
                    "the complete native pin number, function, and electrical-type inventory "
                    "does not match."
                )
                continue
            resolved[key] = binding
    return ComponentRoleResolution(by_reference=resolved, issues=tuple(issues))


def _net_assignments(
    observed: NetlistContract,
) -> tuple[dict[str, set[str]], dict[str, tuple[str, ...]]]:
    pin_nets: dict[str, set[str]] = {}
    net_pins: dict[str, tuple[str, ...]] = {}
    for net, pins in observed.nets.items():
        net_pins[net] = tuple(pins)
        for pin in pins:
            pin_nets.setdefault(pin.casefold(), set()).add(net)
    return pin_nets, net_pins


def _net_roles(
    net: str, net_pins: dict[str, tuple[str, ...]], observed: NetlistContract
) -> tuple[bool, bool]:
    functions = tuple(observed.pin_functions.get(pin, "") for pin in net_pins.get(net, ()))
    is_positive = power_function_key(net) is not None or any(
        power_function_key(function) is not None for function in functions
    )
    is_return = is_return_like_net_name(net) or any(
        is_return_like_net_name(function) for function in functions
    )
    return is_positive, is_return


def _exclusive_rail_role(
    net: str, net_pins: dict[str, tuple[str, ...]], observed: NetlistContract
) -> str | None:
    is_positive, is_return = _net_roles(net, net_pins, observed)
    if is_positive == is_return:
        return None
    return "positive" if is_positive else "return"


def _canonical_return_net_name(net: str) -> bool:
    compact = "".join(character for character in net.casefold() if character.isalnum())
    return compact in _CANONICAL_RETURN_NET_NAMES


def leds_directly_between_positive_and_return_nets(
    observed: NetlistContract,
) -> tuple[DirectLedRailBridge, ...]:
    """Find supported two-pin LEDs whose native pin nets directly span rails."""
    dnp = {reference.casefold() for reference in observed.dnp_components}
    pin_nets, net_pins = _net_assignments(observed)

    results: list[DirectLedRailBridge] = []
    for reference, symbol in sorted(observed.component_symbols.items()):
        if reference.casefold() in dnp or symbol.casefold() not in _SUPPORTED_LED_SYMBOLS:
            continue
        pin_numbers = tuple(sorted(observed.component_pin_numbers.get(reference, ())))
        if len(pin_numbers) != 2:
            continue
        pins = (f"{reference}.{pin_numbers[0]}", f"{reference}.{pin_numbers[1]}")
        assigned = tuple(pin_nets.get(pin.casefold(), set()) for pin in pins)
        if any(len(nets) != 1 for nets in assigned):
            continue
        first_net = next(iter(assigned[0]))
        second_net = next(iter(assigned[1]))
        if first_net == second_net:
            continue

        first_positive, first_return = _net_roles(first_net, net_pins, observed)
        second_positive, second_return = _net_roles(second_net, net_pins, observed)
        if first_positive and not first_return and second_return and not second_positive:
            positive_net, return_net = first_net, second_net
        elif second_positive and not second_return and first_return and not first_positive:
            positive_net, return_net = second_net, first_net
        else:
            continue
        results.append(
            DirectLedRailBridge(
                reference=reference,
                symbol=symbol,
                pins=pins,
                positive_net=positive_net,
                return_net=return_net,
            )
        )
    return tuple(results)


def leds_directly_driven_without_visible_series_resistor(
    observed: NetlistContract,
    component_role_map: ComponentRoleMap | None = None,
) -> tuple[LedOutputWithoutVisibleSeriesResistor, ...]:
    """Find exact two-pin LEDs directly sharing an output net and a rail.

    This narrow prompt uses native output pin types and recognized rail evidence.
    It ignores a return-like intermediate net when a fitted resistor visibly
    connects that net to a separately recognized return net.
    """
    dnp = {reference.casefold() for reference in observed.dnp_components}
    roles = resolve_component_role_map(observed, component_role_map).by_reference
    pin_nets, net_pins = _net_assignments(observed)
    resistors_by_net: dict[str, list[str]] = {}
    for resistor in direct_resistors(observed):
        resistors_by_net.setdefault(resistor.first_net, []).append(resistor.second_net)
        resistors_by_net.setdefault(resistor.second_net, []).append(resistor.first_net)
    output_pins_by_net: dict[str, list[tuple[str, str]]] = {}
    for pin, raw_type in observed.pin_electrical_types.items():
        reference = pin.rsplit(".", 1)[0]
        pin_type = raw_type.strip().casefold()
        if (
            reference.casefold() not in dnp
            and pin_type in _OUTPUT_PIN_TYPES
            and (assigned := pin_nets.get(pin.casefold())) is not None
            and len(assigned) == 1
        ):
            net = next(iter(assigned))
            output_pins_by_net.setdefault(net, []).append((pin, pin_type))

    findings: list[LedOutputWithoutVisibleSeriesResistor] = []
    for reference, symbol in sorted(
        observed.component_symbols.items(), key=lambda item: (item[0].casefold(), item[0])
    ):
        role_binding = roles.get(reference.casefold())
        if reference.casefold() in dnp or (
            symbol.casefold() not in _SUPPORTED_LED_SYMBOLS and role_binding is None
        ):
            continue
        pin_numbers = next(
            (
                numbers
                for candidate, numbers in observed.component_pin_numbers.items()
                if candidate.casefold() == reference.casefold()
            ),
            (),
        )
        ordered_numbers = tuple(sorted(pin_numbers, key=str.casefold))
        if len(ordered_numbers) != 2 or len({item.casefold() for item in ordered_numbers}) != 2:
            continue
        led_pins = tuple(f"{reference}.{number}" for number in ordered_numbers)
        assigned_nets = tuple(pin_nets.get(pin.casefold(), set()) for pin in led_pins)
        if any(len(assigned) != 1 for assigned in assigned_nets):
            continue
        led_nets = tuple(next(iter(assigned)) for assigned in assigned_nets)
        if led_nets[0] == led_nets[1]:
            continue

        matches: list[LedOutputWithoutVisibleSeriesResistor] = []
        for output_index in range(2):
            driven_net = led_nets[output_index]
            opposite_net = led_nets[1 - output_index]
            output_pins = tuple(
                (pin, pin_type)
                for pin, pin_type in output_pins_by_net.get(driven_net, ())
                if pin.rsplit(".", 1)[0].casefold() != reference.casefold()
            )
            if not output_pins:
                continue

            opposite_role = _exclusive_rail_role(opposite_net, net_pins, observed)
            if opposite_role is None:
                continue
            opposite_functions = tuple(
                observed.pin_functions.get(pin, "") for pin in net_pins.get(opposite_net, ())
            )
            if (
                opposite_role == "return"
                and not _canonical_return_net_name(opposite_net)
                and not any(is_return_like_net_name(function) for function in opposite_functions)
                and any(
                    _exclusive_rail_role(far_net, net_pins, observed) == "return"
                    for far_net in resistors_by_net.get(opposite_net, ())
                )
            ):
                continue

            sorted_drivers = tuple(
                sorted(output_pins, key=lambda item: (item[0].casefold(), item[0], item[1]))
            )
            matches.append(
                LedOutputWithoutVisibleSeriesResistor(
                    reference=reference,
                    symbol=symbol,
                    led_pins=(led_pins[0], led_pins[1]),
                    output_pins=tuple(pin for pin, _ in sorted_drivers),
                    output_pin_types=tuple(f"{pin}={pin_type}" for pin, pin_type in sorted_drivers),
                    driven_net=driven_net,
                    opposite_net=opposite_net,
                    opposite_net_role=opposite_role,
                    role_binding=role_binding,
                    role_binding_sha256=(
                        None if role_binding is None else _role_binding_digest(role_binding)
                    ),
                )
            )
        if len(matches) == 1:
            findings.append(matches[0])
    return tuple(findings)
