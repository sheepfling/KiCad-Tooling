"""Source-bound findings for project-authored PCB fiducial counts."""

from __future__ import annotations

from dataclasses import dataclass

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .pcb_fiducial_models import PcbFiducialCoverageEntry, PcbFiducialCoverageReport

RULE_ID: DesignLintRuleId = "pcb.fiducial_count"


@dataclass(frozen=True, slots=True)
class PcbFiducialFindingEvidence:
    """One incomplete requirement or a blocked source-bound scan."""

    report: PcbFiducialCoverageReport
    entry: PcbFiducialCoverageEntry | None = None

    def __post_init__(self) -> None:
        if self.report.status == "INCOMPLETE":
            if self.entry is None or self.entry not in self.report.entries:
                raise ValueError("Incomplete fiducial findings require a report entry")
            if self.entry.status != "INCOMPLETE":
                raise ValueError("Complete fiducial requirement cannot emit a finding")
        elif self.report.status == "BLOCKED":
            if self.entry is not None:
                raise ValueError("Blocked fiducial evidence cannot claim a measured entry")
        else:
            raise ValueError("Fiducial finding evidence needs incomplete or blocked coverage")


def project_pcb_fiducial_evidence(
    source: PcbFiducialFindingEvidence,
) -> CandidateEvidenceProjection:
    """Keep the exact requirement, board receipt, and matched native footprints visible."""
    report = source.report
    entry = source.entry
    observations = (
        ()
        if entry is None
        else tuple(
            f"{item.reference}: {item.footprint}; {item.side}; position {item.position_nm[0]},{item.position_nm[1]} nm"
            for item in entry.observations
        )
    )
    return CandidateEvidenceProjection(
        rule_id=RULE_ID,
        evidence={
            "status": (report.status,),
            "requirement_id": (() if entry is None else (entry.id,)),
            "basis": (() if entry is None else (entry.basis,)),
            "minimum_count": (() if entry is None else (str(entry.minimum_count),)),
            "accepted_footprints": (() if entry is None else entry.accepted_footprints),
            "required_side": (() if entry is None else (entry.side,)),
            "observed_count": (() if entry is None else (str(entry.observed_count),)),
            "native_footprints": observations,
            "issues": (() if entry is None else entry.issues),
            "map_sha256": (() if report.map_sha256 is None else (report.map_sha256,)),
            "board_path": (() if report.board_path is None else (report.board_path,)),
            "board_sha256": (() if report.board_sha256 is None else (report.board_sha256,)),
            "snapshot_sha256": (
                () if report.snapshot_sha256 is None else (report.snapshot_sha256,)
            ),
            "kicad_version": (() if report.kicad_version is None else (report.kicad_version,)),
            "issue": (() if report.issue is None else (report.issue,)),
            "limit": (
                (
                    "Counts only fitted native PCB footprint identities from the exact authored "
                    "list. It does not verify panel fiducials, pad geometry, solder-mask openings, "
                    "assembly vision performance, or manufacturing suitability."
                ),
            ),
        },
    )


@dataclass(frozen=True, slots=True)
class PcbFiducialCandidate(Candidate):
    """Review finding retaining its typed native source report."""

    source_evidence: PcbFiducialFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: PcbFiducialFindingEvidence,
        *,
        subject: str,
        message: str,
    ) -> PcbFiducialCandidate:
        projection = project_pcb_fiducial_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_pcb_fiducial_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("Fiducial candidate evidence must match its source projection")
