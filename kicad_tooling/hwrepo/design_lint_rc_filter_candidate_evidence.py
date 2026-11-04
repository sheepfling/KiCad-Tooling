"""Typed source evidence and projection for mapped RC-filter findings."""

from __future__ import annotations

from dataclasses import dataclass

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .rc_filter_models import RcFilterCoverageEntry, RcFilterCoverageReport

RULE_ID: DesignLintRuleId = "filter.rc_corner_mismatch"


@dataclass(frozen=True, slots=True)
class RcFilterFindingEvidence:
    """One reviewable RC comparison and its source-bound coverage report."""

    report: RcFilterCoverageReport
    entry: RcFilterCoverageEntry

    def __post_init__(self) -> None:
        if self.report.status not in {"COMPLETE", "INCOMPLETE"}:
            raise ValueError("RC-filter finding evidence requires configured coverage")
        if self.entry not in self.report.entries:
            raise ValueError("RC-filter finding must belong to the source report")
        if self.entry.status == "COMPLETE":
            raise ValueError("Complete RC-filter coverage emits no finding")


def project_rc_filter_evidence(
    source: RcFilterFindingEvidence,
) -> CandidateEvidenceProjection:
    """Project exact mapped RC measurements to the established report fields."""
    entry = source.entry
    calculated = (
        "unavailable"
        if entry.calculated_corner_hz is None
        else f"{entry.calculated_corner_hz:g} Hz"
    )
    resistance = "unavailable" if entry.resistance_ohms is None else f"{entry.resistance_ohms:g} Ω"
    capacitance = "unavailable" if entry.capacitance_pf is None else f"{entry.capacitance_pf:g} pF"
    return CandidateEvidenceProjection(
        rule_id=RULE_ID,
        evidence={
            "profile": (entry.id,),
            "resistor": (entry.resistor_reference,),
            "capacitor": (entry.capacitor_reference,),
            "input_net": (entry.input_net,),
            "filtered_net": (entry.filtered_net,),
            "reference_net": (entry.reference_net,),
            "pin_nets": tuple(
                f"{pin} -> {', '.join(nets) or 'unconnected'}"
                for pin, nets in sorted(entry.pin_nets.items())
            ),
            "nominal_resistance_ohms": (resistance,),
            "nominal_capacitance_pf": (capacitance,),
            "formula": (entry.formula,),
            "calculated_nominal_corner_hz": (calculated,),
            "target_corner_hz": (
                f"{entry.target_minimum_corner_hz:g}–{entry.target_maximum_corner_hz:g} Hz",
            ),
            "nominal_resistance_range_ohms": (
                (
                    f"{entry.nominal_resistance_range_ohms[0]:g}–"
                    f"{entry.nominal_resistance_range_ohms[1]:g} Ω"
                ),
            ),
            "nominal_capacitance_range_pf": (
                (
                    f"{entry.nominal_capacitance_range_pf[0]:g}–"
                    f"{entry.nominal_capacitance_range_pf[1]:g} pF"
                ),
            ),
            "unlisted_parallel_components": entry.unlisted_parallel_components,
            "basis": (entry.basis,),
            "issues": entry.issues,
        },
    )


@dataclass(frozen=True, slots=True)
class RcFilterCandidate(Candidate):
    """RC-filter finding retaining its exact coverage entry and source report."""

    source_evidence: RcFilterFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: RcFilterFindingEvidence,
        *,
        subject: str,
        message: str,
    ) -> RcFilterCandidate:
        projection = project_rc_filter_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_rc_filter_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("RC-filter evidence must match its source projection")
