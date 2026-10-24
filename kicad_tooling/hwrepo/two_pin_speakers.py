"""Review supported fitted two-pin speakers whose terminals share one net."""

from __future__ import annotations

from .design_lint_types import Candidate
from .two_pin_components import TwoPinComponentOnSameNet


def two_pin_speaker_same_net_candidates(
    observations: tuple[TwoPinComponentOnSameNet, ...],
) -> tuple[Candidate, ...]:
    """Build REVIEW candidates for exact supported speakers assigned to one net."""
    return tuple(
        Candidate(
            rule_id="component.two_pin_speaker_same_net",
            subject=f"{item.reference}: both speaker terminals share {item.net}",
            message=(
                "Both terminals of this supported fitted two-pin speaker are assigned to the "
                "same native schematic net, so the net assignment provides no voltage "
                "difference across the speaker. Review whether it is intentionally bypassed or "
                "a connection is missing. This prompt does not establish speaker behavior, "
                "amplifier compatibility, physical connectivity, or assembly state."
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
        if item.kind == "speaker"
    )
