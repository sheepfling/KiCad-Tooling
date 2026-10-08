"""Find supported fitted two-pin components whose schematic pins share one net."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .models import NetlistContract

_SUPPORTED_DEVICE_SYMBOL = re.compile(
    r"^Device:(?P<kind>R|C|L|D|Fuse|Polyfuse|FerriteBead|Crystal)"
    r"(?:_(?P<variant>[A-Za-z0-9_]+))?$",
    re.IGNORECASE,
)
_SUPPORTED_SWITCH_SYMBOL = re.compile(r"^Switch:SW_SPST$", re.IGNORECASE)
_KIND_NAMES = {
    "r": "resistor",
    "c": "capacitor",
    "l": "inductor",
    "d": "diode",
    "fuse": "fuse",
    "polyfuse": "polyfuse",
    "ferritebead": "ferrite_bead",
    "crystal": "crystal",
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


def two_pin_components_on_same_net(
    observed: NetlistContract,
) -> tuple[TwoPinComponentOnSameNet, ...]:
    """Return bounded review candidates without deciding whether a short is intentional.

    Recognition requires an exact supported symbol identity, exactly two
    distinct native pin numbers, one unambiguous net per pin, and a fitted
    component. Supported identities are the listed ``Device`` families and
    ``Switch:SW_SPST``. Project-specific symbols and incomplete inventories
    are skipped.
    """
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
            kind = _KIND_NAMES[native_kind]
        elif _SUPPORTED_SWITCH_SYMBOL.fullmatch(symbol):
            kind = "switch"
        else:
            continue

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
        pin_numbers = tuple(sorted(raw_pin_numbers, key=str.casefold))
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
            )
        )
    return tuple(sorted(results, key=lambda item: (item.reference.casefold(), item.reference)))
