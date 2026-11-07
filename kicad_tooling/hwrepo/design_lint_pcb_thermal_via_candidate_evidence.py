"""Typed source evidence and projection for PCB thermal-pad via findings."""

from __future__ import annotations

from dataclasses import dataclass

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .pcb_thermal_via_models import PcbThermalViaCoverageEntry, PcbThermalViaCoverageReport

RULE_ID: DesignLintRuleId = "pcb.thermal_via_coverage"


@dataclass(frozen=True, slots=True)
class PcbThermalViaFindingEvidence:
    """One authored pad screen and its source-bound native PCB report."""

    report: PcbThermalViaCoverageReport
    entry: PcbThermalViaCoverageEntry

    def __post_init__(self) -> None:
        if self.report.status not in {"COMPLETE", "INCOMPLETE"}:
            raise ValueError("Thermal-via finding evidence requires scanned coverage")
        if self.entry not in self.report.entries:
            raise ValueError("Thermal-via finding must belong to the source report")
        if self.entry.status == "COMPLETE":
            raise ValueError("Complete thermal-via coverage emits no finding")


def project_pcb_thermal_via_evidence(
    source: PcbThermalViaFindingEvidence,
) -> CandidateEvidenceProjection:
    """Retain exact via identities, connectivity, distances, and required layer spans."""
    entry = source.entry
    measurements = tuple(
        f"{item.via_id}: {item.start_layer} to {item.end_layer}; "
        f"multiplicity {item.multiplicity}; distance squared "
        f"{item.center_distance_squared_nm2} nm^2; "
        f"within radius={'yes' if item.within_authored_radius else 'no'}; "
        f"connected to pad component={'yes' if item.connected_to_pad_component else 'no'}"
        for item in entry.measurements
    )
    required = tuple(
        f"{item.start_layer} to {item.end_layer}: minimum {item.minimum_vias}"
        for item in entry.required_layer_spans
    )
    return CandidateEvidenceProjection(
        rule_id=RULE_ID,
        evidence={
            "pad": (entry.pad,),
            "expected_footprint": (entry.expected_footprint,),
            "observed_footprint": (entry.observed_footprint or "unavailable",),
            "expected_net": (entry.expected_net,),
            "observed_net": (entry.observed_net or "unavailable",),
            "maximum_center_distance_um": (str(entry.maximum_center_distance_um),),
            "required_layer_spans": required,
            "native_vias": measurements,
            "issues": entry.issues,
            "basis": (entry.basis,),
            "metric_limit": (
                (
                    "Exact native connectivity, layer transitions, and via-center distance only; "
                    "no thermal resistance, temperature, solderability, or thermal adequacy is inferred."
                ),
            ),
        },
    )


@dataclass(frozen=True, slots=True)
class PcbThermalViaCandidate(Candidate):
    """Thermal-pad via coverage finding retaining its complete native report."""

    source_evidence: PcbThermalViaFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: PcbThermalViaFindingEvidence,
        *,
        subject: str,
        message: str,
    ) -> PcbThermalViaCandidate:
        projection = project_pcb_thermal_via_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_pcb_thermal_via_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("Thermal-via evidence must match its source projection")
