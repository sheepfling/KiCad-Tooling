"""Typed CAN peer sources and their stable finding projection."""

from __future__ import annotations

from dataclasses import dataclass

from .can_peer_heuristics import CanPeerAssignmentDivergence
from .design_lint_types import Candidate, CandidateEvidenceProjection


def project_can_peer_evidence(source: CanPeerAssignmentDivergence) -> CandidateEvidenceProjection:
    """Project one typed peer-assignment divergence to the established report fields."""
    return CandidateEvidenceProjection(
        rule_id="bus.can_peer_assignment_divergence",
        evidence={
            "shared_role": (source.shared_role,),
            "shared_net": (source.shared_net,),
            "complementary_role": (source.complementary_role,),
            "complementary_nets": source.complementary_nets,
            "participants": source.participants,
        },
    )


@dataclass(frozen=True, slots=True)
class CanPeerCandidate(Candidate):
    """Internal CAN peer finding retaining its typed scan record."""

    source_evidence: CanPeerAssignmentDivergence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: CanPeerAssignmentDivergence,
        *,
        subject: str,
        message: str,
    ) -> CanPeerCandidate:
        projection = project_can_peer_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_can_peer_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id:
            raise ValueError("CAN peer candidate rule must match its source evidence")
        if self.evidence != projection.evidence:
            raise ValueError("CAN peer evidence must match its typed source projection")
