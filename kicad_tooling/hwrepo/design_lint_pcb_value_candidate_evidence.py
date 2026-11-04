"""Typed source evidence and stable projection for PCB component value findings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .design_lint_pcb_variant_population_evidence import (
    project_named_variant_population_evidence,
)
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .pcb_component_inventory_models import (
    PcbComponentInventorySourceReceipt,
    PcbComponentValueMismatch,
    PcbVariantPopulationCoverage,
)


@dataclass(frozen=True, slots=True)
class PcbValueMismatchEvidence:
    """One text-value comparison with native and optional variant source identity."""

    observation: PcbComponentValueMismatch
    receipt: PcbComponentInventorySourceReceipt
    variant_population: PcbVariantPopulationCoverage


def project_pcb_value_mismatch_evidence(
    source: PcbValueMismatchEvidence,
) -> CandidateEvidenceProjection:
    """Project a typed value comparison and source receipt to stable report fields."""
    observation = source.observation
    receipt = source.receipt
    evidence: dict[str, tuple[str, ...]] = {
        "reference": (observation.reference,),
        "schematic_value": (observation.schematic_value,),
        "board_value": (observation.board_value,),
        "netlist_sha256": (receipt.netlist_sha256 or "unavailable",),
        "board_path": (receipt.board_path or "unavailable",),
        "board_sha256": (receipt.board_sha256 or "unavailable",),
        "snapshot_sha256": (receipt.snapshot_sha256 or "unavailable",),
        "snapshot_schema": (receipt.snapshot_schema or "unavailable",),
        "kicad_version": (receipt.kicad_version or "unavailable",),
        "image": (receipt.image or "unavailable",),
        "probe_sha256": (receipt.probe_sha256 or "unavailable",),
    }
    evidence.update(
        project_named_variant_population_evidence(
            observation.variant,
            source.variant_population,
            rule_id="pcb.schematic_pcb_value_mismatch",
        ).evidence
    )
    return CandidateEvidenceProjection(
        rule_id="pcb.schematic_pcb_value_mismatch",
        evidence=evidence,
    )


@dataclass(frozen=True, slots=True)
class PcbValueMismatchCandidate(Candidate):
    """Per-reference value finding retaining its typed comparison source."""

    source_evidence: PcbValueMismatchEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: PcbValueMismatchEvidence,
        *,
        subject: str,
        message: str,
    ) -> PcbValueMismatchCandidate:
        projection = project_pcb_value_mismatch_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_pcb_value_mismatch_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id:
            raise ValueError("PCB value rule must match its source evidence")
        if self.evidence != projection.evidence:
            raise ValueError("PCB value evidence must match its typed source projection")


@dataclass(frozen=True, slots=True)
class PcbBlockedValueComparisonEvidence:
    """Explicit blocked value coverage and its best available PCB source receipt."""

    issue: str
    receipt: PcbComponentInventorySourceReceipt
    inventory_status: Literal["BLOCKED", "COMPLETE"]
    coverage_status: Literal["BLOCKED"] = "BLOCKED"

    def __post_init__(self) -> None:
        if self.inventory_status not in {"BLOCKED", "COMPLETE"}:
            raise ValueError("PCB value comparison requires an explicit inventory state")
        if self.coverage_status != "BLOCKED":
            raise ValueError("PCB value comparison evidence requires BLOCKED coverage")
        if not self.issue:
            raise ValueError("Blocked PCB value comparison requires an issue")


def project_blocked_value_comparison_evidence(
    source: PcbBlockedValueComparisonEvidence,
) -> CandidateEvidenceProjection:
    """Project blocked value coverage without implying a successful comparison."""
    receipt = source.receipt
    if source.inventory_status == "BLOCKED":
        evidence = {
            "coverage_issue": (source.issue,),
            "netlist_sha256": (() if receipt.netlist_sha256 is None else (receipt.netlist_sha256,)),
            "board_path": (() if receipt.board_path is None else (receipt.board_path,)),
            "board_sha256": (() if receipt.board_sha256 is None else (receipt.board_sha256,)),
            "snapshot_sha256": (
                () if receipt.snapshot_sha256 is None else (receipt.snapshot_sha256,)
            ),
            "snapshot_schema": (
                () if receipt.snapshot_schema is None else (receipt.snapshot_schema,)
            ),
        }
    else:
        evidence = {
            "coverage_issue": (source.issue,),
            "netlist_sha256": (receipt.netlist_sha256 or "unavailable",),
            "board_path": (receipt.board_path or "unavailable",),
            "board_sha256": (receipt.board_sha256 or "unavailable",),
            "snapshot_sha256": (receipt.snapshot_sha256 or "unavailable",),
            "snapshot_schema": (receipt.snapshot_schema or "unavailable",),
            "kicad_version": (receipt.kicad_version or "unavailable",),
            "image": (receipt.image or "unavailable",),
            "probe_sha256": (receipt.probe_sha256 or "unavailable",),
        }
    return CandidateEvidenceProjection(
        rule_id="pcb.schematic_pcb_value_mismatch",
        evidence=evidence,
    )


@dataclass(frozen=True, slots=True)
class PcbBlockedValueComparisonCandidate(Candidate):
    """Coverage finding retaining its explicit blocked value source record."""

    source_evidence: PcbBlockedValueComparisonEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: PcbBlockedValueComparisonEvidence,
        *,
        subject: str,
        message: str,
    ) -> PcbBlockedValueComparisonCandidate:
        projection = project_blocked_value_comparison_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_blocked_value_comparison_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id:
            raise ValueError("PCB value rule must match its blocked coverage evidence")
        if self.evidence != projection.evidence:
            raise ValueError("Blocked value evidence must match its typed source projection")
