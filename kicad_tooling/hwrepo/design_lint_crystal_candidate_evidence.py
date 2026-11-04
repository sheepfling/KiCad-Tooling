"""Typed source evidence and projection for crystal-network findings."""

from __future__ import annotations

from dataclasses import dataclass

from .crystal_network_models import CrystalNetworkCoverageEntry, CrystalNetworkCoverageReport
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection

RULE_ID: DesignLintRuleId = "oscillator.crystal_load_network_mismatch"


@dataclass(frozen=True, slots=True)
class CrystalNetworkFindingEvidence:
    """One reviewable oscillator entry and its complete source-bound report."""

    report: CrystalNetworkCoverageReport
    entry: CrystalNetworkCoverageEntry

    def __post_init__(self) -> None:
        if self.report.status not in {"COMPLETE", "INCOMPLETE"}:
            raise ValueError("Crystal finding evidence requires configured coverage")
        if self.entry not in self.report.entries:
            raise ValueError("Crystal finding must belong to the source report")
        if self.entry.status == "COMPLETE":
            raise ValueError("Complete crystal-network coverage emits no finding")


def project_crystal_network_evidence(
    source: CrystalNetworkFindingEvidence,
) -> CandidateEvidenceProjection:
    """Project the typed load-network measurements to established report fields."""
    entry = source.entry
    calculated = (
        "unavailable"
        if entry.calculated_minimum_load_pf is None or entry.calculated_maximum_load_pf is None
        else (f"{entry.calculated_minimum_load_pf:g}–{entry.calculated_maximum_load_pf:g} pF")
    )
    return CandidateEvidenceProjection(
        rule_id=RULE_ID,
        evidence={
            "oscillator": (entry.oscillator_reference,),
            "resonator": (entry.resonator_reference,),
            "load_capacitors": entry.load_capacitor_references,
            "potential_extra_load_capacitors": entry.extra_capacitor_references,
            "potential_extra_load_capacitor_pin_nets": tuple(
                f"{reference}: {', '.join(pin_nets)}"
                for reference, pin_nets in sorted(entry.extra_capacitor_pin_nets.items())
            ),
            "pin_nets": tuple(
                f"{pin} -> {', '.join(nets) or 'unconnected'}"
                for pin, nets in sorted(entry.node_nets.items())
            ),
            "capacitance_pf": tuple(
                f"{reference}={value:g} pF"
                for reference, value in sorted(entry.capacitance_pf.items())
            ),
            "formula": (entry.formula,),
            "calculated_nominal_load_pf": (calculated,),
            "target_nominal_load_pf": (
                f"{entry.target_minimum_load_pf:g}–{entry.target_maximum_load_pf:g} pF",
            ),
            "stray_capacitance_assumption_pf": (
                f"{entry.minimum_stray_capacitance_pf:g}–{entry.maximum_stray_capacitance_pf:g} pF",
            ),
            "basis": (entry.basis,),
            "issues": entry.issues,
        },
    )


@dataclass(frozen=True, slots=True)
class CrystalNetworkCandidate(Candidate):
    """Crystal finding that retains the exact comparison and source report."""

    source_evidence: CrystalNetworkFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: CrystalNetworkFindingEvidence,
        *,
        subject: str,
        message: str,
    ) -> CrystalNetworkCandidate:
        projection = project_crystal_network_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_crystal_network_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("Crystal evidence must match its source projection")
