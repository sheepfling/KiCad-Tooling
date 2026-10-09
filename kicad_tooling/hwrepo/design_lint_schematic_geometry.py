"""Candidate translation for source-bound schematic geometry findings."""

from __future__ import annotations

from .design_lint_types import Candidate
from .schematic_geometry import SchematicGeometryScan


def schematic_geometry_evidence(
    scan: SchematicGeometryScan,
    sheet_instance_path: str,
) -> dict[str, tuple[str, ...]]:
    """Bind a geometry finding to its exact sheet occurrence and source bytes."""
    binding = next(
        (item for item in scan.source_bindings if item.sheet_instance_path == sheet_instance_path),
        None,
    )
    source_path = scan.source_path if binding is None else binding.source_path
    source_sha256 = scan.source_sha256 if binding is None else binding.source_sha256
    evidence = {
        "schematic": (source_path,),
        "schematic_sha256": (source_sha256,),
        "sheet_instance_path": (sheet_instance_path,),
        "sheet_path": (" / ".join(binding.sheet_path) if binding is not None else "",),
        "schematic_root": (scan.source_path,),
        "schematic_root_sha256": (scan.source_sha256,),
        "schematic_tree_sha256": (scan.source_tree_sha256 or scan.source_sha256,),
    }
    return evidence


def schematic_geometry_candidates(scan: SchematicGeometryScan) -> tuple[Candidate, ...]:
    """Translate each supported geometry observation into its review candidate."""
    found: list[Candidate] = []
    for item in scan.findings:
        endpoint_x, endpoint_y = item.wire_endpoint_mm
        found.append(
            Candidate(
                rule_id="schematic.wire_end_on_pin_line",
                subject=f"{item.reference}.{item.pin_number}: wire endpoint on pin segment",
                message=(
                    "The native netlist marks this pin unconnected, while a wire endpoint lies "
                    "along its transformed pin segment. Review the schematic and intended "
                    "connection before changing the drawing."
                ),
                evidence={
                    **schematic_geometry_evidence(scan, item.sheet_instance_path),
                    "symbol": (item.symbol_library_id,),
                    "symbol_uuid": (item.symbol_uuid,),
                    "pin": (f"{item.reference}.{item.pin_number}",),
                    "pin_uuid": (item.pin_uuid or "<unavailable>",),
                    "pin_tip_mm": (f"{item.pin_tip_mm[0]:.6f},{item.pin_tip_mm[1]:.6f}",),
                    "wire_uuid": (item.wire_uuid,),
                    "wire_endpoint_mm": (f"{endpoint_x:.6f},{endpoint_y:.6f}",),
                    "distance_to_pin_tip_mm": (f"{item.distance_to_pin_tip_mm:.6f}",),
                    "distance_along_pin_mm": (f"{item.distance_along_pin_mm:.6f}",),
                    "kicad_version": (scan.kicad_version,),
                },
            )
        )
    for item in scan.pin_tip_on_wire_interiors:
        pin_x, pin_y = item.pin_tip_mm
        start_x, start_y = item.wire_segment_start_mm
        end_x, end_y = item.wire_segment_end_mm
        found.append(
            Candidate(
                rule_id="schematic.pin_tip_on_wire_interior",
                subject=f"{item.reference}.{item.pin_number}: pin tip on wire interior",
                message=(
                    "The native netlist marks this pin unconnected, although its tip lies on "
                    "the interior of a wire segment. Review whether a junction or explicit "
                    "connection is intended; the lint does not edit schematic geometry."
                ),
                evidence={
                    **schematic_geometry_evidence(scan, item.sheet_instance_path),
                    "symbol": (item.symbol_library_id,),
                    "symbol_uuid": (item.symbol_uuid,),
                    "pin": (f"{item.reference}.{item.pin_number}",),
                    "pin_uuid": (item.pin_uuid or "<unavailable>",),
                    "pin_tip_mm": (f"{pin_x:.6f},{pin_y:.6f}",),
                    "wire_uuid": (item.wire_uuid,),
                    "wire_segment_start_mm": (f"{start_x:.6f},{start_y:.6f}",),
                    "wire_segment_end_mm": (f"{end_x:.6f},{end_y:.6f}",),
                    "distance_to_wire_mm": (f"{item.distance_to_wire_mm:.6f}",),
                    "kicad_version": (scan.kicad_version,),
                },
            )
        )
    for item in scan.wire_endpoints_near_pin_tips:
        endpoint_x, endpoint_y = item.wire_endpoint_mm
        pin_x, pin_y = item.pin_tip_mm
        found.append(
            Candidate(
                rule_id="schematic.wire_endpoint_near_pin_tip",
                subject=f"{item.reference}.{item.pin_number}: wire endpoint near pin tip",
                message=(
                    "The native netlist marks this pin unconnected, and a wire endpoint is "
                    f"{item.distance_to_pin_tip_mm:.3f} mm from its tip. Review this near miss "
                    "and the native ERC finding; the lint does not connect or repair the "
                    "schematic."
                ),
                evidence={
                    **schematic_geometry_evidence(scan, item.sheet_instance_path),
                    "symbol": (item.symbol_library_id,),
                    "symbol_uuid": (item.symbol_uuid,),
                    "pin": (f"{item.reference}.{item.pin_number}",),
                    "pin_uuid": (item.pin_uuid or "<unavailable>",),
                    "pin_tip_mm": (f"{pin_x:.6f},{pin_y:.6f}",),
                    "wire_uuid": (item.wire_uuid,),
                    "wire_endpoint_mm": (f"{endpoint_x:.6f},{endpoint_y:.6f}",),
                    "distance_to_pin_tip_mm": (f"{item.distance_to_pin_tip_mm:.6f}",),
                    "kicad_version": (scan.kicad_version,),
                },
            )
        )
    for item in scan.labels_near_wire_endpoints:
        endpoint_evidence = tuple(
            f"{candidate.wire_uuid}@{candidate.wire_endpoint_mm[0]:.6f},"
            f"{candidate.wire_endpoint_mm[1]:.6f} "
            f"({candidate.distance_mm:.6f} mm)"
            for candidate in item.candidates
        )
        found.append(
            Candidate(
                rule_id="schematic.label_near_wire_endpoint",
                subject=f"{item.label_kind} {item.text!r}: near wire endpoint",
                message=(
                    "This label anchor misses nearby wire geometry but lies within the "
                    "heuristic's 1.27 mm review radius of a wire endpoint. Review whether the "
                    "label or wire should meet; the lint does not change the drawing."
                ),
                evidence={
                    **schematic_geometry_evidence(scan, item.sheet_instance_path),
                    "label_kind": (item.label_kind,),
                    "label_text": (item.text,),
                    "label_uuid": (item.label_uuid,),
                    "label_anchor_mm": (f"{item.anchor_mm[0]:.6f},{item.anchor_mm[1]:.6f}",),
                    "near_wire_endpoints": endpoint_evidence,
                    "kicad_version": (scan.kicad_version,),
                },
            )
        )
    for item in scan.unmarked_wire_crossings:
        x, y = item.crossing_mm
        found.append(
            Candidate(
                rule_id="schematic.unmarked_wire_crossing",
                subject=f"unmarked orthogonal wire crossing at {x:.3f},{y:.3f} mm",
                message=(
                    "Two wire interiors cross without a junction marker. Review whether the "
                    "signals should connect; intentional unconnected crossings are valid and "
                    "will also be reported."
                ),
                evidence={
                    **schematic_geometry_evidence(scan, item.sheet_instance_path),
                    "crossing_mm": (f"{x:.6f},{y:.6f}",),
                    "wire_uuids": item.wire_uuids,
                    "kicad_version": (scan.kicad_version,),
                },
            )
        )
    for item in scan.unmarked_t_junctions:
        x, y = item.junction_mm
        found.append(
            Candidate(
                rule_id="schematic.unmarked_t_junction",
                subject=f"unmarked T-junction at {x:.3f},{y:.3f} mm",
                message=(
                    "A wire endpoint touches the interior of another wire without a junction "
                    "marker. Review whether the branch should connect; this geometry hint "
                    "does not join or repair nets."
                ),
                evidence={
                    **schematic_geometry_evidence(scan, item.sheet_instance_path),
                    "junction_mm": (f"{x:.6f},{y:.6f}",),
                    "endpoint_wire_uuid": (item.endpoint_wire_uuid,),
                    "interior_wire_uuid": (item.interior_wire_uuid,),
                    "kicad_version": (scan.kicad_version,),
                },
            )
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
        found.append(
            Candidate(
                rule_id="schematic.wire_through_symbol_body",
                subject=f"wire {item.wire_uuid} crosses {item.reference} body envelope",
                message=(
                    "A schematic wire centerline runs through a guarded symbol-body envelope. "
                    "Review the rendered sheet; the bounding box is graphical evidence and "
                    "does not establish pin connectivity or design intent."
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
                    "kicad_version": (scan.kicad_version,),
                },
            )
        )
    return tuple(found)
