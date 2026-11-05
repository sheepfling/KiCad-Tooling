"""Review supported fitted two-pin thermocouples assigned to one schematic net."""

from __future__ import annotations

from .design_lint_two_pin_candidate_evidence import (
    TwoPinComponentFindingEvidence,
    TwoPinSameNetCandidate,
)
from .design_lint_types import Candidate
from .two_pin_components import TwoPinComponentOnSameNet


def two_pin_thermocouple_same_net_candidates(
    observations: tuple[TwoPinComponentOnSameNet, ...],
) -> tuple[Candidate, ...]:
    """Build REVIEW candidates for exact two-pin thermocouples sharing one net."""
    return tuple(
        TwoPinSameNetCandidate.from_source_evidence(
            TwoPinComponentFindingEvidence(item),
            subject=f"{item.reference}: both thermocouple leads share {item.net}",
            message=(
                "Both leads of this supported fitted two-pin thermocouple are assigned to the "
                "same native schematic net, so the net assignment shows no differential signal "
                "across its input leads. Review whether this is intentional or a connection is "
                "missing. This prompt does not establish temperature measurement, cold-junction "
                "compensation, sensor suitability, instrumentation grounding, polarity, footprint "
                "mapping, physical connectivity, or assembly state."
            ),
        )
        for item in observations
        if item.kind == "thermocouple"
    )
