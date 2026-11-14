"""Review project-authored signal capacitance budgets for mapped protectors."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .external_protection_models import (
    ExternalProtectionCapacitanceReview,
    ExternalProtectionCoverageReport,
)

RULE_ID: DesignLintRuleId = "protection.channel_capacitance_budget_exceeded"


@dataclass(frozen=True, slots=True)
class ProtectionCapacitanceFindingEvidence:
    """A reviewed capacitance budget retained with its native-source-bound report."""

    report: ExternalProtectionCoverageReport
    review: ExternalProtectionCapacitanceReview

    def __post_init__(self) -> None:
        if self.report.status not in {"COMPLETE", "INCOMPLETE", "UNDECLARED"}:
            raise ValueError("Capacitance evidence requires admitted protection coverage")
        if self.review not in self.report.capacitance_reviews:
            raise ValueError("Capacitance evidence must match a review in its source report")


def project_protection_capacitance_evidence(
    source: ProtectionCapacitanceFindingEvidence,
) -> CandidateEvidenceProjection:
    """Project authored limits, channel data, and the native value identities."""
    review = source.review
    channels = tuple(
        f"{item.device_reference}.{item.signal_pin.rsplit('.', 1)[1]}: "
        f"{item.maximum_channel_capacitance_pf:g} pF max ({item.expected_value})"
        for item in review.channels
    )
    bases = tuple(item.capacitance_basis for item in review.channels)
    return CandidateEvidenceProjection(
        rule_id=RULE_ID,
        evidence={
            "signal_net": (review.signal_net,),
            "maximum_signal_capacitance_pf": (f"{review.maximum_signal_capacitance_pf:g}",),
            "total_channel_capacitance_pf": (f"{review.total_channel_capacitance_pf:g}",),
            "capacitance_limit_basis": (review.capacitance_limit_basis,),
            "channel_maxima": channels,
            "channel_capacitance_bases": bases,
        },
    )


@dataclass(frozen=True, slots=True)
class ProtectionCapacitanceCandidate(Candidate):
    """Project-owned channel maxima exceed the authored signal budget."""

    source_evidence: ProtectionCapacitanceFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: ProtectionCapacitanceFindingEvidence,
    ) -> ProtectionCapacitanceCandidate:
        projection = project_protection_capacitance_evidence(source_evidence)
        review = source_evidence.review
        return cls(
            rule_id=projection.rule_id,
            subject=f"{review.signal_net}: external-protection capacitance budget",
            message=(
                f"Project-authored protector channel maxima total "
                f"{review.total_channel_capacitance_pf:g} pF, above the project signal limit "
                f"of {review.maximum_signal_capacitance_pf:g} pF. Review the selected parts and "
                "the interface capacitance budget."
            ),
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_protection_capacitance_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("Protection capacitance evidence must match its source projection")


def protection_capacitance_candidates(
    coverage: ExternalProtectionCoverageReport | None,
) -> tuple[ProtectionCapacitanceCandidate, ...]:
    """Emit candidates only when complete authored maxima exceed their project budget."""
    if coverage is None or coverage.status not in {"COMPLETE", "INCOMPLETE", "UNDECLARED"}:
        return ()
    return tuple(
        ProtectionCapacitanceCandidate.from_source_evidence(
            ProtectionCapacitanceFindingEvidence(report=coverage, review=review)
        )
        for review in coverage.capacitance_reviews
        if Decimal(str(review.total_channel_capacitance_pf))
        > Decimal(str(review.maximum_signal_capacitance_pf))
    )
