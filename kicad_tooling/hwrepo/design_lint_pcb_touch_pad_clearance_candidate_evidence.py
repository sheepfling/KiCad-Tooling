"""Typed source evidence and projections for touch-pad clearance findings."""

from __future__ import annotations

from dataclasses import dataclass

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .pcb_touch_pad_clearance_models import (
    PcbTouchPadClearanceCoverageEntry,
    PcbTouchPadClearanceCoverageReport,
)

RULE_ID: DesignLintRuleId = "pcb.touch_pad_reference_clearance"


@dataclass(frozen=True, slots=True)
class PcbBlockedTouchPadClearanceFindingEvidence:
    """Blocked map coverage with its explicit issue and authored-map identity."""

    report: PcbTouchPadClearanceCoverageReport

    def __post_init__(self) -> None:
        if self.report.status != "BLOCKED":
            raise ValueError("Blocked touch-pad finding evidence requires BLOCKED report")


def project_blocked_touch_pad_clearance_evidence(
    source: PcbBlockedTouchPadClearanceFindingEvidence,
) -> CandidateEvidenceProjection:
    """Preserve the established sparse evidence fields for unavailable coverage."""
    report = source.report
    return CandidateEvidenceProjection(
        rule_id=RULE_ID,
        evidence={
            "map_sha256": () if report.map_sha256 is None else (report.map_sha256,),
            "issue": () if report.issue is None else (report.issue,),
        },
    )


@dataclass(frozen=True, slots=True)
class PcbBlockedTouchPadClearanceCandidate(Candidate):
    """Blocked touch-pad review finding retaining the complete coverage report."""

    source_evidence: PcbBlockedTouchPadClearanceFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: PcbBlockedTouchPadClearanceFindingEvidence,
    ) -> PcbBlockedTouchPadClearanceCandidate:
        projection = project_blocked_touch_pad_clearance_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject="touch-pad clearance evidence",
            message=(
                "The configured touch-pad clearance could not be measured against the "
                "source-bound native PCB snapshot. Review the probe evidence and exact "
                "project-authored clearance requirement."
            ),
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_blocked_touch_pad_clearance_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("Blocked touch-pad evidence must match its source projection")


@dataclass(frozen=True, slots=True)
class PcbTouchPadClearanceFindingEvidence:
    """A measured or incomplete pad comparison with its source-bound report."""

    report: PcbTouchPadClearanceCoverageReport
    entry: PcbTouchPadClearanceCoverageEntry

    def __post_init__(self) -> None:
        if self.report.status not in {"COMPLETE", "INCOMPLETE"}:
            raise ValueError("Touch-pad finding evidence requires scanned coverage")
        if self.entry not in self.report.entries:
            raise ValueError("Touch-pad finding must belong to the source report")
        if self.entry.status == "COMPLETE" and not self.entry.violates_minimum_clearance:
            raise ValueError("Valid touch-pad clearance emits no finding")


def project_touch_pad_clearance_evidence(
    source: PcbTouchPadClearanceFindingEvidence,
) -> CandidateEvidenceProjection:
    """Preserve the established measurement and complete source receipt fields."""
    report = source.report
    entry = source.entry
    measured = (
        "unavailable" if entry.measured_clearance_nm is None else str(entry.measured_clearance_nm)
    )
    return CandidateEvidenceProjection(
        rule_id=RULE_ID,
        evidence={
            "basis": (entry.basis,),
            "pad": (entry.pad,),
            "expected_pad_net": (entry.expected_pad_net,),
            "schematic_pad_net": (
                () if entry.schematic_pad_net is None else (entry.schematic_pad_net,)
            ),
            "observed_pad_net": (
                () if entry.observed_pad_net is None else (entry.observed_pad_net,)
            ),
            "reference_net": (entry.reference_net,),
            "layer": (entry.layer,),
            "minimum_clearance_nm": (str(entry.minimum_clearance_nm),),
            "measured_clearance_nm": (measured,),
            "closest_zone_uuid": (
                () if entry.closest_zone_uuid is None else (entry.closest_zone_uuid,)
            ),
            "violates_minimum_clearance": (str(entry.violates_minimum_clearance).lower(),),
            "coverage_status": (entry.status,),
            "issues": entry.issues,
            "board_path": (() if report.board_path is None else (report.board_path,)),
            "board_sha256": (() if report.board_sha256 is None else (report.board_sha256,)),
            "snapshot_path": (() if report.snapshot_path is None else (report.snapshot_path,)),
            "snapshot_sha256": (
                () if report.snapshot_sha256 is None else (report.snapshot_sha256,)
            ),
            "probe_sha256": (() if report.probe_sha256 is None else (report.probe_sha256,)),
            "request_sha256": (() if report.request_sha256 is None else (report.request_sha256,)),
            "kicad_version": (() if report.kicad_version is None else (report.kicad_version,)),
            "image": () if report.image is None else (report.image,),
        },
    )


@dataclass(frozen=True, slots=True)
class PcbTouchPadClearanceCandidate(Candidate):
    """Per-requirement touch-pad finding retaining its source report and entry."""

    source_evidence: PcbTouchPadClearanceFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: PcbTouchPadClearanceFindingEvidence,
    ) -> PcbTouchPadClearanceCandidate:
        projection = project_touch_pad_clearance_evidence(source_evidence)
        entry = source_evidence.entry
        message = (
            "Review the exact touch-pad clearance requirement and filled-copper "
            "measurement. The measured gap must meet the project's independently "
            "approved minimum."
            if entry.status == "COMPLETE"
            else "The mapped touch-pad clearance is incomplete; resolve its evidence "
            "gaps before relying on the measurement."
        )
        return cls(
            rule_id=projection.rule_id,
            subject=f"{entry.pad} to {entry.reference_net} on {entry.layer}",
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_touch_pad_clearance_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("Touch-pad evidence must match its source projection")


def touch_pad_clearance_violations(
    coverage: PcbTouchPadClearanceCoverageReport,
) -> tuple[Candidate, ...]:
    """Emit typed findings for blocked coverage, incomplete evidence, or a narrow gap."""
    found: list[Candidate] = []
    if coverage.status == "BLOCKED":
        found.append(
            PcbBlockedTouchPadClearanceCandidate.from_source_evidence(
                PcbBlockedTouchPadClearanceFindingEvidence(report=coverage)
            )
        )
    for entry in coverage.entries:
        if entry.status == "COMPLETE" and not entry.violates_minimum_clearance:
            continue
        found.append(
            PcbTouchPadClearanceCandidate.from_source_evidence(
                PcbTouchPadClearanceFindingEvidence(report=coverage, entry=entry)
            )
        )
    return tuple(found)
