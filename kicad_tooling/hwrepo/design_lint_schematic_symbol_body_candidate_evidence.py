"""Typed source projections for schematic symbol-body obstruction candidates."""

from __future__ import annotations

from dataclasses import dataclass

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_schematic_geometry_candidate_evidence import (
    schematic_geometry_evidence,
    schematic_mm_box,
    schematic_mm_segment,
)
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .schematic_geometry_types import (
    FreeTextSymbolBodyOverlap,
    SchematicGeometryScan,
    WireThroughSymbolBody,
)

_FREE_TEXT_OVER_SYMBOL_BODY: DesignLintRuleId = "schematic.free_text_over_symbol_body"
_WIRE_THROUGH_SYMBOL_BODY: DesignLintRuleId = "schematic.wire_through_symbol_body"


@dataclass(frozen=True, slots=True)
class FreeTextSymbolBodyOverlapSource:
    """One text-to-body overlap retained from its containing scan."""

    scan: SchematicGeometryScan
    finding: FreeTextSymbolBodyOverlap

    def __post_init__(self) -> None:
        if not any(item is self.finding for item in self.scan.free_text_symbol_body_overlaps):
            raise ValueError("Text-body finding must be an observation from its source scan")


@dataclass(frozen=True, slots=True)
class WireThroughSymbolBodySource:
    """One wire-to-body overlap retained from its containing scan."""

    scan: SchematicGeometryScan
    finding: WireThroughSymbolBody

    def __post_init__(self) -> None:
        if not any(item is self.finding for item in self.scan.wires_through_symbol_bodies):
            raise ValueError("Wire-body finding must be an observation from its source scan")


SchematicSymbolBodyObstructionSource = FreeTextSymbolBodyOverlapSource | WireThroughSymbolBodySource


def project_schematic_symbol_body_evidence(
    source: SchematicSymbolBodyObstructionSource,
) -> CandidateEvidenceProjection:
    """Project a retained text or wire obstruction of a symbol body."""
    scan = source.scan
    evidence = schematic_geometry_evidence(scan, source.finding.sheet_instance_path)
    evidence["kicad_version"] = (scan.kicad_version,)

    if isinstance(source, FreeTextSymbolBodyOverlapSource):
        finding = source.finding
        evidence.update(
            {
                "text": (finding.text,),
                "text_uuid": (finding.text_uuid,),
                "text_box_mm": (schematic_mm_box(finding.text_box_mm),),
                "reference": (finding.reference,),
                "symbol_library_id": (finding.symbol_library_id,),
                "symbol_uuid": (finding.symbol_uuid,),
                "body_box_mm": (schematic_mm_box(finding.body_box_mm),),
                "overlap_box_mm": (schematic_mm_box(finding.overlap_box_mm),),
                "overlap_area_mm2": (f"{finding.overlap_area_mm2:.6f}",),
            }
        )
        rule_id = _FREE_TEXT_OVER_SYMBOL_BODY
    else:
        finding = source.finding
        pin_numbers = tuple(match.pin_number for match in finding.pin_endpoint_matches)
        pin_names = tuple(match.pin_name for match in finding.pin_endpoint_matches)
        pin_endpoints = tuple(
            f"{match.endpoint_mm[0]:.6f},{match.endpoint_mm[1]:.6f}"
            for match in finding.pin_endpoint_matches
        )
        evidence.update(
            {
                "reference": (finding.reference,),
                "symbol_library_id": (finding.symbol_library_id,),
                "symbol_uuid": (finding.symbol_uuid,),
                "body_box_mm": (schematic_mm_box(finding.body_box_mm),),
                "wire_uuid": (finding.wire_uuid,),
                "overlap_segment_mm": (
                    schematic_mm_segment(finding.overlap_start_mm, finding.overlap_end_mm),
                ),
                "overlap_length_mm": (f"{finding.overlap_length_mm:.6f}",),
                "pin_endpoint_numbers": pin_numbers,
                "pin_endpoint_names": pin_names,
                "pin_endpoint_mm": pin_endpoints,
            }
        )
        rule_id = _WIRE_THROUGH_SYMBOL_BODY

    return CandidateEvidenceProjection(rule_id=rule_id, evidence=evidence)


def _candidate_text(source: SchematicSymbolBodyObstructionSource) -> tuple[str, str]:
    if isinstance(source, FreeTextSymbolBodyOverlapSource):
        finding = source.finding
        message = (
            "A supported free-text glyph envelope overlaps a guarded symbol-body envelope. "
            "Review the rendered sheet; axis-aligned bounds can include empty space and do not "
            "establish electrical meaning."
        )
        return (
            f"free text {finding.text_uuid} overlaps {finding.reference} body envelope",
            message,
        )

    finding = source.finding
    pin_numbers = tuple(match.pin_number for match in finding.pin_endpoint_matches)
    pin_names = tuple(match.pin_name for match in finding.pin_endpoint_matches)
    pin_context = ""
    if pin_numbers:
        pins = ", ".join(
            f"{number} ({name})" for number, name in zip(pin_numbers, pin_names, strict=True)
        )
        pin_context = f" Endpoint coordinates match pin tip(s): {pins}."
    message = (
        "A schematic wire centerline runs through a guarded symbol-body envelope. "
        f"{pin_context} Review the rendered sheet; source-bound coordinates locate the overlap "
        "for project review."
    )
    return (
        f"wire {finding.wire_uuid} crosses {finding.reference} body envelope",
        message,
    )


@dataclass(frozen=True, slots=True)
class SchematicSymbolBodyObstructionCandidate(Candidate):
    """A body-obstruction candidate bound to the scan record that produced it."""

    source_evidence: SchematicSymbolBodyObstructionSource

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: SchematicSymbolBodyObstructionSource,
    ) -> SchematicSymbolBodyObstructionCandidate:
        projection = project_schematic_symbol_body_evidence(source_evidence)
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
        projection = project_schematic_symbol_body_evidence(self.source_evidence)
        subject, message = _candidate_text(self.source_evidence)
        if (
            self.rule_id != projection.rule_id
            or self.subject != subject
            or self.message != message
            or self.evidence != projection.evidence
        ):
            raise ValueError("Schematic body fields must match their typed source projection")
