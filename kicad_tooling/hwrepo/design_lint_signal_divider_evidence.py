"""Typed evidence projection for source-bound signal-divider findings."""

from __future__ import annotations

from dataclasses import dataclass

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .signal_divider_models import SignalDividerCoverageEntry, SignalDividerCoverageReport

RULE_ID: DesignLintRuleId = "interface.signal_divider_input_range_mismatch"


@dataclass(frozen=True, slots=True)
class SignalDividerFindingEvidence:
    """One noncompliant divider entry and the full source-bound report."""

    report: SignalDividerCoverageReport
    entry: SignalDividerCoverageEntry

    def __post_init__(self) -> None:
        if self.report.status not in {"COMPLETE", "INCOMPLETE"}:
            raise ValueError("Signal-divider finding evidence requires configured coverage")
        if self.entry not in self.report.entries:
            raise ValueError("Signal-divider finding must belong to the source report")
        if self.entry.status == "COMPLETE":
            raise ValueError("Complete signal-divider coverage emits no finding")


def project_signal_divider_evidence(
    source: SignalDividerFindingEvidence,
) -> CandidateEvidenceProjection:
    """Project mapped divider measurements to stable, reviewable evidence fields."""
    entry = source.entry
    calculated = (
        "unavailable"
        if entry.calculated_input_minimum_v is None or entry.calculated_input_maximum_v is None
        else f"{entry.calculated_input_minimum_v:g}–{entry.calculated_input_maximum_v:g} V"
    )
    return CandidateEvidenceProjection(
        rule_id=RULE_ID,
        evidence={
            "profile": (entry.id,),
            "receiver": (entry.receiver_reference,),
            "source_net": (entry.source_net,),
            "input_net": (entry.input_net,),
            "reference_net": (entry.reference_net,),
            "pin_nets": tuple(
                f"{pin} -> {', '.join(nets) or 'unconnected'}"
                for pin, nets in sorted(entry.pin_nets.items())
            ),
            "nominal_resistance_ohms": tuple(
                f"{reference}={value:g} Ω"
                for reference, value in sorted(entry.nominal_resistance_ohms.items())
            ),
            "formula": (entry.formula,),
            "source_voltage_range_v": (f"{entry.source_minimum_v:g}–{entry.source_maximum_v:g} V",),
            "calculated_nominal_input_range_v": (calculated,),
            "target_input_range_v": (
                f"{entry.target_input_minimum_v:g}–{entry.target_input_maximum_v:g} V",
            ),
            "basis": (entry.basis,),
            "issues": entry.issues,
        },
    )


@dataclass(frozen=True, slots=True)
class SignalDividerCandidate(Candidate):
    """Signal-divider finding retaining its exact comparison report."""

    source_evidence: SignalDividerFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: SignalDividerFindingEvidence,
        *,
        subject: str,
        message: str,
    ) -> SignalDividerCandidate:
        projection = project_signal_divider_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_signal_divider_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("Signal-divider evidence must match its source projection")
