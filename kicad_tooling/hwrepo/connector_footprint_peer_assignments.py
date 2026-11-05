"""Canonical exact-net assignments for connector footprint-peer pins."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from .netlist_contract_models import NetlistContract


def connector_footprint_peer_pin_net_map(
    observed: NetlistContract,
) -> Mapping[str, frozenset[str]]:
    """Index exact net membership by case-folded native pin reference."""
    mutable: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            mutable.setdefault(pin.casefold(), set()).add(net)
    return MappingProxyType({pin: frozenset(nets) for pin, nets in mutable.items()})


def connector_footprint_peer_pin_assignments(
    pin_nets: Mapping[str, frozenset[str]],
    pin: str,
) -> tuple[str, ...]:
    """Return sorted exact net assignments for one native pin reference."""
    return tuple(
        sorted(
            pin_nets.get(pin.casefold(), frozenset()),
            key=lambda item: (item.casefold(), item),
        )
    )
