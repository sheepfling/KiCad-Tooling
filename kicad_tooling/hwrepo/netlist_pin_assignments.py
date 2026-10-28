"""Shared indexes for native netlist pin assignments."""

from __future__ import annotations

from .casefold_mapping_lookup import lookup_unique_casefold
from .models import NetlistContract


def netlist_pin_net_index(observed: NetlistContract) -> dict[str, set[str]]:
    """Return each case-folded pin's exact assigned schematic net names."""
    by_pin: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            by_pin.setdefault(pin.casefold(), set()).add(net)
    return by_pin


def netlist_pin_inventory_contains(observed: NetlistContract, pin: str) -> bool | None:
    """Check a reference.pin against native inventory; None means inventory is absent."""
    reference, separator, number = pin.rpartition(".")
    if not separator:
        return False
    inventory = lookup_unique_casefold(observed.component_pin_numbers, reference)
    if inventory is None:
        return None
    return any(str(candidate).casefold() == number.casefold() for candidate in inventory)
