"""Typed source evidence and stable projection for PCB footprint inventory findings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from .design_lint_types import Candidate, CandidateEvidenceProjection
from .pcb_component_inventory_models import (
    PcbComponentInventorySourceReceipt,
    PcbFootprintIdentityMismatch,
    PcbMissingFootprintPlacement,
)

_RULE_ID = "pcb.schematic_component_inventory"


PcbInventoryObservation: TypeAlias = PcbMissingFootprintPlacement | PcbFootprintIdentityMismatch


@dataclass(frozen=True, slots=True)
class PcbInventorySourceEvidence:
    """One typed footprint comparison and the source receipt it came from."""

    observation: PcbInventoryObservation
    receipt: PcbComponentInventorySourceReceipt


def project_pcb_inventory_evidence(
    source: PcbInventorySourceEvidence,
) -> CandidateEvidenceProjection:
    """Map a typed footprint comparison and native receipt to stable report fields."""
    observation = source.observation
    receipt = source.receipt
    evidence = {
        "reference": (observation.reference,),
        "assigned_footprint": (observation.assigned_footprint,),
        "netlist_sha256": (receipt.netlist_sha256 or "unavailable",),
        "board_path": (receipt.board_path or "unavailable",),
        "board_sha256": (receipt.board_sha256 or "unavailable",),
        "snapshot_sha256": (receipt.snapshot_sha256 or "unavailable",),
        "snapshot_schema": (receipt.snapshot_schema or "unavailable",),
        "kicad_version": (receipt.kicad_version or "unavailable",),
        "image": (receipt.image or "unavailable",),
        "probe_sha256": (receipt.probe_sha256 or "unavailable",),
    }
    if isinstance(observation, PcbFootprintIdentityMismatch):
        evidence["placed_footprint"] = (observation.placed_footprint,)
    return CandidateEvidenceProjection(rule_id=_RULE_ID, evidence=evidence)


@dataclass(frozen=True, slots=True)
class PcbInventoryCandidate(Candidate):
    """PCB footprint finding retaining its comparison and source receipt."""

    source_evidence: PcbInventorySourceEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: PcbInventorySourceEvidence,
        *,
        subject: str,
        message: str,
    ) -> PcbInventoryCandidate:
        projection = project_pcb_inventory_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_pcb_inventory_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id:
            raise ValueError("PCB inventory rule must match its source evidence")
        if self.evidence != projection.evidence:
            raise ValueError("PCB inventory evidence must match its typed source projection")
