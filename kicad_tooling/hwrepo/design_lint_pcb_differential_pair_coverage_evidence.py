"""Typed evidence and report projection for differential-pair DRC coverage gaps."""

from __future__ import annotations

from dataclasses import dataclass

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .pcb_drc_models import (
    PcbDifferentialPairRuleCoverageEntry,
    PcbDifferentialPairRuleCoverageReport,
)

RULE_ID: DesignLintRuleId = "pcb.differential_pair_rule_coverage"


@dataclass(frozen=True, slots=True)
class PcbDifferentialPairCoverageFindingEvidence:
    """An incomplete pair entry with the full source-bound coverage report."""

    report: PcbDifferentialPairRuleCoverageReport
    entry: PcbDifferentialPairRuleCoverageEntry

    def __post_init__(self) -> None:
        if self.report.status != "INCOMPLETE":
            raise ValueError("Differential-pair finding evidence requires INCOMPLETE report")
        if self.entry.status != "INCOMPLETE" or self.entry not in self.report.entries:
            raise ValueError("Differential-pair finding must belong to incomplete report entries")


def project_pcb_differential_pair_coverage_evidence(
    source: PcbDifferentialPairCoverageFindingEvidence,
) -> CandidateEvidenceProjection:
    """Keep the existing wire fields for incomplete pair coverage findings."""
    entry = source.entry
    constraint_evidence = tuple(
        f"{item.constraint}: {item.status}" + ("" if item.issue is None else f" ({item.issue})")
        for item in entry.constraints
        if item.status != "COVERED"
    )
    return CandidateEvidenceProjection(
        rule_id=RULE_ID,
        evidence={
            "positive_net": (entry.positive_net,),
            "negative_net": (entry.negative_net,),
            "pair_selector": (entry.pair_selector,),
            "basis": (entry.basis,),
            "constraints": constraint_evidence,
            "issues": entry.issues,
        },
    )


@dataclass(frozen=True, slots=True)
class PcbDifferentialPairCoverageCandidate(Candidate):
    """Incomplete DRC coverage finding retaining its authored and native route."""

    source_evidence: PcbDifferentialPairCoverageFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: PcbDifferentialPairCoverageFindingEvidence,
        *,
        subject: str,
        message: str,
    ) -> PcbDifferentialPairCoverageCandidate:
        projection = project_pcb_differential_pair_coverage_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_pcb_differential_pair_coverage_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id:
            raise ValueError("Differential-pair coverage rule must match its source evidence")
        if self.evidence != projection.evidence:
            raise ValueError("Differential-pair coverage evidence must match its projection")
