"""Review supported fitted two-pin batteries whose terminals share one net."""

from __future__ import annotations

from .design_lint_types import Candidate
from .two_pin_components import TwoPinComponentOnSameNet


def two_pin_battery_same_net_candidates(
    observations: tuple[TwoPinComponentOnSameNet, ...],
) -> tuple[Candidate, ...]:
    """Build REVIEW candidates for exact supported batteries assigned to one net."""
    return tuple(
        Candidate(
            rule_id="component.two_pin_battery_same_net",
            subject=f"{item.reference}: both battery terminals share {item.net}",
            message=(
                "Both terminals of this supported fitted two-pin battery are assigned to the "
                "same native schematic net, so the net assignment shows no voltage difference "
                "across the source. Review whether the battery is intentionally bypassed or a "
                "power connection is missing. This prompt does not establish source behavior, "
                "polarity, footprint mapping, physical connectivity, or assembly state."
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
        if item.kind == "battery"
    )
