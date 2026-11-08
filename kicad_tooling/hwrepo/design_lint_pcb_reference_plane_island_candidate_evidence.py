"""Typed evidence projection for mapped reference-zone island reviews."""

from __future__ import annotations

import json
from dataclasses import dataclass

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .pcb_reference_plane_models import (
    PcbReferencePlaneCoverageEntry,
    PcbReferencePlaneCoverageReport,
    PcbReferencePlaneUnanchoredIsland,
)

RULE_ID: DesignLintRuleId = "pcb.reference_plane_unanchored_island"


@dataclass(frozen=True, slots=True)
class PcbReferencePlaneIslandFindingEvidence:
    """One unanchored island and its exact source-bound reference-plane report."""

    report: PcbReferencePlaneCoverageReport
    entry: PcbReferencePlaneCoverageEntry
    island: PcbReferencePlaneUnanchoredIsland

    def __post_init__(self) -> None:
        if self.report.status not in {"COMPLETE", "INCOMPLETE"}:
            raise ValueError("Reference-zone island evidence requires scanned coverage")
        if self.entry not in self.report.entries:
            raise ValueError("Reference-zone island evidence must belong to its source report")
        if not self.entry.review_unanchored_islands:
            raise ValueError("Reference-zone island review must be enabled by the project map")
        if self.island not in self.entry.unanchored_reference_islands:
            raise ValueError("Reference-zone island finding must belong to its mapped entry")


def project_reference_plane_island_evidence(
    source: PcbReferencePlaneIslandFindingEvidence,
) -> CandidateEvidenceProjection:
    """Project exact zone-island geometry and native source identities to report fields."""
    report, entry, island = source.report, source.entry, source.island
    return CandidateEvidenceProjection(
        rule_id=RULE_ID,
        evidence={
            "requirement_id": (entry.id,),
            "basis": (entry.basis,),
            "signal_net": (entry.signal_net,),
            "signal_layers": entry.signal_layers,
            "reference_net": (island.net,),
            "reference_layer": (island.layer,),
            "zone_uuid": (island.zone_uuid,),
            "island_index": (str(island.island.island_index),),
            "outline_nm": (json.dumps(island.island.outline_nm, separators=(",", ":")),),
            "holes_nm": (json.dumps(island.island.holes_nm, separators=(",", ":")),),
            "board_path": (str(report.board_path),),
            "board_sha256": (str(report.board_sha256),),
            "snapshot_sha256": (str(report.snapshot_sha256),),
            "probe_sha256": (str(report.probe_sha256),),
            "kicad_version": (str(report.kicad_version),),
            "image": (str(report.image),),
            "map_sha256": (str(report.map_sha256),),
            "netlist_sha256": (str(report.netlist_sha256),),
            "interpretation": (
                (
                    "The native snapshot found no direct pad anchor on this filled island. "
                    "It may still connect through tracks or vias; this evidence does not "
                    "establish electrical isolation or a defect."
                ),
            ),
        },
    )


@dataclass(frozen=True, slots=True)
class PcbReferencePlaneIslandCandidate(Candidate):
    """Default-review candidate for one mapped reference-zone island without a pad anchor."""

    source_evidence: PcbReferencePlaneIslandFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: PcbReferencePlaneIslandFindingEvidence,
    ) -> PcbReferencePlaneIslandCandidate:
        projection = project_reference_plane_island_evidence(source_evidence)
        island = source_evidence.island
        return cls(
            rule_id=projection.rule_id,
            subject=(
                f"{source_evidence.entry.id}: {island.net} zone {island.zone_uuid} "
                f"{island.layer} island {island.island.island_index}"
            ),
            message=(
                "Review this mapped reference-net filled island: the native snapshot found no "
                "direct pad anchor. It may still connect through tracks or vias; the finding "
                "does not establish electrical isolation, a defect, or return-current adequacy."
            ),
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_reference_plane_island_evidence(self.source_evidence)
        island = self.source_evidence.island
        expected_subject = (
            f"{self.source_evidence.entry.id}: {island.net} zone {island.zone_uuid} "
            f"{island.layer} island {island.island.island_index}"
        )
        expected_message = (
            "Review this mapped reference-net filled island: the native snapshot found no "
            "direct pad anchor. It may still connect through tracks or vias; the finding "
            "does not establish electrical isolation, a defect, or return-current adequacy."
        )
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("Reference-zone island evidence must match its source projection")
        if (self.subject, self.message) != (expected_subject, expected_message):
            raise ValueError("Reference-zone island text must match its source evidence")
