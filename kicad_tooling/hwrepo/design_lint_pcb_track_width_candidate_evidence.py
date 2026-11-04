"""Typed source evidence and projection for PCB track-width findings."""

from __future__ import annotations

from dataclasses import dataclass

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .pcb_track_width_models import PcbTrackWidthCoverageEntry, PcbTrackWidthCoverageReport

RULE_ID: DesignLintRuleId = "pcb.minimum_track_width"


@dataclass(frozen=True, slots=True)
class PcbTrackWidthFindingEvidence:
    """A mapped width screen with its full source-bound measurement report."""

    report: PcbTrackWidthCoverageReport
    entry: PcbTrackWidthCoverageEntry

    def __post_init__(self) -> None:
        if self.report.status not in {"COMPLETE", "INCOMPLETE"}:
            raise ValueError("Track-width finding evidence requires scanned coverage")
        if self.entry not in self.report.entries:
            raise ValueError("Track-width finding must belong to the source report")
        if self.entry.status == "COMPLETE" and not any(
            item.below_minimum for item in self.entry.tracks
        ):
            raise ValueError("Track-width control coverage emits no finding")


def project_pcb_track_width_evidence(
    source: PcbTrackWidthFindingEvidence,
) -> CandidateEvidenceProjection:
    """Preserve the exact measured tracks and project-authored minimum."""
    entry = source.entry
    below = tuple(item for item in entry.tracks if item.below_minimum)
    measured_tracks = tuple(
        f"{item.track_uuid} {item.layer}: "
        f"{item.width_nm // 1000}.{item.width_nm % 1000:03d} um; "
        f"minimum {item.minimum_width_um} um; "
        f"start {item.start_nm[0]},{item.start_nm[1]} nm; "
        f"end {item.end_nm[0]},{item.end_nm[1]} nm"
        for item in entry.tracks
    )
    return CandidateEvidenceProjection(
        rule_id=RULE_ID,
        evidence={
            "net": (entry.net,),
            "minimum_track_width_um": (str(entry.minimum_width_um),),
            "measured_tracks": measured_tracks,
            "below_minimum_track_uuids": tuple(item.track_uuid for item in below),
            "coverage_status": (entry.status,),
            "basis": (entry.basis,),
            "issues": entry.issues,
            "metric": (
                "KiCad native track item GetWidth in integer nanometers compared "
                + "with the project-authored minimum",
            ),
        },
    )


@dataclass(frozen=True, slots=True)
class PcbTrackWidthCandidate(Candidate):
    """Track-width finding retaining the full measurement source report."""

    source_evidence: PcbTrackWidthFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: PcbTrackWidthFindingEvidence,
        *,
        subject: str,
        message: str,
    ) -> PcbTrackWidthCandidate:
        projection = project_pcb_track_width_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_pcb_track_width_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("Track-width evidence must match its source projection")
