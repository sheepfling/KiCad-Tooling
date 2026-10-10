"""Text and wire obstruction checks around visible symbol bodies."""

from __future__ import annotations

from .model_inventory import _Span  # pyright: ignore[reportPrivateUsage]
from .schematic_geometry_primitives import clip_segment_to_box
from .schematic_geometry_source import schematic_nodes
from .schematic_geometry_types import (
    SYMBOL_BODY_WIRE_GUARD_MM,
    SYMBOL_BODY_WIRE_LENGTH_EPSILON_MM,
    SYMBOL_BODY_WIRE_MIN_OVERLAP_MM,
    TEXT_BODY_AREA_EPSILON_MM2,
    TEXT_BODY_MIN_OVERLAP_AREA_MM2,
    TEXT_BODY_SYMBOL_GUARD_MM,
    TEXT_BODY_TEXT_GUARD_MM,
    TEXT_WIRE_GUARD_MM,
    TEXT_WIRE_LENGTH_EPSILON_MM,
    TEXT_WIRE_MIN_OVERLAP_MM,
    FreeTextGeometry,
    FreeTextSymbolBodyOverlap,
    FreeTextWireOverlap,
    SymbolBodyEnvelope,
    WireSegment,
    WireThroughSymbolBody,
)
from .schematic_text_geometry import free_text_box_mm, schematic_text_metrics


def wire_through_symbol_bodies(
    bodies: tuple[SymbolBodyEnvelope, ...],
    wire_segments: tuple[WireSegment, ...],
    *,
    sheet_instance_path: str,
) -> tuple[WireThroughSymbolBody, ...]:
    """Find wire centerlines with substantial overlap inside a guarded body box."""
    findings: list[WireThroughSymbolBody] = []
    for body in bodies:
        x0, y0, x1, y1 = body.box_mm
        guarded_box = (
            x0 + SYMBOL_BODY_WIRE_GUARD_MM,
            y0 + SYMBOL_BODY_WIRE_GUARD_MM,
            x1 - SYMBOL_BODY_WIRE_GUARD_MM,
            y1 - SYMBOL_BODY_WIRE_GUARD_MM,
        )
        if guarded_box[0] >= guarded_box[2] or guarded_box[1] >= guarded_box[3]:
            continue
        for segment in wire_segments:
            clipped = clip_segment_to_box(segment.start, segment.end, guarded_box)
            if clipped is None:
                continue
            start, end, length = clipped
            if length + SYMBOL_BODY_WIRE_LENGTH_EPSILON_MM < (SYMBOL_BODY_WIRE_MIN_OVERLAP_MM):
                continue
            findings.append(
                WireThroughSymbolBody(
                    reference=body.reference,
                    symbol_library_id=body.library_id,
                    symbol_uuid=body.symbol_uuid,
                    wire_uuid=segment.uuid,
                    body_box_mm=body.box_mm,
                    overlap_start_mm=(round(start[0], 6), round(start[1], 6)),
                    overlap_end_mm=(round(end[0], 6), round(end[1], 6)),
                    overlap_length_mm=round(length, 6),
                    sheet_instance_path=sheet_instance_path,
                )
            )
    findings.sort(
        key=lambda item: (
            item.sheet_instance_path,
            item.reference,
            item.symbol_uuid,
            item.wire_uuid,
            item.overlap_start_mm,
        )
    )
    return tuple(findings)


def free_text_wire_overlaps(
    source: str,
    root: _Span,
    wire_segments: tuple[WireSegment, ...],
    *,
    sheet_instance_path: str,
) -> tuple[tuple[FreeTextWireOverlap, ...], tuple[str, ...]]:
    """Find wire centerlines that cross a guarded standard free-text envelope."""
    metrics = schematic_text_metrics()
    geometries: list[FreeTextGeometry] = []
    unsupported: list[str] = []
    for node in schematic_nodes(source, root, "text"):
        try:
            anchor, box = free_text_box_mm(source, node, metrics)
        except ValueError as exc:
            unsupported.append(f"Free-text wire-overlap geometry is unsupported: {exc}")
            continue
        geometries.append(FreeTextGeometry(anchor, box))

    uuid_counts: dict[str, int] = {}
    for geometry in geometries:
        uuid_counts[geometry.anchor.uuid] = uuid_counts.get(geometry.anchor.uuid, 0) + 1
    duplicate_uuids = {uuid for uuid, count in uuid_counts.items() if count > 1}
    unsupported.extend(f"Duplicate free-text UUID: {uuid}" for uuid in sorted(duplicate_uuids))
    geometries = [
        geometry for geometry in geometries if geometry.anchor.uuid not in duplicate_uuids
    ]

    findings: list[FreeTextWireOverlap] = []
    for geometry in geometries:
        x0, y0, x1, y1 = geometry.box_mm
        guarded_box = (
            x0 + TEXT_WIRE_GUARD_MM,
            y0 + TEXT_WIRE_GUARD_MM,
            x1 - TEXT_WIRE_GUARD_MM,
            y1 - TEXT_WIRE_GUARD_MM,
        )
        if guarded_box[0] >= guarded_box[2] or guarded_box[1] >= guarded_box[3]:
            continue
        for segment in wire_segments:
            clipped = clip_segment_to_box(segment.start, segment.end, guarded_box)
            if clipped is None:
                continue
            clipped_start, clipped_end, overlap_length = clipped
            if overlap_length + TEXT_WIRE_LENGTH_EPSILON_MM < TEXT_WIRE_MIN_OVERLAP_MM:
                continue
            findings.append(
                FreeTextWireOverlap(
                    text=geometry.anchor.text,
                    text_uuid=geometry.anchor.uuid,
                    text_box_mm=geometry.box_mm,
                    wire_uuid=segment.uuid,
                    wire_segment_start_mm=(
                        round(clipped_start[0], 6),
                        round(clipped_start[1], 6),
                    ),
                    wire_segment_end_mm=(round(clipped_end[0], 6), round(clipped_end[1], 6)),
                    overlap_length_mm=round(overlap_length, 6),
                    sheet_instance_path=sheet_instance_path,
                )
            )
    findings.sort(
        key=lambda item: (
            item.sheet_instance_path,
            item.text_uuid,
            item.wire_uuid,
            item.wire_segment_start_mm,
            item.wire_segment_end_mm,
        )
    )
    return tuple(findings), tuple(sorted(set(unsupported)))


def free_text_over_symbol_bodies(
    source: str,
    root: _Span,
    bodies: tuple[SymbolBodyEnvelope, ...],
    *,
    sheet_instance_path: str,
) -> tuple[tuple[FreeTextSymbolBodyOverlap, ...], tuple[str, ...]]:
    """Find supported top-level free-text envelopes inside symbol-body bounds."""
    metrics = schematic_text_metrics()
    geometries: list[FreeTextGeometry] = []
    unsupported: list[str] = []
    for node in schematic_nodes(source, root, "text"):
        try:
            anchor, box = free_text_box_mm(source, node, metrics)
        except ValueError as exc:
            unsupported.append(f"Free-text body-overlap geometry is unsupported: {exc}")
            continue
        geometries.append(FreeTextGeometry(anchor, box))

    uuid_counts: dict[str, int] = {}
    for geometry in geometries:
        uuid_counts[geometry.anchor.uuid] = uuid_counts.get(geometry.anchor.uuid, 0) + 1
    duplicate_uuids = {uuid for uuid, count in uuid_counts.items() if count > 1}
    unsupported.extend(f"Duplicate free-text UUID: {uuid}" for uuid in sorted(duplicate_uuids))
    geometries = [
        geometry for geometry in geometries if geometry.anchor.uuid not in duplicate_uuids
    ]

    findings: list[FreeTextSymbolBodyOverlap] = []
    for geometry in geometries:
        x0, y0, x1, y1 = geometry.box_mm
        text_box = (
            x0 + TEXT_BODY_TEXT_GUARD_MM,
            y0 + TEXT_BODY_TEXT_GUARD_MM,
            x1 - TEXT_BODY_TEXT_GUARD_MM,
            y1 - TEXT_BODY_TEXT_GUARD_MM,
        )
        if text_box[0] >= text_box[2] or text_box[1] >= text_box[3]:
            continue
        for body in bodies:
            bx0, by0, bx1, by1 = body.box_mm
            body_box = (
                bx0 + TEXT_BODY_SYMBOL_GUARD_MM,
                by0 + TEXT_BODY_SYMBOL_GUARD_MM,
                bx1 - TEXT_BODY_SYMBOL_GUARD_MM,
                by1 - TEXT_BODY_SYMBOL_GUARD_MM,
            )
            if body_box[0] >= body_box[2] or body_box[1] >= body_box[3]:
                continue
            overlap = (
                max(text_box[0], body_box[0]),
                max(text_box[1], body_box[1]),
                min(text_box[2], body_box[2]),
                min(text_box[3], body_box[3]),
            )
            if overlap[0] >= overlap[2] or overlap[1] >= overlap[3]:
                continue
            overlap_area = (overlap[2] - overlap[0]) * (overlap[3] - overlap[1])
            if overlap_area + TEXT_BODY_AREA_EPSILON_MM2 < TEXT_BODY_MIN_OVERLAP_AREA_MM2:
                continue
            findings.append(
                FreeTextSymbolBodyOverlap(
                    text=geometry.anchor.text,
                    text_uuid=geometry.anchor.uuid,
                    text_box_mm=geometry.box_mm,
                    reference=body.reference,
                    symbol_library_id=body.library_id,
                    symbol_uuid=body.symbol_uuid,
                    body_box_mm=body.box_mm,
                    overlap_box_mm=(
                        round(overlap[0], 6),
                        round(overlap[1], 6),
                        round(overlap[2], 6),
                        round(overlap[3], 6),
                    ),
                    overlap_area_mm2=round(overlap_area, 6),
                    sheet_instance_path=sheet_instance_path,
                )
            )
    findings.sort(
        key=lambda item: (
            item.sheet_instance_path,
            item.reference,
            item.symbol_uuid,
            item.text_uuid,
            item.overlap_box_mm,
        )
    )
    return tuple(findings), tuple(sorted(set(unsupported)))
