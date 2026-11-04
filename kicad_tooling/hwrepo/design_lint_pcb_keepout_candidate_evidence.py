"""Typed source and report projection for named PCB keepout findings."""

from __future__ import annotations

from dataclasses import dataclass

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .pcb_keepout_models import PcbKeepoutCoverageEntry, PcbKeepoutCoverageReport

RULE_ID: DesignLintRuleId = "pcb.keepout_intent_coverage"


@dataclass(frozen=True, slots=True)
class PcbKeepoutFindingEvidence:
    """An incomplete named-area comparison with its source-bound report."""

    report: PcbKeepoutCoverageReport
    entry: PcbKeepoutCoverageEntry

    def __post_init__(self) -> None:
        if self.report.status != "INCOMPLETE":
            raise ValueError("Keepout finding evidence requires INCOMPLETE report")
        if self.entry.status != "INCOMPLETE" or self.entry not in self.report.entries:
            raise ValueError("Keepout finding must belong to incomplete report entries")


def project_pcb_keepout_evidence(
    source: PcbKeepoutFindingEvidence,
) -> CandidateEvidenceProjection:
    """Keep the existing named-area signature and observed restriction fields."""
    entry = source.entry
    observed_restrictions = tuple(
        f"{name}={value}"
        for name, value in (
            ("tracks", entry.observed_forbids_tracks),
            ("vias", entry.observed_forbids_vias),
            ("pads", entry.observed_forbids_pads),
            ("zone_fills", entry.observed_forbids_zone_fills),
            ("footprints", entry.observed_forbids_footprints),
        )
        if value is not None
    )
    return CandidateEvidenceProjection(
        rule_id=RULE_ID,
        evidence={
            "basis": (entry.basis,),
            "expected_geometry_sha256": (entry.expected_geometry_sha256,),
            "observed_geometry_sha256": (
                () if entry.observed_geometry_sha256 is None else (entry.observed_geometry_sha256,)
            ),
            "expected_layers": entry.expected_layers,
            "observed_layers": entry.observed_layers,
            "observed_restrictions": observed_restrictions,
            "issues": entry.issues,
        },
    )


@dataclass(frozen=True, slots=True)
class PcbKeepoutCandidate(Candidate):
    """Named keepout finding retaining its exact comparison and source report."""

    source_evidence: PcbKeepoutFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: PcbKeepoutFindingEvidence,
        *,
        subject: str,
        message: str,
    ) -> PcbKeepoutCandidate:
        projection = project_pcb_keepout_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_pcb_keepout_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id:
            raise ValueError("Keepout rule must match its source evidence")
        if self.evidence != projection.evidence:
            raise ValueError("Keepout evidence must match its projection")
