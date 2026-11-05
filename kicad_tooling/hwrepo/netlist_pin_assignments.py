"""Shared indexes for native netlist pin assignments."""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from types import MappingProxyType
from typing import TypeAlias

from .casefold_mapping_lookup import lookup_unique_casefold
from .netlist_contract_models import NetlistContract

NetlistPinNetIndex: TypeAlias = Mapping[str, AbstractSet[str]]
NetlistPinNetAssignmentsByPin: TypeAlias = Mapping[str, tuple[str, ...]]


def netlist_pin_net_index(observed: NetlistContract) -> NetlistPinNetIndex:
    """Return a read-only case-folded index of exact pin-to-net assignments."""
    return MappingProxyType(
        {pin: frozenset(nets) for pin, nets in netlist_pin_net_assignments(observed).items()}
    )


def netlist_pin_net_assignments(observed: NetlistContract) -> NetlistPinNetAssignmentsByPin:
    """Return each pin's native net occurrences in source iteration order."""
    by_pin: dict[str, list[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            by_pin.setdefault(pin.casefold(), []).append(net)
    return MappingProxyType({pin: tuple(nets) for pin, nets in by_pin.items()})


def netlist_pin_inventory_contains(observed: NetlistContract, pin: str) -> bool | None:
    """Check a reference.pin against native inventory; None means inventory is absent."""
    reference, separator, number = pin.rpartition(".")
    if not separator:
        return False
    inventory = lookup_unique_casefold(observed.component_pin_numbers, reference)
    if inventory is None:
        return None
    return any(str(candidate).casefold() == number.casefold() for candidate in inventory)
