"""Connector-specific ordering for native peer-pin assignments."""

from __future__ import annotations

from .netlist_pin_assignments import NetlistPinNetIndex


def connector_footprint_peer_pin_assignments(
    pin_nets: NetlistPinNetIndex,
    pin: str,
) -> tuple[str, ...]:
    """Return sorted exact net assignments for one native pin reference."""
    return tuple(
        sorted(
            pin_nets.get(pin.casefold(), frozenset()),
            key=lambda item: (item.casefold(), item),
        )
    )
