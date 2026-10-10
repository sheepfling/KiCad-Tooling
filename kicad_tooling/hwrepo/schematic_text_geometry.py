"""Free-text anchor and glyph-envelope review heuristics."""

from __future__ import annotations

import math
from functools import lru_cache
from importlib.resources import files

from .contracts import parse_model_text
from .model_inventory import _atoms, _Span  # pyright: ignore[reportPrivateUsage]
from .models import SchematicTextMetricsResource
from .schematic_geometry_source import schematic_at, schematic_nodes, schematic_number
from .schematic_geometry_types import (
    POINT_TOLERANCE_MM,
    TEXT_MARKUP,
    TEXT_OVERLAP_GUARD_MM,
    TEXT_OVERLAP_MIN_AREA_MM2,
    CoincidentTextAnchors,
    FreeTextGeometry,
    FreeTextOverlap,
    SchematicTextMetrics,
    TextAnchor,
)


def coincident_text_anchors(
    source: str,
    root: _Span,
) -> tuple[tuple[CoincidentTextAnchors, ...], tuple[str, ...]]:
    """Report free-text objects whose insertion anchors coincide within tolerance.

    This intentionally does not estimate rendered glyph bounds. The result is a
    review prompt about coincident source anchors, not a claim that text overlaps
    or that either placement is unintended.
    """
    anchors: list[TextAnchor] = []
    unsupported: list[str] = []
    for node in schematic_nodes(source, root, "text"):
        atoms = _atoms(source, node)
        uuids = schematic_nodes(source, node, "uuid")
        if len(atoms) < 2 or not atoms[1].strip() or len(uuids) != 1:
            unsupported.append("free text without non-empty content or one unique UUID")
            continue
        uuid_atoms = _atoms(source, uuids[0])
        if len(uuid_atoms) != 2 or not uuid_atoms[1]:
            unsupported.append("free text with malformed UUID")
            continue
        try:
            x, y, _angle = schematic_at(source, node, angle_required=True)
        except ValueError as exc:
            unsupported.append(f"free text {uuid_atoms[1]} has invalid anchor: {exc}")
            continue
        anchors.append(TextAnchor(atoms[1], uuid_atoms[1], (x, y)))

    uuid_counts: dict[str, int] = {}
    for anchor in anchors:
        uuid_counts[anchor.uuid] = uuid_counts.get(anchor.uuid, 0) + 1
    duplicate_uuids = {uuid for uuid, count in uuid_counts.items() if count > 1}
    unsupported.extend(f"duplicate free-text UUID: {uuid}" for uuid in sorted(duplicate_uuids))
    anchors = [anchor for anchor in anchors if anchor.uuid not in duplicate_uuids]
    anchors.sort(key=lambda item: (item.point, item.uuid, item.text))

    findings: list[CoincidentTextAnchors] = []
    for index, first in enumerate(anchors):
        for second in anchors[index + 1 :]:
            if second.point[0] - first.point[0] > POINT_TOLERANCE_MM:
                break
            if math.dist(first.point, second.point) <= POINT_TOLERANCE_MM:
                findings.append(
                    CoincidentTextAnchors(
                        first_text=first.text,
                        first_uuid=first.uuid,
                        second_text=second.text,
                        second_uuid=second.uuid,
                        anchor_mm=first.point,
                    )
                )
    findings.sort(key=lambda item: (item.anchor_mm, item.first_uuid, item.second_uuid))
    return tuple(findings), tuple(unsupported)


@lru_cache(maxsize=1)
def schematic_text_metrics() -> SchematicTextMetrics:
    """Read bounded KiCad 10.0.6 standard-stroke metrics measured from native SVG."""
    content = (
        files("kicad_tooling.hwrepo")
        .joinpath("schematic-text-metrics.json")
        .read_text(encoding="utf-8")
    )
    document = parse_model_text(content, SchematicTextMetricsResource)
    top_ratio, bottom_ratio = document.vertical_ink_envelope_ratio
    return SchematicTextMetrics(
        advances_mm=dict(document.advances_mm),
        reference_size_mm=document.reference_size_mm,
        single_glyph_end_spacing_mm=document.single_glyph_svg_end_spacing_mm,
        line_end_spacing_mm=document.line_end_spacing_mm,
        multiline_line_spacing_mm=document.multiline_line_spacing_mm,
        vertical_top_ratio=top_ratio,
        vertical_bottom_ratio=bottom_ratio,
        stroke_width_mm=document.stroke_width_mm,
    )


def free_text_lines(source: str, node: _Span) -> tuple[str, ...]:
    """Decode KiCad's escaped plain-text line breaks without confusing ``\\n``."""
    position = node.start + 1
    while position < node.end - 1 and source[position].isspace():
        position += 1
    token_start = position
    while (
        position < node.end - 1 and not source[position].isspace() and source[position] not in "()"
    ):
        position += 1
    if source[token_start:position] != "text":
        raise ValueError("free-text object has an unsupported content node")
    while position < node.end - 1 and source[position].isspace():
        position += 1
    if position >= node.end - 1 or source[position] != '"':
        raise ValueError("free text content is not one quoted string")

    position += 1
    lines: list[list[str]] = [[]]
    closed = False
    while position < node.end - 1:
        character = source[position]
        if character == '"':
            closed = True
            break
        if character in "\r\n":
            raise ValueError("literal source line breaks inside free text are unsupported")
        if character == "\\":
            if position + 1 >= node.end - 1:
                raise ValueError("free text ends with an incomplete escape")
            escaped = source[position + 1]
            if escaped == "n":
                lines.append([])
            elif escaped in {"\\", '"'}:
                lines[-1].append(escaped)
            elif escaped == "r":
                raise ValueError("carriage-return escapes in free text are unsupported")
            else:
                lines[-1].extend(("\\", escaped))
            position += 2
            continue
        lines[-1].append(character)
        position += 1

    if not closed:
        raise ValueError("free text has an unterminated quoted string")
    decoded = tuple("".join(line) for line in lines)
    if not any(line.strip() for line in decoded):
        raise ValueError("free text needs at least one non-empty line")
    return decoded


def free_text_box_mm(
    source: str,
    node: _Span,
    metrics: SchematicTextMetrics,
) -> tuple[TextAnchor, tuple[float, float, float, float]]:
    atoms = _atoms(source, node)
    uuids = schematic_nodes(source, node, "uuid")
    if len(atoms) < 2 or not atoms[1].strip() or len(uuids) != 1:
        raise ValueError("free text needs non-empty content and one unique UUID")
    uuid_atoms = _atoms(source, uuids[0])
    if len(uuid_atoms) != 2 or not uuid_atoms[1]:
        raise ValueError("free text has a malformed UUID")
    text_lines = free_text_lines(source, node)
    text_value = "\n".join(text_lines)
    if TEXT_MARKUP.search(text_value):
        raise ValueError("formatted free text is outside the measured geometry")
    if any(character not in metrics.advances_mm for line in text_lines for character in line):
        raise ValueError("free text contains glyphs outside the measured standard-stroke set")

    x, y, angle = schematic_at(source, node, angle_required=True)
    if angle != 0.0:
        raise ValueError("free-text rotation must be horizontal")
    effects = schematic_nodes(source, node, "effects")
    if len(effects) != 1:
        raise ValueError("free text must have one effects section")
    fonts = schematic_nodes(source, effects[0], "font")
    if len(fonts) != 1:
        raise ValueError("free text must use one standard font section")
    font = fonts[0]
    if any(schematic_nodes(source, font, name) for name in ("face", "bold", "italic", "thickness")):
        raise ValueError("custom, bold, italic, or thick free text is outside the measured font")
    sizes = schematic_nodes(source, font, "size")
    if len(sizes) != 1:
        raise ValueError("free text must have one explicit font size")
    size_atoms = _atoms(source, sizes[0])
    if len(size_atoms) != 3:
        raise ValueError("free-text font size must contain width and height")
    size_width = schematic_number(size_atoms[1], "free-text width")
    size_height = schematic_number(size_atoms[2], "free-text height")
    if size_width <= 0.0 or size_height <= 0.0:
        raise ValueError("free-text font size must be positive")

    justify_nodes = schematic_nodes(source, effects[0], "justify")
    horizontal_justification = "center"
    if justify_nodes:
        if len(justify_nodes) != 1:
            raise ValueError("free text must have at most one justification field")
        justification_atoms = _atoms(source, justify_nodes[0])
        options = justification_atoms[1:]
        if options == ():
            horizontal_justification = "center"
        elif options == ("left",):
            horizontal_justification = "left"
        elif options == ("right",):
            horizontal_justification = "right"
        else:
            raise ValueError(
                "free-text justification must be horizontal left or right; "
                "vertical alignment and mirrored text are outside the measured geometry"
            )

    scale_x = size_width / metrics.reference_size_mm
    scale_y = size_height / metrics.reference_size_mm
    line_widths = tuple(
        (
            sum(metrics.advances_mm[character] for character in line)
            + (
                metrics.single_glyph_end_spacing_mm
                if len(line) == 1
                else metrics.line_end_spacing_mm
            )
        )
        * scale_x
        if line
        else 0.0
        for line in text_lines
    )
    width = max(line_widths)
    stroke = metrics.stroke_width_mm * scale_y
    if horizontal_justification == "left":
        left, right = 0.0, width
    elif horizontal_justification == "right":
        left, right = -width, 0.0
    else:
        left, right = -width / 2.0, width / 2.0
    line_spacing = metrics.multiline_line_spacing_mm * scale_y
    row_offsets = tuple(
        (index - (len(text_lines) - 1) / 2.0) * line_spacing for index in range(len(text_lines))
    )
    top = min(row_offsets) + metrics.vertical_top_ratio * size_height - stroke / 2.0
    bottom = max(row_offsets) + metrics.vertical_bottom_ratio * size_height + stroke / 2.0
    box = (round(x + left, 6), round(y + top, 6), round(x + right, 6), round(y + bottom, 6))
    return TextAnchor(text_value, uuid_atoms[1], (x, y)), box


def free_text_overlaps(
    source: str,
    root: _Span,
) -> tuple[tuple[FreeTextOverlap, ...], tuple[str, ...]]:
    """Find likely text-envelope collisions using the pinned standard-stroke metrics."""
    metrics = schematic_text_metrics()
    geometries: list[FreeTextGeometry] = []
    unsupported: list[str] = []
    for node in schematic_nodes(source, root, "text"):
        try:
            anchor, box = free_text_box_mm(source, node, metrics)
        except ValueError as exc:
            unsupported.append(f"Free-text overlap geometry is unsupported: {exc}")
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
    geometries.sort(
        key=lambda item: (item.box_mm[0], item.box_mm[1], item.anchor.uuid, item.anchor.text)
    )

    findings: list[FreeTextOverlap] = []
    for index, first in enumerate(geometries):
        first_box = first.box_mm
        first_interior = (
            first_box[0] + TEXT_OVERLAP_GUARD_MM,
            first_box[1] + TEXT_OVERLAP_GUARD_MM,
            first_box[2] - TEXT_OVERLAP_GUARD_MM,
            first_box[3] - TEXT_OVERLAP_GUARD_MM,
        )
        if first_interior[0] >= first_interior[2] or first_interior[1] >= first_interior[3]:
            continue
        for second in geometries[index + 1 :]:
            second_box = second.box_mm
            second_interior = (
                second_box[0] + TEXT_OVERLAP_GUARD_MM,
                second_box[1] + TEXT_OVERLAP_GUARD_MM,
                second_box[2] - TEXT_OVERLAP_GUARD_MM,
                second_box[3] - TEXT_OVERLAP_GUARD_MM,
            )
            if second_interior[0] >= first_interior[2]:
                break
            if (
                first.anchor.uuid == second.anchor.uuid
                or math.dist(first.anchor.point, second.anchor.point) <= POINT_TOLERANCE_MM
                or second_interior[1] >= first_interior[3]
                or first_interior[1] >= second_interior[3]
            ):
                continue
            overlap = (
                max(first_interior[0], second_interior[0]),
                max(first_interior[1], second_interior[1]),
                min(first_interior[2], second_interior[2]),
                min(first_interior[3], second_interior[3]),
            )
            if (overlap[2] - overlap[0]) * (overlap[3] - overlap[1]) < (TEXT_OVERLAP_MIN_AREA_MM2):
                continue
            findings.append(
                FreeTextOverlap(
                    first_text=first.anchor.text,
                    first_uuid=first.anchor.uuid,
                    first_box_mm=first.box_mm,
                    second_text=second.anchor.text,
                    second_uuid=second.anchor.uuid,
                    second_box_mm=second.box_mm,
                    overlap_box_mm=(
                        round(overlap[0], 6),
                        round(overlap[1], 6),
                        round(overlap[2], 6),
                        round(overlap[3], 6),
                    ),
                )
            )
    findings.sort(key=lambda item: (item.overlap_box_mm, item.first_uuid, item.second_uuid))
    return tuple(findings), tuple(sorted(set(unsupported)))
