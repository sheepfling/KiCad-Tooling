"""Can termination heuristics for deterministic KiCad bus analysis."""

from __future__ import annotations

from dataclasses import dataclass

from .bus_signal_roles import can_function_role
from .models import NetlistContract
from .resistor_paths import direct_resistors


@dataclass(frozen=True)
class CanTerminationGap:
    high_net: str
    low_net: str
    high_pins: tuple[str, ...]
    low_pins: tuple[str, ...]


def can_buses_without_local_termination(
    observed: NetlistContract,
) -> tuple[CanTerminationGap, ...]:
    """Find named CANH/CANL pairs without a visible direct 108–132 Ω resistor."""
    pin_nets: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin, set()).add(net)

    signal_pins: dict[str, dict[str, set[str]]] = {}
    for pin, function in observed.pin_functions.items():
        role = can_function_role(function)
        if role is None:
            continue
        reference = pin.rsplit(".", 1)[0]
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

    terminated_pairs: set[tuple[str, str]] = set()
    for resistor in direct_resistors(observed):
        if 108 <= resistor.resistance_ohms <= 132:
            terminated_pairs.add((resistor.first_net, resistor.second_net))

    gaps: list[CanTerminationGap] = []
    for (high_net, low_net), evidence in sorted(buses.items()):
        if tuple(sorted((high_net, low_net))) in terminated_pairs:
            continue
        gaps.append(
            CanTerminationGap(
                high_net=high_net,
                low_net=low_net,
                high_pins=tuple(sorted(evidence["CANH"])),
                low_pins=tuple(sorted(evidence["CANL"])),
            )
        )
    return tuple(gaps)
