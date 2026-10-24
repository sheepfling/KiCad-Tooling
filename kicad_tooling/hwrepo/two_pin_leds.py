"""Review supported two-pin LEDs whose schematic terminals share one net."""

from __future__ import annotations

from .design_lint_types import Candidate
from .two_pin_components import TwoPinComponentOnSameNet


def two_pin_led_same_net_candidates(
    observations: tuple[TwoPinComponentOnSameNet, ...],
) -> tuple[Candidate, ...]:
    """Build REVIEW candidates for exact supported LEDs assigned to one net."""
    return tuple(
        Candidate(
            rule_id="component.two_pin_led_same_net",
            subject=f"{item.reference}: both LED terminals share {item.net}",
            message=(
                "Both terminals of this supported fitted two-pin LED are assigned to the same "
                "native schematic net, so this net assignment provides no voltage difference "
                "across the LED. Review whether the short is intentional or a connection is "
                "missing. This prompt does not establish LED behavior, current, physical board "
                "connectivity, or assembly state."
            ),
            evidence={
                "symbol": (item.symbol,),
                "value": (item.value,),
                "net": (item.net,),
                "pin_assignments": tuple(
                    f"{item.reference}.{number} -> {item.net}" for number in item.pin_numbers
                ),
            },
        )
        for item in observations
        if item.kind == "led"
    )
