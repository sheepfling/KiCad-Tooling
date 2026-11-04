"""Typed source evidence and projections for blocked PCB inventory coverage."""

from __future__ import annotations

from dataclasses import dataclass

from .design_lint_types import Candidate, CandidateEvidenceProjection
from .pcb_component_inventory_models import PcbComponentInventoryCoverageReport


@dataclass(frozen=True, slots=True)
class PcbBlockedComponentInventoryEvidence:
    """Source report whose top-level PCB inventory status is explicitly blocked."""

    report: PcbComponentInventoryCoverageReport

    def __post_init__(self) -> None:
        if self.report.status != "BLOCKED":
            raise ValueError("Blocked PCB inventory evidence requires BLOCKED status")


def project_blocked_component_inventory_evidence(
    source: PcbBlockedComponentInventoryEvidence,
) -> CandidateEvidenceProjection:
    """Preserve the sparse evidence fields for unavailable footprint inventory."""
    report = source.report
    return CandidateEvidenceProjection(
        rule_id="pcb.schematic_component_inventory",
        evidence={
            "coverage_issue": (report.issue or "unavailable",),
            "netlist_sha256": (() if report.netlist_sha256 is None else (report.netlist_sha256,)),
            "board_path": (() if report.board_path is None else (report.board_path,)),
            "board_sha256": (() if report.board_sha256 is None else (report.board_sha256,)),
        },
    )


@dataclass(frozen=True, slots=True)
class PcbBlockedComponentInventoryCandidate(Candidate):
    """Blocked footprint-inventory finding retaining the typed coverage report."""

    source_evidence: PcbBlockedComponentInventoryEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: PcbBlockedComponentInventoryEvidence,
        *,
        subject: str,
        message: str,
    ) -> PcbBlockedComponentInventoryCandidate:
        projection = project_blocked_component_inventory_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_blocked_component_inventory_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id:
            raise ValueError("Blocked inventory rule must match its source evidence")
        if self.evidence != projection.evidence:
            raise ValueError("Blocked inventory evidence must match its typed projection")


def project_blocked_population_evidence(
    source: PcbBlockedComponentInventoryEvidence,
) -> CandidateEvidenceProjection:
    """Preserve the established DNP coverage evidence for blocked inventory."""
    report = source.report
    return CandidateEvidenceProjection(
        rule_id="pcb.schematic_pcb_dnp_mismatch",
        evidence={
            "coverage_issue": (report.issue or "unavailable",),
            "netlist_sha256": (() if report.netlist_sha256 is None else (report.netlist_sha256,)),
            "board_path": (() if report.board_path is None else (report.board_path,)),
            "board_sha256": (() if report.board_sha256 is None else (report.board_sha256,)),
            "snapshot_sha256": (
                () if report.snapshot_sha256 is None else (report.snapshot_sha256,)
            ),
        },
    )


@dataclass(frozen=True, slots=True)
class PcbBlockedPopulationCandidate(Candidate):
    """Blocked DNP finding retaining the same top-level coverage source."""

    source_evidence: PcbBlockedComponentInventoryEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: PcbBlockedComponentInventoryEvidence,
        *,
        subject: str,
        message: str,
    ) -> PcbBlockedPopulationCandidate:
        projection = project_blocked_population_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_blocked_population_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id:
            raise ValueError("Blocked population rule must match its source evidence")
        if self.evidence != projection.evidence:
            raise ValueError("Blocked population evidence must match its typed projection")
