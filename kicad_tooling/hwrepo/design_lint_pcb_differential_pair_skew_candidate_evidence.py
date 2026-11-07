"""Finding evidence for measured differential-pair route-skew review."""

from __future__ import annotations

from dataclasses import dataclass

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .pcb_differential_pair_skew_models import (
    PcbDifferentialPairRouteSkewEntry,
    PcbDifferentialPairRouteSkewReport,
)

RULE_ID: DesignLintRuleId = "pcb.differential_pair_route_skew"


@dataclass(frozen=True, slots=True)
class PcbDifferentialPairRouteSkewFindingEvidence:
    """One out-of-limit or unmeasurable bundle with its source-bound route report."""

    report: PcbDifferentialPairRouteSkewReport
    entry: PcbDifferentialPairRouteSkewEntry

    def __post_init__(self) -> None:
        if self.report.status != "INCOMPLETE":
            raise ValueError("Route-skew finding evidence requires an incomplete report")
        if self.entry.status == "WITHIN_LIMIT" or self.entry not in self.report.entries:
            raise ValueError("Route-skew finding must belong to an incomplete bundle entry")


def project_differential_pair_route_skew_evidence(
    source: PcbDifferentialPairRouteSkewFindingEvidence,
) -> CandidateEvidenceProjection:
    """Project the measured bundle and exact routes into stable finding evidence."""
    entry = source.entry
    paths = tuple(
        f"{item.path_id}: {item.net} {item.from_pad} to {item.to_pad}; "
        f"{item.status}; length {item.length_nm if item.length_nm is not None else 'unavailable'} nm"
        + (f"; issue: {item.issue}" if item.issue is not None else "")
        for item in entry.paths
    )
    measured = "unavailable" if entry.measured_skew_nm is None else str(entry.measured_skew_nm)
    return CandidateEvidenceProjection(
        rule_id=RULE_ID,
        evidence={
            "bundle_id": (entry.bundle_id,),
            "basis": ("Project-authored exact endpoints and maximum skew",),
            "maximum_skew_nm": (str(entry.max_skew_nm),),
            "measured_skew_nm": (measured,),
            "paths": paths,
            "issues": () if entry.issue is None else (entry.issue,),
        },
    )


@dataclass(frozen=True, slots=True)
class PcbDifferentialPairRouteSkewCandidate(Candidate):
    """A project-mapped pair route exceeds its authored skew or cannot be measured."""

    source_evidence: PcbDifferentialPairRouteSkewFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: PcbDifferentialPairRouteSkewFindingEvidence,
        *,
        message: str,
    ) -> PcbDifferentialPairRouteSkewCandidate:
        projection = project_differential_pair_route_skew_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=f"{source_evidence.entry.bundle_id}: routed differential-pair skew",
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_differential_pair_route_skew_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id:
            raise ValueError("Route-skew rule must match its source evidence")
        if self.evidence != projection.evidence:
            raise ValueError("Route-skew finding evidence must match its projection")
