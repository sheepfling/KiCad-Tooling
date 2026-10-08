"""Find fitted supported two-pin diodes whose schematic pins share one net."""

from __future__ import annotations

from .models import NetlistContract
from .two_pin_components import TwoPinComponentOnSameNet, two_pin_components_on_same_net


def two_pin_diodes_on_same_net(
    observed: NetlistContract,
) -> tuple[TwoPinComponentOnSameNet, ...]:
    """Return only exact ``Device:D`` family candidates with both pins on one net."""
    return tuple(item for item in two_pin_components_on_same_net(observed) if item.kind == "diode")
