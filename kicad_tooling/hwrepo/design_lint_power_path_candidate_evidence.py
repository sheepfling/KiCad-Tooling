"""Typed source evidence and projection for mapped power-path findings."""

from __future__ import annotations

from dataclasses import dataclass

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .model_primitives import Digest
from .power_paths import PowerPathMismatch

RULE_ID: DesignLintRuleId = "power.mapped_series_path_mismatch"


@dataclass(frozen=True, slots=True)
class PowerPathFindingEvidence:
    """One named native mismatch bound to the project-authored path map."""

    mismatch: PowerPathMismatch
    map_sha256: Digest


def project_power_path_evidence(
    source: PowerPathFindingEvidence,
) -> CandidateEvidenceProjection:
    """Project the named mismatch and map identity to existing report fields."""
    mismatch = source.mismatch
    return CandidateEvidenceProjection(
        rule_id=RULE_ID,
        evidence={
            "path": (mismatch.path_id,),
            "basis": (mismatch.basis,),
            "start_endpoint": (f"{mismatch.start_pin} on {mismatch.start_net}",),
            "end_endpoint": (f"{mismatch.end_pin} on {mismatch.end_net}",),
            "mapped_elements": mismatch.elements,
            "map_sha256": (source.map_sha256,),
            "issues": mismatch.issues,
        },
    )


@dataclass(frozen=True, slots=True)
class PowerPathCandidate(Candidate):
    """Power-path finding retaining its measured mismatch and map identity."""

    source_evidence: PowerPathFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: PowerPathFindingEvidence,
        *,
        subject: str,
        message: str,
    ) -> PowerPathCandidate:
        projection = project_power_path_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_power_path_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("Power-path evidence must match its source projection")
