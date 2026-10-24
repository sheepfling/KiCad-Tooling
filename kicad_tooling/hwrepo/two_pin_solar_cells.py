"""Review supported fitted two-pin solar cells whose terminals share one net."""

from __future__ import annotations

from .design_lint_types import Candidate
from .two_pin_components import TwoPinComponentOnSameNet


def two_pin_solar_cell_same_net_candidates(
    observations: tuple[TwoPinComponentOnSameNet, ...],
) -> tuple[Candidate, ...]:
    """Build REVIEW candidates for exact solar cells assigned to one net."""
    return tuple(
        Candidate(
            rule_id="component.two_pin_solar_cell_same_net",
            subject=f"{item.reference}: both solar-cell terminals share {item.net}",
            message=(
                "Both terminals of this supported fitted two-pin solar cell are assigned to the "
                "same native schematic net, so the net assignment shows no voltage difference "
                "across the cell. Review whether a test short or measurement configuration is "
                "intentional or a connection is missing. This prompt does not establish cell "
                "output, polarity, illumination, footprint mapping, physical connectivity, or "
                "assembly state."
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
        if item.kind == "solar_cell"
    )
