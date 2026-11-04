"""Typed source and report projection for RF module antenna findings."""

from __future__ import annotations

from dataclasses import dataclass

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .pcb_rf_antenna_models import (
    PcbRfModuleAntennaCoverageEntry,
    PcbRfModuleAntennaCoverageReport,
)

RULE_ID: DesignLintRuleId = "pcb.rf_module_antenna_keepout_coverage"


@dataclass(frozen=True, slots=True)
class PcbRfAntennaFindingEvidence:
    """An incomplete module comparison with its source-bound board report."""

    report: PcbRfModuleAntennaCoverageReport
    entry: PcbRfModuleAntennaCoverageEntry

    def __post_init__(self) -> None:
        if self.report.status != "INCOMPLETE":
            raise ValueError("RF antenna finding evidence requires INCOMPLETE report")
        if self.entry.status != "INCOMPLETE" or self.entry not in self.report.entries:
            raise ValueError("RF antenna finding must belong to incomplete report entries")


def project_pcb_rf_antenna_evidence(
    source: PcbRfAntennaFindingEvidence,
) -> CandidateEvidenceProjection:
    """Keep the existing module, feed, and placement-relative keepout fields."""
    entry = source.entry
    return CandidateEvidenceProjection(
        rule_id=RULE_ID,
        evidence={
            "basis": (entry.basis,),
            "disposition": (entry.disposition,),
            "expected_symbol": (entry.expected_symbol,),
            "observed_symbol": (() if entry.observed_symbol is None else (entry.observed_symbol,)),
            "expected_footprint": (entry.expected_footprint,),
            "observed_schematic_footprint": (
                ()
                if entry.observed_schematic_footprint is None
                else (entry.observed_schematic_footprint,)
            ),
            "observed_board_footprint": (
                () if entry.observed_board_footprint is None else (entry.observed_board_footprint,)
            ),
            "expected_part_id": (
                () if entry.expected_part_id is None else (entry.expected_part_id,)
            ),
            "observed_part_id": (
                () if entry.observed_part_id is None else (entry.observed_part_id,)
            ),
            "rf_feed_pad": (() if entry.rf_feed_pad is None else (entry.rf_feed_pad,)),
            "expected_rf_feed_net": (
                () if entry.expected_rf_feed_net is None else (entry.expected_rf_feed_net,)
            ),
            "observed_schematic_rf_feed_nets": (entry.observed_schematic_rf_feed_nets),
            "observed_board_rf_feed_net": (
                ()
                if entry.observed_board_rf_feed_net is None
                else (entry.observed_board_rf_feed_net,)
            ),
            "expected_keepout_name": (
                () if entry.expected_keepout_name is None else (entry.expected_keepout_name,)
            ),
            "expected_geometry_sha256": (
                () if entry.expected_geometry_sha256 is None else (entry.expected_geometry_sha256,)
            ),
            "observed_geometry_sha256": (
                () if entry.observed_geometry_sha256 is None else (entry.observed_geometry_sha256,)
            ),
            "issues": entry.issues,
        },
    )


@dataclass(frozen=True, slots=True)
class PcbRfAntennaCandidate(Candidate):
    """RF module finding retaining its authored and native source evidence."""

    source_evidence: PcbRfAntennaFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: PcbRfAntennaFindingEvidence,
        *,
        subject: str,
        message: str,
    ) -> PcbRfAntennaCandidate:
        projection = project_pcb_rf_antenna_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_pcb_rf_antenna_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id:
            raise ValueError("RF antenna rule must match its source evidence")
        if self.evidence != projection.evidence:
            raise ValueError("RF antenna evidence must match its projection")
