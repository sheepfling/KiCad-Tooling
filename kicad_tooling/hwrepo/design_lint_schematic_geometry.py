"""Candidate translation for source-bound schematic geometry findings."""

from __future__ import annotations

from .design_lint_schematic_geometry_candidate_evidence import (
    LabelNearWireEndpointSource,
    PinTipOnWireInteriorSource,
    SchematicLabelEndpointCandidate,
    SchematicPinGeometryCandidate,
    SchematicWireTopologyCandidate,
    UnmarkedTJunctionSource,
    UnmarkedWireCrossingSource,
    WireEndOnPinLineSource,
    WireEndpointNearPinTipSource,
    schematic_geometry_evidence,
)
from .design_lint_types import Candidate
from .schematic_geometry import SchematicGeometryScan


def schematic_geometry_candidates(scan: SchematicGeometryScan) -> tuple[Candidate, ...]:
    """Translate each supported geometry observation into its review candidate."""
    found: list[Candidate] = []
    for item in scan.findings:
        found.append(
            SchematicPinGeometryCandidate.from_source_evidence(WireEndOnPinLineSource(scan, item))
        )
    for item in scan.pin_tip_on_wire_interiors:
        found.append(
            SchematicPinGeometryCandidate.from_source_evidence(
                PinTipOnWireInteriorSource(scan, item)
            )
        )
    for item in scan.wire_endpoints_near_pin_tips:
        found.append(
            SchematicPinGeometryCandidate.from_source_evidence(
                WireEndpointNearPinTipSource(scan, item)
            )
        )
    for item in scan.labels_near_wire_endpoints:
        found.append(
            SchematicLabelEndpointCandidate.from_source_evidence(
                LabelNearWireEndpointSource(scan, item)
            )
        )
    for item in scan.unmarked_wire_crossings:
        found.append(
            SchematicWireTopologyCandidate.from_source_evidence(
                UnmarkedWireCrossingSource(scan, item)
            )
        )
    for item in scan.unmarked_t_junctions:
        found.append(
            SchematicWireTopologyCandidate.from_source_evidence(UnmarkedTJunctionSource(scan, item))
        )
    for item in scan.coincident_text_anchors:
        x, y = item.anchor_mm
        found.append(
            Candidate(
                rule_id="schematic.coincident_text_anchors",
                subject=f"free-text anchors coincide at {x:.3f},{y:.3f} mm",
                message=(
                    "Two free-text objects use coincident insertion anchors. Review their "
                    "rendered placement; anchor coincidence alone does not prove glyph "
                    "overlap or a design error."
                ),
                evidence={
                    **schematic_geometry_evidence(scan, item.sheet_instance_path),
                    "anchor_mm": (f"{x:.6f},{y:.6f}",),
                    "first_text": (item.first_text,),
                    "first_text_uuid": (item.first_uuid,),
                    "second_text": (item.second_text,),
                    "second_text_uuid": (item.second_uuid,),
                    "kicad_version": (scan.kicad_version,),
                },
            )
        )
    for item in scan.free_text_overlaps:
        x0, y0, x1, y1 = item.overlap_box_mm
        found.append(
            Candidate(
                rule_id="schematic.free_text_overlap",
                subject=(f"free-text envelopes overlap: {item.first_uuid}, {item.second_uuid}"),
                message=(
                    "Two top-level free-text glyph envelopes overlap. Review the rendered "
                    "sheet; this approximate standard-font geometry is a drawing-quality "
                    "hint, not an electrical finding or an edit instruction."
                ),
                evidence={
                    **schematic_geometry_evidence(scan, item.sheet_instance_path),
                    "first_text": (item.first_text,),
                    "first_text_uuid": (item.first_uuid,),
                    "first_text_box_mm": (",".join(f"{value:.6f}" for value in item.first_box_mm),),
                    "second_text": (item.second_text,),
                    "second_text_uuid": (item.second_uuid,),
                    "second_text_box_mm": (
                        ",".join(f"{value:.6f}" for value in item.second_box_mm),
                    ),
                    "overlap_box_mm": (f"{x0:.6f},{y0:.6f},{x1:.6f},{y1:.6f}",),
                    "kicad_version": (scan.kicad_version,),
                },
            )
        )
    for item in scan.free_text_wire_overlaps:
        start_x, start_y = item.wire_segment_start_mm
        end_x, end_y = item.wire_segment_end_mm
        box = ",".join(f"{value:.6f}" for value in item.text_box_mm)
        found.append(
            Candidate(
                rule_id="schematic.free_text_over_wire",
                subject=f"wire {item.wire_uuid} crosses free-text envelope {item.text_uuid}",
                message=(
                    "A schematic wire centerline intersects a guarded free-text glyph envelope. "
                    "Review the rendered sheet; this approximate graphical finding does not "
                    "change connectivity or imply electrical intent."
                ),
                evidence={
                    **schematic_geometry_evidence(scan, item.sheet_instance_path),
                    "text": (item.text,),
                    "text_uuid": (item.text_uuid,),
                    "text_box_mm": (box,),
                    "wire_uuid": (item.wire_uuid,),
                    "overlap_segment_mm": (f"{start_x:.6f},{start_y:.6f},{end_x:.6f},{end_y:.6f}",),
                    "overlap_length_mm": (f"{item.overlap_length_mm:.6f}",),
                    "kicad_version": (scan.kicad_version,),
                },
            )
        )
    for item in scan.free_text_symbol_body_overlaps:
        overlap_box = ",".join(f"{value:.6f}" for value in item.overlap_box_mm)
        body_box = ",".join(f"{value:.6f}" for value in item.body_box_mm)
        text_box = ",".join(f"{value:.6f}" for value in item.text_box_mm)
        found.append(
            Candidate(
                rule_id="schematic.free_text_over_symbol_body",
                subject=f"free text {item.text_uuid} overlaps {item.reference} body envelope",
                message=(
                    "A supported free-text glyph envelope overlaps a guarded symbol-body "
                    "envelope. Review the rendered sheet; axis-aligned bounds can include "
                    "empty space and do not establish electrical meaning."
                ),
                evidence={
                    **schematic_geometry_evidence(scan, item.sheet_instance_path),
                    "text": (item.text,),
                    "text_uuid": (item.text_uuid,),
                    "text_box_mm": (text_box,),
                    "reference": (item.reference,),
                    "symbol_library_id": (item.symbol_library_id,),
                    "symbol_uuid": (item.symbol_uuid,),
                    "body_box_mm": (body_box,),
                    "overlap_box_mm": (overlap_box,),
                    "overlap_area_mm2": (f"{item.overlap_area_mm2:.6f}",),
                    "kicad_version": (scan.kicad_version,),
                },
            )
        )
    for item in scan.wires_through_symbol_bodies:
        start_x, start_y = item.overlap_start_mm
        end_x, end_y = item.overlap_end_mm
        body_box = ",".join(f"{value:.6f}" for value in item.body_box_mm)
        pin_numbers = tuple(match.pin_number for match in item.pin_endpoint_matches)
        pin_names = tuple(match.pin_name for match in item.pin_endpoint_matches)
        pin_endpoints = tuple(
            f"{match.endpoint_mm[0]:.6f},{match.endpoint_mm[1]:.6f}"
            for match in item.pin_endpoint_matches
        )
        pin_context = ""
        if pin_numbers:
            pins = ", ".join(
                f"{number} ({name})" for number, name in zip(pin_numbers, pin_names, strict=True)
            )
            pin_context = f" Endpoint coordinates match pin tip(s): {pins}."
        found.append(
            Candidate(
                rule_id="schematic.wire_through_symbol_body",
                subject=f"wire {item.wire_uuid} crosses {item.reference} body envelope",
                message=(
                    "A schematic wire centerline runs through a guarded symbol-body envelope. "
                    f"{pin_context} Review the rendered sheet; source-bound coordinates locate "
                    "the overlap for project review."
                ),
                evidence={
                    **schematic_geometry_evidence(scan, item.sheet_instance_path),
                    "reference": (item.reference,),
                    "symbol_library_id": (item.symbol_library_id,),
                    "symbol_uuid": (item.symbol_uuid,),
                    "body_box_mm": (body_box,),
                    "wire_uuid": (item.wire_uuid,),
                    "overlap_segment_mm": (f"{start_x:.6f},{start_y:.6f},{end_x:.6f},{end_y:.6f}",),
                    "overlap_length_mm": (f"{item.overlap_length_mm:.6f}",),
                    "pin_endpoint_numbers": pin_numbers,
                    "pin_endpoint_names": pin_names,
                    "pin_endpoint_mm": pin_endpoints,
                    "kicad_version": (scan.kicad_version,),
                },
            )
        )
    return tuple(found)
