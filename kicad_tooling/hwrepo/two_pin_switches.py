"""Find supported fitted two-pin SPST switches whose schematic pins share one net."""

from __future__ import annotations

from .models import NetlistContract
from .two_pin_components import TwoPinComponentOnSameNet, two_pin_components_on_same_net


def two_pin_switches_on_same_net(
    observed: NetlistContract,
) -> tuple[TwoPinComponentOnSameNet, ...]:
    """Return review candidates only for the exact native ``Switch:SW_SPST`` identity."""
    return tuple(item for item in two_pin_components_on_same_net(observed) if item.kind == "switch")
