"""Find fitted supported two-pin fuses whose schematic pins share one net."""

from __future__ import annotations

from .models import NetlistContract
from .two_pin_components import TwoPinComponentOnSameNet, two_pin_components_on_same_net


def two_pin_fuses_on_same_net(
    observed: NetlistContract,
) -> tuple[TwoPinComponentOnSameNet, ...]:
    """Return exact ``Device:Fuse`` and ``Device:Polyfuse`` review candidates."""
    return tuple(
        item
        for item in two_pin_components_on_same_net(observed)
        if item.kind in {"fuse", "polyfuse"}
    )
