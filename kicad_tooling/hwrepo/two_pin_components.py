"""Find supported fitted two-pin components whose schematic pins share one net."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from types import MappingProxyType

from .casefold_mapping_lookup import lookup_unique_casefold
from .component_role_models import ComponentRoleBinding, ComponentRoleMap
from .component_roles import resolve_component_role_map
from .netlist_contract_models import NetlistContract
from .netlist_pin_assignments import netlist_pin_net_index

_SUPPORTED_DEVICE_SYMBOL = re.compile(
    r"^Device:(?P<kind>R|C|L|D|Fuse|Polyfuse|FerriteBead|Crystal|Varistor|Thermistor)"
    r"(?:_(?P<variant>[A-Za-z0-9_]+))?$",
    re.IGNORECASE,
)
_SUPPORTED_SWITCH_SYMBOL = re.compile(r"^Switch:SW_SPST$", re.IGNORECASE)
_SUPPORTED_LED_SYMBOLS = frozenset({"Device:LED"})
_SUPPORTED_BUZZER_SYMBOLS = frozenset({"Device:Buzzer"})
_SUPPORTED_SPEAKER_SYMBOLS = frozenset({"Device:Speaker"})
_SUPPORTED_BATTERY_SYMBOLS = frozenset({"Device:Battery"})
_SUPPORTED_MOTOR_SYMBOLS = frozenset({"Motor:Motor_DC"})
_SUPPORTED_SOLAR_CELL_SYMBOLS = frozenset({"Device:Solar_Cell"})
_SUPPORTED_THERMOCOUPLE_SYMBOLS = frozenset(
    {
        "Device:Thermocouple",
        "Device:Thermocouple_Alt",
        "Device:Thermocouple_Block",
    }
)
_SUPPORTED_THERMISTOR_SYMBOLS = frozenset(
    {
        "Device:Thermistor",
        "Device:Thermistor_NTC",
        "Device:Thermistor_PTC",
        "Device:Thermistor_US",
        "Device:Thermistor_NTC_US",
        "Device:Thermistor_PTC_US",
    }
)
_KIND_NAMES = MappingProxyType(
    {
        "r": "resistor",
        "c": "capacitor",
        "l": "inductor",
        "d": "diode",
        "fuse": "fuse",
        "polyfuse": "polyfuse",
        "ferritebead": "ferrite_bead",
        "crystal": "crystal",
        "varistor": "varistor",
        "thermistor": "thermistor",
    }
)


@dataclass(frozen=True, slots=True)
class TwoPinComponentOnSameNet:
    """A complete, fitted supported component with both pins on one native net."""

    reference: str
    symbol: str
    value: str
    kind: str
    pin_numbers: tuple[str, str]
    net: str
    role_binding: ComponentRoleBinding | None = None
    source_netlist: NetlistContract | None = field(default=None, compare=False, repr=False)


def _supported_native_kind(symbol: str) -> str | None:
    match = _SUPPORTED_DEVICE_SYMBOL.fullmatch(symbol)
    if match is not None:
        native_kind = match.group("kind").casefold()
        if native_kind == "ferritebead" and (match.group("variant") or "").casefold() not in {
            "",
            "small",
        }:
            return None
        if native_kind == "varistor" and symbol not in {
            "Device:Varistor",
            "Device:Varistor_US",
        }:
            return None
        if native_kind == "thermistor" and symbol not in _SUPPORTED_THERMISTOR_SYMBOLS:
            return None
        return _KIND_NAMES[native_kind]
    if _SUPPORTED_SWITCH_SYMBOL.fullmatch(symbol):
        return "switch"
    if symbol in _SUPPORTED_LED_SYMBOLS:
        return "led"
    if symbol in _SUPPORTED_BUZZER_SYMBOLS:
        return "buzzer"
    if symbol in _SUPPORTED_SPEAKER_SYMBOLS:
        return "speaker"
    if symbol in _SUPPORTED_BATTERY_SYMBOLS:
        return "battery"
    if symbol in _SUPPORTED_MOTOR_SYMBOLS:
        return "motor"
    if symbol in _SUPPORTED_SOLAR_CELL_SYMBOLS:
        return "solar_cell"
    if symbol in _SUPPORTED_THERMOCOUPLE_SYMBOLS:
        return "thermocouple"
    return None


def two_pin_component_is_current(component: TwoPinComponentOnSameNet) -> bool:
    """Check a retained two-pin observation against its exact native netlist."""
    observed = component.source_netlist
    if observed is None:
        return False

    native_component = lookup_unique_casefold(observed.components, component.reference)
    symbol = lookup_unique_casefold(observed.component_symbols, component.reference)
    pin_numbers = lookup_unique_casefold(observed.component_pin_numbers, component.reference)
    if (
        native_component is None
        or symbol != component.symbol
        or native_component.value != component.value
        or component.reference.casefold()
        in {reference.casefold() for reference in observed.dnp_components}
        or pin_numbers is None
        or symbol is None
    ):
        return False

    ordered_pin_numbers = tuple(sorted(pin_numbers, key=lambda item: (item.casefold(), item)))
    if (
        ordered_pin_numbers != component.pin_numbers
        or len({number.casefold() for number in ordered_pin_numbers}) != 2
    ):
        return False

    assignments = netlist_pin_net_index(observed)
    if any(
        assignments.get(f"{component.reference}.{number}".casefold(), set()) != {component.net}
        for number in component.pin_numbers
    ):
        return False

    native_kind = _supported_native_kind(symbol)
    binding = component.role_binding
    if native_kind is not None:
        return native_kind == component.kind and binding is None
    if (
        binding is None
        or binding.role != component.kind
        or binding.symbol != symbol
        or native_component.part_id != binding.part_id
        or native_component.footprint != binding.footprint
    ):
        return False

    expected_pins = tuple(
        sorted(binding.pins, key=lambda item: (item.number.casefold(), item.number))
    )
    if tuple(item.number for item in expected_pins) != ordered_pin_numbers:
        return False
    functions = {pin.casefold(): value for pin, value in observed.pin_functions.items()}
    electrical_types = {
        pin.casefold(): value.casefold() for pin, value in observed.pin_electrical_types.items()
    }
    return all(
        functions.get(f"{component.reference}.{item.number}".casefold()) == item.function
        and electrical_types.get(f"{component.reference}.{item.number}".casefold())
        == item.electrical_type.casefold()
        for item in expected_pins
    )


def two_pin_components_on_same_net(
    observed: NetlistContract,
    component_role_map: ComponentRoleMap | None = None,
) -> tuple[TwoPinComponentOnSameNet, ...]:
    """Return bounded review candidates without deciding whether a short is intentional.

    Recognition requires an exact supported symbol identity, exactly two
    distinct native pin numbers, one unambiguous net per pin, and a fitted
    component. Supported identities are the listed ``Device`` families and
    ``Switch:SW_SPST``, ``Motor:Motor_DC``, ``Device:Solar_Cell``, and the
    three exact two-terminal ``Device:Thermocouple`` symbols. Custom
    capacitors, LEDs, batteries, and motors are eligible only when an exact project-authored
    role binding matches their PART_ID, symbol, footprint, and complete pin
    inventory. Other project-specific symbols and incomplete inventories are
    skipped.
    """
    role_bindings = resolve_component_role_map(observed, component_role_map).by_reference
    dnp = {reference.casefold() for reference in observed.dnp_components}
    nets_by_pin: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            nets_by_pin.setdefault(pin.casefold(), set()).add(net)

    results: list[TwoPinComponentOnSameNet] = []
    for reference, symbol in observed.component_symbols.items():
        if reference.casefold() in dnp:
            continue
        kind = _supported_native_kind(symbol)
        if kind is not None:
            role_binding = None
        else:
            role_binding = role_bindings.get(reference.casefold())
            if role_binding is None or role_binding.role not in {
                "capacitor",
                "led",
                "battery",
                "motor",
            }:
                continue
            kind = role_binding.role

        raw_pin_numbers = observed.component_pin_numbers.get(reference)
        if raw_pin_numbers is None:
            raw_pin_numbers = next(
                (
                    numbers
                    for candidate, numbers in observed.component_pin_numbers.items()
                    if candidate.casefold() == reference.casefold()
                ),
                (),
            )
        pin_numbers = tuple(sorted(raw_pin_numbers, key=lambda item: (item.casefold(), item)))
        if len(pin_numbers) != 2 or len({item.casefold() for item in pin_numbers}) != 2:
            continue

        pin_nets = tuple(
            nets_by_pin.get(f"{reference}.{number}".casefold(), set()) for number in pin_numbers
        )
        if any(len(assigned) != 1 for assigned in pin_nets):
            continue
        first_net = next(iter(pin_nets[0]))
        second_net = next(iter(pin_nets[1]))
        if first_net != second_net:
            continue

        component = next(
            (
                item
                for candidate, item in observed.components.items()
                if candidate.casefold() == reference.casefold()
            ),
            None,
        )
        if component is None:
            continue
        results.append(
            TwoPinComponentOnSameNet(
                reference=reference,
                symbol=symbol,
                value=component.value,
                kind=kind,
                pin_numbers=(pin_numbers[0], pin_numbers[1]),
                net=first_net,
                role_binding=role_binding,
                source_netlist=observed,
            )
        )
    return tuple(sorted(results, key=lambda item: (item.reference.casefold(), item.reference)))
