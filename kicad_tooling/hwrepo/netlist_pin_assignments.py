"""Shared indexes for native netlist pin assignments."""

from __future__ import annotations

from .models import NetlistContract


def netlist_pin_net_index(observed: NetlistContract) -> dict[str, set[str]]:
    """Return each case-folded pin's exact assigned schematic net names."""
    by_pin: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            by_pin.setdefault(pin.casefold(), set()).add(net)
    return by_pin
