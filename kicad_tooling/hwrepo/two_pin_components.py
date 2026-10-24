"""Find supported fitted two-pin components whose schematic pins share one net."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .component_role_models import ComponentRoleBinding, ComponentRoleMap
from .component_roles import resolve_component_role_map
from .models import NetlistContract

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
_KIND_NAMES = {
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


@dataclass(frozen=True)
class TwoPinComponentOnSameNet:
    """A complete, fitted supported component with both pins on one native net."""

    reference: str
    symbol: str
    value: str
    kind: str
    pin_numbers: tuple[str, str]
    net: str
    role_binding: ComponentRoleBinding | None = None


def two_pin_components_on_same_net(
    observed: NetlistContract,
    component_role_map: ComponentRoleMap | None = None,
) -> tuple[TwoPinComponentOnSameNet, ...]:
    """Return bounded review candidates without deciding whether a short is intentional.

    Recognition requires an exact supported symbol identity, exactly two
    distinct native pin numbers, one unambiguous net per pin, and a fitted
    component. Supported identities are the listed ``Device`` families and
    ``Switch:SW_SPST``, ``Motor:Motor_DC``, and ``Device:Solar_Cell``. A
    custom symbol is eligible only when an exact project-authored capacitor
    role binding matches its PART_ID, symbol, footprint, and complete pin
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
        match = _SUPPORTED_DEVICE_SYMBOL.fullmatch(symbol)
        if match is not None:
            native_kind = match.group("kind").casefold()
            if native_kind == "ferritebead" and (match.group("variant") or "").casefold() not in {
                "",
                "small",
            }:
                continue
            if native_kind == "varistor" and symbol not in {
                "Device:Varistor",
                "Device:Varistor_US",
            }:
                continue
            if native_kind == "thermistor" and symbol not in _SUPPORTED_THERMISTOR_SYMBOLS:
                continue
            kind = _KIND_NAMES[native_kind]
            role_binding = None
        elif _SUPPORTED_SWITCH_SYMBOL.fullmatch(symbol):
            kind = "switch"
            role_binding = None
        elif symbol in _SUPPORTED_LED_SYMBOLS:
            kind = "led"
            role_binding = None
        elif symbol in _SUPPORTED_BUZZER_SYMBOLS:
            kind = "buzzer"
            role_binding = None
        elif symbol in _SUPPORTED_SPEAKER_SYMBOLS:
            kind = "speaker"
            role_binding = None
        elif symbol in _SUPPORTED_BATTERY_SYMBOLS:
            kind = "battery"
            role_binding = None
        elif symbol in _SUPPORTED_MOTOR_SYMBOLS:
            kind = "motor"
            role_binding = None
        elif symbol in _SUPPORTED_SOLAR_CELL_SYMBOLS:
            kind = "solar_cell"
            role_binding = None
        else:
            role_binding = role_bindings.get(reference.casefold())
            if role_binding is None or role_binding.role != "capacitor":
                continue
            kind = "capacitor"

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
            )
        )
    return tuple(sorted(results, key=lambda item: (item.reference.casefold(), item.reference)))
