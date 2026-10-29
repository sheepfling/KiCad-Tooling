"""Map only source-bound finding locations with an established coordinate frame."""

from __future__ import annotations

import math
from collections.abc import Mapping

from .design_lint_finding_models import DesignLintFinding
from .findings_view_models import FindingMarker, ReviewDrawing, ReviewFinding
from .native_drc_findings import NativeDrcFinding

DRC_MAPPING_VERSIONS = frozenset({"10.0.0", "10.0.5", "10.0.6"})
SCHEMATIC_MAPPING_VERSIONS = frozenset({"10.0.5", "10.0.6"})
_SCHEMATIC_POINT = {
    "schematic.wire_end_on_pin_line": "wire_endpoint_mm",
    "schematic.pin_tip_on_wire_interior": "pin_tip_mm",
    "schematic.wire_endpoint_near_pin_tip": "pin_tip_mm",
    "schematic.label_near_wire_endpoint": "label_anchor_mm",
    "schematic.unmarked_wire_crossing": "crossing_mm",
    "schematic.unmarked_t_junction": "junction_mm",
    "schematic.coincident_text_anchors": "anchor_mm",
    "schematic.free_text_overlap": "overlap_box_mm",
    "schematic.free_text_over_symbol_body": "overlap_box_mm",
    "schematic.wire_through_symbol_body": "overlap_segment_mm",
}


def _point(values: tuple[str, ...] | None) -> tuple[float, float] | None:
    if values is None or len(values) != 1:
        return None
    try:
        numbers = tuple(float(item) for item in values[0].split(","))
    except ValueError:
        return None
    if len(numbers) not in {2, 4} or not all(math.isfinite(number) for number in numbers):
        return None
    if len(numbers) == 2:
        return numbers[0], numbers[1]
    return (numbers[0] + numbers[2]) / 2, (numbers[1] + numbers[3]) / 2


def _inside(drawing: ReviewDrawing, x: float, y: float) -> bool:
    return 0 <= x <= drawing.width_mm and 0 <= y <= drawing.height_mm


def design_lint_finding(
    finding: DesignLintFinding,
    drawings: Mapping[str, ReviewDrawing],
    source_hashes: Mapping[str, str],
    primary_schematic: str,
    version: str,
    root_sheet_instance: str | None,
) -> ReviewFinding:
    """Use explicit root-sheet geometry only; never infer a coordinate from a subject."""
    evidence = finding.evidence
    drawing = drawings.get("schematic")
    key = _SCHEMATIC_POINT.get(finding.rule_id)
    position = _point(evidence.get(key)) if key is not None else None
    can_map = bool(
        key
        and position
        and drawing
        and drawing.mapping_supported
        and root_sheet_instance
        and version in SCHEMATIC_MAPPING_VERSIONS
        and evidence.get("kicad_version") == (version,)
        and evidence.get("sheet_instance_path") == (root_sheet_instance,)
        and evidence.get("schematic") == (primary_schematic,)
        and source_hashes.get(primary_schematic) is not None
        and evidence.get("schematic_sha256") == (source_hashes[primary_schematic],)
    )
    markers: tuple[FindingMarker, ...] = ()
    if can_map and position is not None and drawing is not None and _inside(drawing, *position):
        markers = (FindingMarker(drawing="schematic", x_mm=position[0], y_mm=position[1]),)
    description = finding.message
    if finding.reason:
        description += f" Decision: {finding.reason}"
    return ReviewFinding(
        origin="DESIGN_LINT",
        rule=finding.rule_id,
        severity=f"{finding.mode} / {finding.disposition}",
        title=finding.subject,
        description=description,
        fingerprint=finding.fingerprint,
        evidence=finding.evidence,
        markers=markers,
        unmapped_reason=None if markers else "No uniquely bound supported schematic location.",
    )


def drc_finding(
    finding: NativeDrcFinding,
    drawing: ReviewDrawing | None,
    version: str,
    units: str,
) -> ReviewFinding:
    """Locate native board DRC items; parity items can refer to the schematic."""
    markers: list[FindingMarker] = []
    for item in finding.items:
        if (
            drawing is not None
            and drawing.mapping_supported
            and version in DRC_MAPPING_VERSIONS
            and units == "mm"
            and finding.category != "schematic_parity"
            and item.x_mm is not None
            and item.y_mm is not None
            and _inside(drawing, item.x_mm, item.y_mm)
        ):
            markers.append(
                FindingMarker(
                    drawing="pcb", x_mm=item.x_mm, y_mm=item.y_mm, detail=item.description
                )
            )
    reason = None
    if len(markers) < max(1, len(finding.items)):
        reason = "One or more item locations are unavailable or not supported on the board view."
    return ReviewFinding(
        origin="DRC",
        rule=finding.rule,
        severity=f"{finding.severity}{' / excluded' if finding.excluded else ''}",
        title=finding.description,
        description="; ".join(item.description for item in finding.items if item.description),
        evidence={
            "native_items": tuple(
                f"{item.description}: {item.x_mm}, {item.y_mm} ({units} reported)"
                for item in finding.items
            ),
            "native_category": (finding.category,),
        },
        markers=tuple(markers),
        unmapped_reason=reason,
    )
