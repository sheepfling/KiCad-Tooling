"""Typed source evidence and report projections for PCB pad-net findings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .pcb_component_inventory_models import PcbComponentInventorySourceReceipt
from .pcb_pad_net_models import PcbSchematicBoardPadNetMismatch

RULE_ID: DesignLintRuleId = "pcb.schematic_pcb_pad_net_mismatch"


@dataclass(frozen=True, slots=True)
class PcbPadNetMismatchEvidence:
    """One exact pin-to-pad comparison with its source receipt."""

    observation: PcbSchematicBoardPadNetMismatch
    receipt: PcbComponentInventorySourceReceipt


def project_pcb_pad_net_mismatch_evidence(
    source: PcbPadNetMismatchEvidence,
) -> CandidateEvidenceProjection:
    """Project a typed pad-net mismatch into the established report fields."""
    item = source.observation
    evidence = _source_receipt_fields(source.receipt)
    evidence.update(
        {
            "reference": (item.reference,),
            "pin": (item.pin,),
            "mismatch": (item.mismatch,),
            "schematic_net": (item.schematic_net or "unconnected",),
            "board_net": (item.board_net or "unassigned",),
        }
    )
    return CandidateEvidenceProjection(rule_id=RULE_ID, evidence=evidence)


@dataclass(frozen=True, slots=True)
class PcbPadNetMismatchCandidate(Candidate):
    """Pad-net candidate retaining the typed mismatch and native source receipt."""

    source_evidence: PcbPadNetMismatchEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: PcbPadNetMismatchEvidence,
        *,
        subject: str,
        message: str,
    ) -> PcbPadNetMismatchCandidate:
        projection = project_pcb_pad_net_mismatch_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_pcb_pad_net_mismatch_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id:
            raise ValueError("PCB pad-net rule must match its typed source evidence")
        if self.evidence != projection.evidence:
            raise ValueError("PCB pad-net evidence must match its typed projection")


@dataclass(frozen=True, slots=True)
class PcbBlockedPadNetComparisonEvidence:
    """A blocked pad-net comparison and the source identity available to it."""

    issue: str
    receipt: PcbComponentInventorySourceReceipt
    inventory_status: Literal["NOT_APPLICABLE", "COMPLETE", "BLOCKED", "DISABLED"]
    comparison_status: Literal["BLOCKED"] = "BLOCKED"

    def __post_init__(self) -> None:
        if not self.issue.strip():
            raise ValueError("Blocked PCB pad-net evidence must explain the comparison gap")


def project_blocked_pcb_pad_net_evidence(
    source: PcbBlockedPadNetComparisonEvidence,
) -> CandidateEvidenceProjection:
    """Project blocked comparison state without implying a clean pad-net result."""
    evidence = _source_receipt_fields(source.receipt)
    evidence["coverage_issue"] = (source.issue,)
    return CandidateEvidenceProjection(rule_id=RULE_ID, evidence=evidence)


@dataclass(frozen=True, slots=True)
class PcbBlockedPadNetComparisonCandidate(Candidate):
    """Blocked pad-net finding retaining comparison and inventory states."""

    source_evidence: PcbBlockedPadNetComparisonEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: PcbBlockedPadNetComparisonEvidence,
        *,
        subject: str,
        message: str,
    ) -> PcbBlockedPadNetComparisonCandidate:
        projection = project_blocked_pcb_pad_net_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_blocked_pcb_pad_net_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id:
            raise ValueError("Blocked PCB pad-net rule must match its source evidence")
        if self.evidence != projection.evidence:
            raise ValueError("Blocked PCB pad-net evidence must match its typed projection")


def _source_receipt_fields(
    receipt: PcbComponentInventorySourceReceipt,
) -> dict[str, tuple[str, ...]]:
    """Format the common native receipt fields used by this rule's wire contract."""
    return {
        "netlist_sha256": (receipt.netlist_sha256 or "unavailable",),
        "board_path": (receipt.board_path or "unavailable",),
        "board_sha256": (receipt.board_sha256 or "unavailable",),
        "snapshot_sha256": (receipt.snapshot_sha256 or "unavailable",),
        "snapshot_schema": (receipt.snapshot_schema or "unavailable",),
        "kicad_version": (receipt.kicad_version or "unavailable",),
        "image": (receipt.image or "unavailable",),
        "probe_sha256": (receipt.probe_sha256 or "unavailable",),
    }
