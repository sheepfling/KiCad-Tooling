"""Find fitted supported two-pin ferrite beads whose pins share one net."""

from __future__ import annotations

from .models import NetlistContract
from .two_pin_components import TwoPinComponentOnSameNet, two_pin_components_on_same_net


def two_pin_ferrites_on_same_net(
    observed: NetlistContract,
) -> tuple[TwoPinComponentOnSameNet, ...]:
    """Return exact ``Device:FerriteBead`` family review candidates."""
    return tuple(
        item for item in two_pin_components_on_same_net(observed) if item.kind == "ferrite_bead"
    )
