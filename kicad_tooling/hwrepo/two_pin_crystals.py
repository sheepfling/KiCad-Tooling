"""Find fitted supported two-pin crystals whose schematic pins share one net."""

from __future__ import annotations

from .models import NetlistContract
from .two_pin_components import TwoPinComponentOnSameNet, two_pin_components_on_same_net


def two_pin_crystals_on_same_net(
    observed: NetlistContract,
) -> tuple[TwoPinComponentOnSameNet, ...]:
    """Return exact ``Device:Crystal`` family candidates with both pins on one net."""
    return tuple(
        item for item in two_pin_components_on_same_net(observed) if item.kind == "crystal"
    )
