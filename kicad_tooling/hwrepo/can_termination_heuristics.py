"""Can termination heuristics for deterministic KiCad bus analysis."""

from __future__ import annotations

from dataclasses import dataclass

from .bus_signal_roles import can_function_role
from .models import NetlistContract
from .resistor_paths import DirectResistor, direct_resistors

CAN_TERMINATION_MIN_OHMS = 108.0
CAN_TERMINATION_MAX_OHMS = 132.0


@dataclass(frozen=True, slots=True)
class CanSignalPair:
    high_net: str
    low_net: str
    high_pins: tuple[str, ...]
    low_pins: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CanTerminationGap:
    high_net: str
    low_net: str
    high_pins: tuple[str, ...]
    low_pins: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CanTerminationExcess:
    high_net: str
    low_net: str
    high_pins: tuple[str, ...]
    low_pins: tuple[str, ...]
    terminations: tuple[DirectResistor, ...]


def recognized_can_signal_pairs(observed: NetlistContract) -> tuple[CanSignalPair, ...]:
    """Return fitted, uniquely assigned CANH/CANL pairs on distinct nets."""
    pin_nets: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin, set()).add(net)

    signal_pins: dict[str, dict[str, set[str]]] = {}
    dnp = {reference.casefold() for reference in observed.dnp_components}
    for pin, function in observed.pin_functions.items():
        role = can_function_role(function)
        reference = pin.rsplit(".", 1)[0]
        if role is None or reference.casefold() in dnp:
            continue
        signal_pins.setdefault(reference, {}).setdefault(role, set()).add(pin)

    buses: dict[tuple[str, str], dict[str, set[str]]] = {}
    for roles in signal_pins.values():
        if not {"CANH", "CANL"}.issubset(roles):
            continue
        high_assignments = {
            (pin, next(iter(nets)))
            for pin in roles["CANH"]
            if len(nets := pin_nets.get(pin, set())) == 1
        }
        low_assignments = {
            (pin, next(iter(nets)))
            for pin in roles["CANL"]
            if len(nets := pin_nets.get(pin, set())) == 1
        }
        for high_pin, high_net in high_assignments:
            for low_pin, low_net in low_assignments:
                if high_net == low_net:
                    continue
                evidence = buses.setdefault((high_net, low_net), {"CANH": set(), "CANL": set()})
                evidence["CANH"].add(high_pin)
                evidence["CANL"].add(low_pin)

    return tuple(
        CanSignalPair(
            high_net=high_net,
            low_net=low_net,
            high_pins=tuple(sorted(evidence["CANH"])),
            low_pins=tuple(sorted(evidence["CANL"])),
        )
        for (high_net, low_net), evidence in sorted(buses.items())
    )


def can_buses_without_local_termination(
    observed: NetlistContract,
) -> tuple[CanTerminationGap, ...]:
    """Find named CANH/CANL pairs without a visible direct 108–132 Ω resistor."""
    terminated_pairs: set[tuple[str, str]] = set()
    for resistor in direct_resistors(observed):
        if CAN_TERMINATION_MIN_OHMS <= resistor.resistance_ohms <= CAN_TERMINATION_MAX_OHMS:
            terminated_pairs.add((resistor.first_net, resistor.second_net))

    gaps: list[CanTerminationGap] = []
    for bus in recognized_can_signal_pairs(observed):
        high_net, low_net = bus.high_net, bus.low_net
        if tuple(sorted((high_net, low_net))) in terminated_pairs:
            continue
        gaps.append(
            CanTerminationGap(
                high_net=high_net,
                low_net=low_net,
                high_pins=bus.high_pins,
                low_pins=bus.low_pins,
            )
        )
    return tuple(gaps)


def can_buses_with_excessive_local_termination(
    observed: NetlistContract,
) -> tuple[CanTerminationExcess, ...]:
    """Find a recognized CAN pair with more than two fitted direct 108–132 Ω resistors."""
    by_pair: dict[tuple[str, str], list[DirectResistor]] = {}
    for resistor in direct_resistors(observed):
        if CAN_TERMINATION_MIN_OHMS <= resistor.resistance_ohms <= CAN_TERMINATION_MAX_OHMS:
            by_pair.setdefault((resistor.first_net, resistor.second_net), []).append(resistor)

    excesses: list[CanTerminationExcess] = []
    reviewed_pairs: set[tuple[str, str]] = set()
    for bus in recognized_can_signal_pairs(observed):
        pair = (bus.high_net, bus.low_net)
        if pair[0] > pair[1]:
            pair = (pair[1], pair[0])
        if pair in reviewed_pairs:
            continue
        terminations = tuple(by_pair.get(pair, []))
        if len(terminations) <= 2:
            continue
        reviewed_pairs.add(pair)
        excesses.append(
            CanTerminationExcess(
                high_net=bus.high_net,
                low_net=bus.low_net,
                high_pins=bus.high_pins,
                low_pins=bus.low_pins,
                terminations=terminations,
            )
        )
    return tuple(excesses)
