"""Resistor paths for deterministic KiCad bus analysis."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .connector_identity import power_function_key
from .models import NetlistContract

RESISTOR_REFERENCE_PATTERN = re.compile(r"^R[A-Z]*[0-9]+$", re.IGNORECASE)

_ENGINEERING_VALUE = re.compile(r"^(?P<whole>[0-9]+)(?P<unit>[krm])(?P<fraction>[0-9]+)$")

_STANDARD_VALUE = re.compile(r"^(?P<amount>[0-9]+(?:\.[0-9]+)?)(?P<unit>[krm]?)$")


@dataclass(frozen=True)
class VisiblePullupPath:
    references: tuple[str, ...]
    resistance_ohms: float
    rail_net: str


@dataclass(frozen=True)
class DirectResistor:
    reference: str
    resistance_ohms: float
    first_net: str
    second_net: str


def resistance_ohms(value: str) -> float | None:
    compact = value.strip().replace("Ω", "").replace("Ω", "").casefold()
    compact = re.sub(r"ohms?$", "", compact).replace(" ", "")
    engineering = _ENGINEERING_VALUE.fullmatch(compact)
    if engineering is not None:
        amount = float(f"{engineering['whole']}.{engineering['fraction']}")
        unit = engineering["unit"]
    else:
        standard = _STANDARD_VALUE.fullmatch(compact)
        if standard is None:
            return None
        amount = float(standard["amount"])
        unit = standard["unit"]
    scale = {"": 1.0, "r": 1.0, "k": 1_000.0, "m": 1_000_000.0}[unit]
    return amount * scale


def direct_resistors(observed: NetlistContract) -> tuple[DirectResistor, ...]:
    """Return fitted, conventional two-terminal resistors with two unique net assignments."""
    pin_nets: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin, set()).add(net)
    component_pins: dict[str, set[str]] = {}
    for pin in set(observed.pin_functions) | set(pin_nets):
        component_pins.setdefault(pin.rsplit(".", 1)[0], set()).add(pin)
    dnp = {reference.casefold() for reference in observed.dnp_components}
    resistors: list[DirectResistor] = []
    for reference, component in observed.components.items():
        if reference.casefold() in dnp or RESISTOR_REFERENCE_PATTERN.fullmatch(reference) is None:
            continue
        resistance = resistance_ohms(component.value)
        if resistance is None or resistance <= 0:
            continue
        pins = component_pins.get(reference, set())
        known_pin_numbers = observed.component_pin_numbers.get(reference)
        if len(pins) != 2 or (known_pin_numbers is not None and len(known_pin_numbers) != 2):
            continue
        terminals = [pin_nets.get(pin, set()) for pin in pins]
        if any(len(nets) != 1 for nets in terminals):
            continue
        first_net, second_net = sorted(next(iter(nets)) for nets in terminals)
        if first_net == second_net:
            continue
        resistors.append(
            DirectResistor(
                reference=reference,
                resistance_ohms=resistance,
                first_net=first_net,
                second_net=second_net,
            )
        )
    return tuple(
        sorted(resistors, key=lambda item: (item.first_net, item.second_net, item.reference))
    )


def positive_power_nets(observed: NetlistContract) -> set[str]:
    """Return only the positive rails identified by a bounded native name/function map."""
    positive_rails = {
        net
        for net, pins in observed.nets.items()
        if power_function_key(net) is not None
        or any(power_function_key(observed.pin_functions.get(pin, "")) for pin in pins)
    }
    return positive_rails


def positive_power_net_families(observed: NetlistContract) -> dict[str, str]:
    """Return recognized positive nets with one stable, narrow naming family."""
    families: dict[str, str] = {}
    for net, pins in observed.nets.items():
        family = power_function_key(net)
        if family is None:
            pin_families = {
                key
                for pin in pins
                if (key := power_function_key(observed.pin_functions.get(pin, ""))) is not None
            }
            if len(pin_families) == 1:
                family = next(iter(pin_families))
        if family is not None:
            families[net] = family
    return families


def visible_resistor_pullups(observed: NetlistContract) -> dict[str, list[VisiblePullupPath]]:
    """Find direct or unbranched fitted resistor chains from a signal net to a named rail."""
    positive_rails = positive_power_nets(observed)
    resistors = {
        item.reference: item
        for item in direct_resistors(observed)
        if 1_000 <= item.resistance_ohms <= 100_000
    }
    by_net: dict[str, list[DirectResistor]] = {}
    for resistor in resistors.values():
        by_net.setdefault(resistor.first_net, []).append(resistor)
        by_net.setdefault(resistor.second_net, []).append(resistor)

    pullups: dict[str, dict[tuple[tuple[str, ...], str], VisiblePullupPath]] = {}

    def visit(
        start_net: str,
        current_net: str,
        references: tuple[str, ...],
        resistance_ohms: float,
        visited: frozenset[str],
    ) -> None:
        for resistor in by_net.get(current_net, ()):
            if resistor.reference in visited:
                continue
            next_net = (
                resistor.second_net if resistor.first_net == current_net else resistor.first_net
            )
            path_references = (*references, resistor.reference)
            path_resistance = resistance_ohms + resistor.resistance_ohms
            if next_net in positive_rails:
                if 1_000 <= path_resistance <= 100_000:
                    path = VisiblePullupPath(
                        references=path_references,
                        resistance_ohms=path_resistance,
                        rail_net=next_net,
                    )
                    pullups.setdefault(start_net, {})[(path_references, next_net)] = path
                continue
            if next_net == start_net:
                continue

            # Only traverse a series junction with exactly two assigned pins,
            # both belonging to recognized fitted two-terminal resistors.
            junction_pins = tuple(observed.nets.get(next_net, ()))
            if len(junction_pins) != 2 or len(set(junction_pins)) != 2:
                continue
            junction_references = {pin.rsplit(".", 1)[0] for pin in junction_pins}
            if len(junction_references) != 2 or resistor.reference not in junction_references:
                continue
            next_references = junction_references - {resistor.reference}
            if len(next_references) != 1:
                continue
            next_reference = next(iter(next_references))
            next_resistor = resistors.get(next_reference)
            if next_resistor is None or next_net not in {
                next_resistor.first_net,
                next_resistor.second_net,
            }:
                continue
            visit(
                start_net,
                next_net,
                path_references,
                path_resistance,
                visited | {resistor.reference},
            )

    for start_net in sorted(by_net):
        if start_net in positive_rails:
            continue
        visit(start_net, start_net, (), 0.0, frozenset())

    return {
        net: sorted(
            paths.values(),
            key=lambda item: (item.rail_net, item.references, item.resistance_ohms),
        )
        for net, paths in sorted(pullups.items())
    }
