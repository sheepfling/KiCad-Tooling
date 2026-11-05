"""Review supported fitted two-pin batteries whose terminals share one net."""

from __future__ import annotations

from .design_lint_two_pin_candidate_evidence import (
    TwoPinComponentFindingEvidence,
    TwoPinSameNetCandidate,
)
from .design_lint_types import Candidate
from .two_pin_components import TwoPinComponentOnSameNet


def two_pin_battery_same_net_candidates(
    observations: tuple[TwoPinComponentOnSameNet, ...],
) -> tuple[Candidate, ...]:
    """Build REVIEW candidates for exact supported batteries assigned to one net."""
    return tuple(
        TwoPinSameNetCandidate.from_source_evidence(
            TwoPinComponentFindingEvidence(item),
            subject=f"{item.reference}: both battery terminals share {item.net}",
            message=(
                "Both terminals of this supported fitted two-pin battery are assigned to the "
                "same native schematic net, so the net assignment shows no voltage difference "
                "across the source. Review whether the battery is intentionally bypassed or a "
                "power connection is missing. This prompt does not establish source behavior, "
                "polarity, footprint mapping, physical connectivity, or assembly state."
            ),
        )
        for item in observations
        if item.kind == "battery"
    )
