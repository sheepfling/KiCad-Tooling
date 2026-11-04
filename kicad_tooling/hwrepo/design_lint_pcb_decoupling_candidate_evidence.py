"""Typed source evidence and projection for PCB decoupling findings."""

from __future__ import annotations

from dataclasses import dataclass

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .pcb_decoupling_models import PcbDecouplingCoverageEntry, PcbDecouplingCoverageReport

RULE_ID: DesignLintRuleId = "pcb.decoupling_proximity"


@dataclass(frozen=True, slots=True)
class PcbDecouplingFindingEvidence:
    """A mapped capacitor comparison and its source-bound board report."""

    report: PcbDecouplingCoverageReport
    entry: PcbDecouplingCoverageEntry

    def __post_init__(self) -> None:
        if self.report.status not in {"COMPLETE", "INCOMPLETE"}:
            raise ValueError("Decoupling finding evidence requires scanned coverage")
        if self.entry not in self.report.entries:
            raise ValueError("Decoupling finding must belong to the source report")
        if self.entry.status == "COMPLETE" and self.entry.max_distance_um is not None:
            raise ValueError("Bounded complete decoupling coverage emits no finding")


def project_pcb_decoupling_evidence(
    source: PcbDecouplingFindingEvidence,
) -> CandidateEvidenceProjection:
    """Preserve candidate measurements and the existing review boundaries."""
    entry = source.entry
    measured: list[str] = []
    for candidate in entry.candidates:
        distance = (
            "unavailable"
            if candidate.distance_nm is None
            else f"{candidate.distance_nm // 1000}.{candidate.distance_nm % 1000:03d} um"
        )
        via_distance = (
            "unavailable"
            if candidate.return_via_distance_nm is None
            else f"{candidate.return_via_distance_nm // 1000}.{candidate.return_via_distance_nm % 1000:03d} um"
        )
        via_id = candidate.nearest_return_via_id or "unavailable"
        state = "eligible" if candidate.eligible else "not eligible"
        measured.append(
            f"{candidate.reference}: supply-pad distance {distance}; "
            f"connected return vias {candidate.connected_return_via_count}; "
            f"nearest return via {via_id} at {via_distance}; {state}"
        )
    return CandidateEvidenceProjection(
        rule_id=RULE_ID,
        evidence={
            "ic_supply_pad": (entry.ic_supply_pad,),
            "ic_return_pad": (entry.ic_return_pad,),
            "supply_net": (entry.ic_supply_net,),
            "return_net": (entry.ic_return_net,),
            "selection": (entry.selection,),
            "maximum_center_distance_um": (
                "not configured" if entry.max_distance_um is None else str(entry.max_distance_um),
            ),
            "maximum_return_via_distance_um": (
                "not configured"
                if entry.max_return_via_distance_um is None
                else str(entry.max_return_via_distance_um),
            ),
            "selected_capacitors": entry.selected_capacitors,
            "candidate_distances": tuple(measured),
            "issues": entry.issues
            + tuple(issue for candidate in entry.candidates for issue in candidate.issues),
            "distance_basis": (
                "Euclidean distance between native IC supply-pad center and native capacitor supply-pad center",
            ),
            "return_via_distance_basis": (
                "Euclidean distance from the native capacitor return-pad center to a via listed in that pad's native copper-connectivity component",
            ),
        },
    )


@dataclass(frozen=True, slots=True)
class PcbDecouplingCandidate(Candidate):
    """Decoupling finding retaining its exact candidate set and native report."""

    source_evidence: PcbDecouplingFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: PcbDecouplingFindingEvidence,
        *,
        subject: str,
        message: str,
    ) -> PcbDecouplingCandidate:
        projection = project_pcb_decoupling_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_pcb_decoupling_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("Decoupling evidence must match its source projection")
