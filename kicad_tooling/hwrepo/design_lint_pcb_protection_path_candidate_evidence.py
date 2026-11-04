"""Typed source evidence and projection for PCB protection-path findings."""

from __future__ import annotations

from dataclasses import dataclass

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .pcb_protection_path_models import PcbProtectionPathCoverageReport, PcbProtectionPathEntry

RULE_ID: DesignLintRuleId = "pcb.protection_entry_path"


@dataclass(frozen=True, slots=True)
class PcbProtectionPathFindingEvidence:
    """An incomplete connector/protector path with its source-bound report."""

    report: PcbProtectionPathCoverageReport
    entry: PcbProtectionPathEntry

    def __post_init__(self) -> None:
        if self.report.status != "INCOMPLETE":
            raise ValueError("Protection-path finding evidence requires INCOMPLETE report")
        if self.entry.status != "INCOMPLETE" or self.entry not in self.report.entries:
            raise ValueError("Protection-path finding must belong to incomplete report entries")


def project_pcb_protection_path_evidence(
    source: PcbProtectionPathFindingEvidence,
) -> CandidateEvidenceProjection:
    """Preserve native path measurements, mapped limits, and observed identities."""
    entry = source.entry
    entry_distance = (
        "unavailable"
        if entry.connector_to_protection_distance_nm is None
        else f"{entry.connector_to_protection_distance_nm} nm"
    )
    nearest_via_distance = (
        "unavailable"
        if entry.nearest_reference_via_distance_nm is None
        else f"{entry.nearest_reference_via_distance_nm} nm"
    )
    via_count = (
        "not configured"
        if entry.reference_vias_within_radius is None
        else f"{entry.reference_vias_within_radius} within {entry.reference_via_radius_um} um"
    )
    return CandidateEvidenceProjection(
        rule_id=RULE_ID,
        evidence={
            "connector_signal_pad": (entry.connector_signal_pad,),
            "protection_signal_pad": (entry.protection_signal_pad,),
            "protection_reference_pad": (entry.protection_reference_pad,),
            "signal_net": (entry.signal_net,),
            "reference_net": (entry.reference_net,),
            "connector_footprint": (
                entry.expected_connector_footprint,
                entry.observed_connector_footprint or "missing",
            ),
            "protection_footprint": (
                entry.expected_protection_footprint,
                entry.observed_protection_signal_footprint or "missing",
                entry.observed_protection_reference_footprint or "missing",
            ),
            "observed_pad_nets": (
                f"{entry.connector_signal_pad}={entry.observed_connector_signal_net or 'unconnected'}",
                f"{entry.protection_signal_pad}={entry.observed_protection_signal_net or 'unconnected'}",
                f"{entry.protection_reference_pad}={entry.observed_protection_reference_net or 'unconnected'}",
            ),
            "native_signal_path_connected": (
                "yes" if entry.native_signal_path_connected else "no",
            ),
            "connector_to_protection_pad_center_distance": (entry_distance,),
            "maximum_project_distance_um": (
                "not configured"
                if entry.max_entry_distance_um is None
                else str(entry.max_entry_distance_um),
            ),
            "native_connected_reference_vias": (str(entry.connected_reference_via_count),),
            "reference_vias_within_project_radius": (via_count,),
            "nearest_connected_reference_via_distance": (nearest_via_distance,),
            "minimum_vias_in_project_radius": (
                "not configured"
                if entry.minimum_reference_vias is None
                else str(entry.minimum_reference_vias),
            ),
            "issues": entry.issues,
        },
    )


@dataclass(frozen=True, slots=True)
class PcbProtectionPathCandidate(Candidate):
    """Protection-path finding retaining its mapped entry and source report."""

    source_evidence: PcbProtectionPathFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: PcbProtectionPathFindingEvidence,
        *,
        subject: str,
        message: str,
    ) -> PcbProtectionPathCandidate:
        projection = project_pcb_protection_path_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_pcb_protection_path_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("Protection-path evidence must match its source projection")
