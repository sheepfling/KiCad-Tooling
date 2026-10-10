"""Detect unassigned named return pins on fitted non-connector components."""

from __future__ import annotations

from .component_pin_patterns import UnconnectedNamedComponentPin, unconnected_named_component_pins
from .models import NetlistContract


def unconnected_component_return_pins(
    observed: NetlistContract,
    declared_references: tuple[str, ...] = (),
) -> tuple[UnconnectedNamedComponentPin, ...]:
    """Find named return pins that have no net assignment."""
    return tuple(
        pin
        for pin in unconnected_named_component_pins(observed, declared_references)
        if pin.category == "return"
    )
