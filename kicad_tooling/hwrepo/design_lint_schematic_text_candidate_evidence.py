"""Typed source projections for schematic text-placement candidates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_schematic_geometry_candidate_evidence import (
    schematic_geometry_source_identity,
    schematic_mm_box,
    schematic_mm_segment,
)
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .schematic_geometry_types import (
    CoincidentTextAnchors,
    FreeTextOverlap,
    FreeTextWireOverlap,
    SchematicGeometryScan,
)

_COINCIDENT_TEXT_ANCHORS: DesignLintRuleId = "schematic.coincident_text_anchors"
_FREE_TEXT_OVERLAP: DesignLintRuleId = "schematic.free_text_overlap"
_FREE_TEXT_OVER_WIRE: DesignLintRuleId = "schematic.free_text_over_wire"


@dataclass(frozen=True, slots=True)
class CoincidentTextAnchorsSource:
    """Two free-text anchors retained from their containing scan."""

    scan: SchematicGeometryScan
    finding: CoincidentTextAnchors

    def __post_init__(self) -> None:
        if not any(item is self.finding for item in self.scan.coincident_text_anchors):
            raise ValueError("Text-anchor finding must be an observation from its source scan")


@dataclass(frozen=True, slots=True)
class FreeTextOverlapSource:
    """One overlapping pair of free-text envelopes retained from its scan."""

    scan: SchematicGeometryScan
    finding: FreeTextOverlap

    def __post_init__(self) -> None:
        if not any(item is self.finding for item in self.scan.free_text_overlaps):
            raise ValueError("Text-overlap finding must be an observation from its source scan")


@dataclass(frozen=True, slots=True)
class FreeTextWireOverlapSource:
    """One text and wire overlap retained from their containing scan."""

    scan: SchematicGeometryScan
    finding: FreeTextWireOverlap

    def __post_init__(self) -> None:
        if not any(item is self.finding for item in self.scan.free_text_wire_overlaps):
            raise ValueError("Text-wire finding must be an observation from its source scan")


SchematicTextGeometrySource: TypeAlias = (
    CoincidentTextAnchorsSource | FreeTextOverlapSource | FreeTextWireOverlapSource
)


def project_schematic_text_geometry_evidence(
    source: SchematicTextGeometrySource,
) -> CandidateEvidenceProjection:
    """Project a retained text-placement observation into stable report fields."""
    scan = source.scan
    evidence = dict(
        schematic_geometry_source_identity(scan, source.finding.sheet_instance_path).report_fields()
    )
    evidence["kicad_version"] = (scan.kicad_version,)

    if isinstance(source, CoincidentTextAnchorsSource):
        finding = source.finding
        evidence.update(
            {
                "anchor_mm": (f"{finding.anchor_mm[0]:.6f},{finding.anchor_mm[1]:.6f}",),
                "first_text": (finding.first_text,),
                "first_text_uuid": (finding.first_uuid,),
                "second_text": (finding.second_text,),
                "second_text_uuid": (finding.second_uuid,),
            }
        )
        rule_id = _COINCIDENT_TEXT_ANCHORS
    elif isinstance(source, FreeTextOverlapSource):
        finding = source.finding
        evidence.update(
            {
                "first_text": (finding.first_text,),
                "first_text_uuid": (finding.first_uuid,),
                "first_text_box_mm": (schematic_mm_box(finding.first_box_mm),),
                "second_text": (finding.second_text,),
                "second_text_uuid": (finding.second_uuid,),
                "second_text_box_mm": (schematic_mm_box(finding.second_box_mm),),
                "overlap_box_mm": (schematic_mm_box(finding.overlap_box_mm),),
            }
        )
        rule_id = _FREE_TEXT_OVERLAP
    else:
        finding = source.finding
        evidence.update(
            {
                "text": (finding.text,),
                "text_uuid": (finding.text_uuid,),
                "text_box_mm": (schematic_mm_box(finding.text_box_mm),),
                "wire_uuid": (finding.wire_uuid,),
                "overlap_segment_mm": (
                    schematic_mm_segment(
                        finding.wire_segment_start_mm,
                        finding.wire_segment_end_mm,
                    ),
                ),
                "overlap_length_mm": (f"{finding.overlap_length_mm:.6f}",),
            }
        )
        rule_id = _FREE_TEXT_OVER_WIRE

    return CandidateEvidenceProjection(rule_id=rule_id, evidence=evidence)


def _candidate_text(source: SchematicTextGeometrySource) -> tuple[str, str]:
    if isinstance(source, CoincidentTextAnchorsSource):
        finding = source.finding
        x, y = finding.anchor_mm
        message = (
            "Two free-text objects use coincident insertion anchors. Review their rendered "
            "placement; anchor coincidence alone does not prove glyph overlap or a design error."
        )
        return (
            f"free-text anchors coincide at {x:.3f},{y:.3f} mm",
            message,
        )
    if isinstance(source, FreeTextOverlapSource):
        finding = source.finding
        message = (
            "Two top-level free-text glyph envelopes overlap. Review the rendered sheet; this "
            "approximate standard-font geometry is a drawing-quality hint, not an electrical "
            "finding or an edit instruction."
        )
        return (
            f"free-text envelopes overlap: {finding.first_uuid}, {finding.second_uuid}",
            message,
        )
    finding = source.finding
    message = (
        "A schematic wire centerline intersects a guarded free-text glyph envelope. Review the "
        "rendered sheet; this approximate graphical finding does not change connectivity or "
        "imply electrical intent."
    )
    return (
        f"wire {finding.wire_uuid} crosses free-text envelope {finding.text_uuid}",
        message,
    )


@dataclass(frozen=True, slots=True)
class SchematicTextGeometryCandidate(Candidate):
    """A text-placement candidate bound to its exact source finding."""

    source_evidence: SchematicTextGeometrySource

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: SchematicTextGeometrySource,
    ) -> SchematicTextGeometryCandidate:
        projection = project_schematic_text_geometry_evidence(source_evidence)
        subject, message = _candidate_text(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_schematic_text_geometry_evidence(self.source_evidence)
        subject, message = _candidate_text(self.source_evidence)
        if (
            self.rule_id != projection.rule_id
            or self.subject != subject
            or self.message != message
            or self.evidence != projection.evidence
        ):
            raise ValueError("Schematic text fields must match their typed source projection")
