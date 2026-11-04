"""Typed source evidence and projection for regulator-feedback findings."""

from __future__ import annotations

from dataclasses import dataclass

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .regulator_feedback_models import (
    RegulatorFeedbackCoverageEntry,
    RegulatorFeedbackCoverageReport,
)

RULE_ID: DesignLintRuleId = "power.regulator_feedback_mismatch"


@dataclass(frozen=True, slots=True)
class RegulatorFeedbackFindingEvidence:
    """One reviewable divider entry and its complete source-bound report."""

    report: RegulatorFeedbackCoverageReport
    entry: RegulatorFeedbackCoverageEntry

    def __post_init__(self) -> None:
        if self.report.status not in {"COMPLETE", "INCOMPLETE"}:
            raise ValueError("Regulator finding evidence requires configured coverage")
        if self.entry not in self.report.entries:
            raise ValueError("Regulator finding must belong to the source report")
        if self.entry.status == "COMPLETE":
            raise ValueError("Complete regulator feedback coverage emits no finding")


def project_regulator_feedback_evidence(
    source: RegulatorFeedbackFindingEvidence,
) -> CandidateEvidenceProjection:
    """Project the typed divider measurements to the established report fields."""
    entry = source.entry
    calculated = (
        "unavailable"
        if entry.calculated_output_minimum_v is None or entry.calculated_output_maximum_v is None
        else (f"{entry.calculated_output_minimum_v:g}–{entry.calculated_output_maximum_v:g} V")
    )
    feedback_reference_range = (
        f"{entry.feedback_reference_minimum_v:g}–{entry.feedback_reference_maximum_v:g} V"
    )
    target_output_range = f"{entry.target_output_minimum_v:g}–{entry.target_output_maximum_v:g} V"
    return CandidateEvidenceProjection(
        rule_id=RULE_ID,
        evidence={
            "profile": (entry.id,),
            "regulator": (entry.regulator_reference,),
            "output_net": (entry.output_net,),
            "reference_net": (entry.reference_net,),
            "feedback_net": (entry.feedback_net or "<unresolved>",),
            "pin_nets": tuple(
                f"{pin} -> {', '.join(nets) or 'unconnected'}"
                for pin, nets in sorted(entry.pin_nets.items())
            ),
            "nominal_resistance_ohms": tuple(
                f"{reference}={value:g} Ω"
                for reference, value in sorted(entry.nominal_resistance_ohms.items())
            ),
            "formula": (entry.formula,),
            "feedback_reference_range_v": (feedback_reference_range,),
            "calculated_nominal_output_range_v": (calculated,),
            "target_output_range_v": (target_output_range,),
            "basis": (entry.basis,),
            "issues": entry.issues,
        },
    )


@dataclass(frozen=True, slots=True)
class RegulatorFeedbackCandidate(Candidate):
    """Regulator finding that retains the exact comparison and source report."""

    source_evidence: RegulatorFeedbackFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: RegulatorFeedbackFindingEvidence,
        *,
        subject: str,
        message: str,
    ) -> RegulatorFeedbackCandidate:
        projection = project_regulator_feedback_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_regulator_feedback_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("Regulator evidence must match its source projection")
