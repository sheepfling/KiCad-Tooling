"""Typed CAN termination sources and their stable finding projection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from .can_termination_heuristics import CanTerminationExcess, CanTerminationGap
from .design_lint_types import Candidate, CandidateEvidenceProjection

CanTerminationCandidateEvidence: TypeAlias = CanTerminationGap | CanTerminationExcess


def project_can_termination_evidence(
    source: CanTerminationCandidateEvidence,
) -> CandidateEvidenceProjection:
    """Project a CAN termination scan record to the existing report fields."""
    if isinstance(source, CanTerminationGap):
        return CandidateEvidenceProjection(
            rule_id="bus.can_missing_termination",
            evidence={
                "CANH": (source.high_net,),
                "CANL": (source.low_net,),
                "pins": (*source.high_pins, *source.low_pins),
                "termination": (),
            },
        )
    terminations = tuple(
        f"{item.reference}={item.resistance_ohms:g} Ω" for item in source.terminations
    )
    return CandidateEvidenceProjection(
        rule_id="bus.can_excess_termination",
        evidence={
            "CANH": (source.high_net,),
            "CANL": (source.low_net,),
            "pins": (*source.high_pins, *source.low_pins),
            "terminations": terminations,
        },
    )


@dataclass(frozen=True, slots=True)
class CanTerminationCandidate(Candidate):
    """Internal CAN termination finding retaining its heuristic source record."""

    source_evidence: CanTerminationCandidateEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: CanTerminationCandidateEvidence,
        *,
        subject: str,
        message: str,
    ) -> CanTerminationCandidate:
        projection = project_can_termination_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_can_termination_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id:
            raise ValueError("CAN termination candidate rule must match its source evidence")
        if self.evidence != projection.evidence:
            raise ValueError("CAN termination evidence must match its typed source projection")
