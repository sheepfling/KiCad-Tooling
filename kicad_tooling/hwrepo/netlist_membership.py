"""Describe exact pin membership for one authored net without inferring intent."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .models import NetlistContract

PinStatus = Literal[
    "MATCH", "DIFFERENT", "MISSING", "UNCONNECTED", "AMBIGUOUS", "UNDECLARED", "UNREVIEWED"
]


@dataclass(frozen=True)
class PinMembership:
    pin: str
    expected_net: str | None
    observed_nets: tuple[str, ...]
    status: PinStatus


def net_pin_membership(
    net: str, declared: tuple[str, ...], observed: NetlistContract | None
) -> tuple[PinMembership, ...]:
    """Retain unmatched and extra pins separately for a selected exact net."""
    if observed is None:
        return tuple(PinMembership(pin, net, (), "UNREVIEWED") for pin in declared)
    locations: dict[str, set[str]] = {}
    unconnected: set[str] = set()
    for name, pins in observed.nets.items():
        for pin in pins:
            locations.setdefault(pin.casefold(), set()).add(name)
    for pins in observed.unconnected_nets.values():
        unconnected.update(pin.casefold() for pin in pins)
    rows: list[PinMembership] = []
    for pin in declared:
        pin_key = pin.casefold()
        found = tuple(sorted(locations.get(pin_key, ())))
        status: PinStatus = (
            "AMBIGUOUS"
            if len(found) > 1
            else "UNCONNECTED"
            if pin_key in unconnected
            else "MISSING"
            if not found
            else "MATCH"
            if found == (net,)
            else "DIFFERENT"
        )
        rows.append(PinMembership(pin, net, found, status))
    declared_keys = {pin.casefold() for pin in declared}
    extra_by_key: dict[str, str] = {}
    for pin in sorted(observed.nets.get(net, ()), key=lambda value: (value.casefold(), value)):
        if pin.casefold() not in declared_keys:
            extra_by_key.setdefault(pin.casefold(), pin)
    for pin in extra_by_key.values():
        rows.append(PinMembership(pin, None, (net,), "UNDECLARED"))
    return tuple(rows)
