"""Review supported fitted two-pin DC motors whose terminals share one net."""

from __future__ import annotations

from .design_lint_two_pin_candidate_evidence import (
    TwoPinComponentFindingEvidence,
    TwoPinSameNetCandidate,
)
from .design_lint_types import Candidate
from .two_pin_components import TwoPinComponentOnSameNet


def two_pin_motor_same_net_candidates(
    observations: tuple[TwoPinComponentOnSameNet, ...],
) -> tuple[Candidate, ...]:
    """Build REVIEW candidates for exact supported motors assigned to one net."""
    return tuple(
        TwoPinSameNetCandidate.from_source_evidence(
            TwoPinComponentFindingEvidence(item),
            subject=f"{item.reference}: both motor terminals share {item.net}",
            message=(
                "Both terminals of this supported fitted two-pin DC motor are assigned to the "
                "same native schematic net, so the net assignment shows no voltage difference "
                "across the motor. Review whether it is intentionally bypassed or a connection "
                "is missing. This prompt does not establish motor behavior, driver compatibility, "
                "footprint mapping, physical connectivity, or assembly state."
            ),
        )
        for item in observations
        if item.kind == "motor"
    )
