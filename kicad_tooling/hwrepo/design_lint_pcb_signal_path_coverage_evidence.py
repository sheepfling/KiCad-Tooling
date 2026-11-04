"""Typed evidence and report projection for signal-path DRC coverage gaps."""

from __future__ import annotations

from dataclasses import dataclass

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .pcb_drc_models import PcbSignalPathRuleCoverageEntry, PcbSignalPathRuleCoverageReport

RULE_ID: DesignLintRuleId = "pcb.signal_path_rule_coverage"


@dataclass(frozen=True, slots=True)
class PcbSignalPathCoverageFindingEvidence:
    """An incomplete path or bundle entry with its source-bound DRC report."""

    report: PcbSignalPathRuleCoverageReport
    entry: PcbSignalPathRuleCoverageEntry

    def __post_init__(self) -> None:
        if self.report.status != "INCOMPLETE":
            raise ValueError("Signal-path finding evidence requires INCOMPLETE report")
        if self.entry.status != "INCOMPLETE" or self.entry not in self.report.entries:
            raise ValueError("Signal-path finding must belong to incomplete report entries")


def project_pcb_signal_path_coverage_evidence(
    source: PcbSignalPathCoverageFindingEvidence,
) -> CandidateEvidenceProjection:
    """Keep the existing wire fields for incomplete signal-path coverage findings."""
    entry = source.entry
    constraint_evidence = tuple(
        f"{item.constraint}: {item.status}" + ("" if item.issue is None else f" ({item.issue})")
        for item in entry.constraints
        if item.status != "COVERED"
    )
    return CandidateEvidenceProjection(
        rule_id=RULE_ID,
        evidence={
            "basis": (entry.basis,),
            "constraints": constraint_evidence,
            "issues": entry.issues,
            "path_ids": entry.path_ids,
        },
    )


@dataclass(frozen=True, slots=True)
class PcbSignalPathCoverageCandidate(Candidate):
    """Incomplete DRC coverage finding retaining its authored and native route."""

    source_evidence: PcbSignalPathCoverageFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: PcbSignalPathCoverageFindingEvidence,
        *,
        subject: str,
        message: str,
    ) -> PcbSignalPathCoverageCandidate:
        projection = project_pcb_signal_path_coverage_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_pcb_signal_path_coverage_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id:
            raise ValueError("Signal-path coverage rule must match its source evidence")
        if self.evidence != projection.evidence:
            raise ValueError("Signal-path coverage evidence must match its projection")
