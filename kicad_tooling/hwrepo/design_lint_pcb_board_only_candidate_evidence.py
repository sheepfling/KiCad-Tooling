"""Typed source evidence and report projections for PCB board-only findings."""

from __future__ import annotations

from dataclasses import dataclass

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .pcb_board_only_footprint_models import PcbBoardOnlyFootprint
from .pcb_component_inventory_models import (
    PcbComponentInventoryCoverageReport,
    PcbComponentInventorySourceReceipt,
)

RULE_ID: DesignLintRuleId = "pcb.board_only_footprint"


@dataclass(frozen=True, slots=True)
class PcbBoardOnlyFootprintEvidence:
    """One board-only footprint comparison with its native source receipt."""

    observation: PcbBoardOnlyFootprint
    receipt: PcbComponentInventorySourceReceipt


def project_pcb_board_only_footprint_evidence(
    source: PcbBoardOnlyFootprintEvidence,
) -> CandidateEvidenceProjection:
    """Project one board-only comparison into the established report fields."""
    receipt = source.receipt
    return CandidateEvidenceProjection(
        rule_id=RULE_ID,
        evidence={
            "reference": (source.observation.reference,),
            "footprint": (source.observation.footprint,),
            "netlist_sha256": (receipt.netlist_sha256 or "unavailable",),
            "board_path": (receipt.board_path or "unavailable",),
            "board_sha256": (receipt.board_sha256 or "unavailable",),
            "snapshot_sha256": (receipt.snapshot_sha256 or "unavailable",),
            "snapshot_schema": (receipt.snapshot_schema or "unavailable",),
            "kicad_version": (receipt.kicad_version or "unavailable",),
            "image": (receipt.image or "unavailable",),
            "probe_sha256": (receipt.probe_sha256 or "unavailable",),
        },
    )


@dataclass(frozen=True, slots=True)
class PcbBoardOnlyFootprintCandidate(Candidate):
    """Board-only finding retaining the exact footprint and native receipt."""

    source_evidence: PcbBoardOnlyFootprintEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: PcbBoardOnlyFootprintEvidence,
        *,
        subject: str,
        message: str,
    ) -> PcbBoardOnlyFootprintCandidate:
        projection = project_pcb_board_only_footprint_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_pcb_board_only_footprint_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id:
            raise ValueError("PCB board-only rule must match its source evidence")
        if self.evidence != projection.evidence:
            raise ValueError("PCB board-only evidence must match its typed projection")


@dataclass(frozen=True, slots=True)
class PcbBlockedBoardOnlyFootprintEvidence:
    """Blocked board-only coverage with the exact enclosing inventory report."""

    report: PcbComponentInventoryCoverageReport

    def __post_init__(self) -> None:
        if self.report.status != "BLOCKED":
            raise ValueError("Blocked board-only evidence requires BLOCKED inventory")
        if self.report.board_only_footprint_coverage.status != "BLOCKED":
            raise ValueError("Blocked board-only evidence requires BLOCKED board-only coverage")


def project_blocked_pcb_board_only_evidence(
    source: PcbBlockedBoardOnlyFootprintEvidence,
) -> CandidateEvidenceProjection:
    """Project unavailable board-only coverage without implying a quiet board."""
    report = source.report
    coverage = report.board_only_footprint_coverage
    return CandidateEvidenceProjection(
        rule_id=RULE_ID,
        evidence={
            "coverage_issue": (coverage.issue or "unavailable",),
            "netlist_sha256": (() if report.netlist_sha256 is None else (report.netlist_sha256,)),
            "board_path": (() if report.board_path is None else (report.board_path,)),
            "board_sha256": (() if report.board_sha256 is None else (report.board_sha256,)),
            "snapshot_sha256": (
                () if report.snapshot_sha256 is None else (report.snapshot_sha256,)
            ),
        },
    )


@dataclass(frozen=True, slots=True)
class PcbBlockedBoardOnlyFootprintCandidate(Candidate):
    """Blocked board-only finding retaining the coverage report that stopped it."""

    source_evidence: PcbBlockedBoardOnlyFootprintEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: PcbBlockedBoardOnlyFootprintEvidence,
        *,
        subject: str,
        message: str,
    ) -> PcbBlockedBoardOnlyFootprintCandidate:
        projection = project_blocked_pcb_board_only_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_blocked_pcb_board_only_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id:
            raise ValueError("Blocked PCB board-only rule must match its source evidence")
        if self.evidence != projection.evidence:
            raise ValueError("Blocked PCB board-only evidence must match its typed projection")
