"""Map only source-bound finding locations with an established coordinate frame."""

from __future__ import annotations

import math
from collections.abc import Mapping
from pathlib import PureWindowsPath

from .design_lint_finding_models import DesignLintFinding
from .findings_view_models import FindingMarker, ReviewDrawing, ReviewFinding
from .native_drc_findings import NativeDrcFinding
from .native_erc_report import KiCadErcReport, KiCadErcViolation

DRC_MAPPING_VERSIONS = frozenset({"10.0.0", "10.0.5", "10.0.6"})
SCHEMATIC_MAPPING_VERSIONS = frozenset({"10.0.5", "10.0.6"})
ERC_MAPPING_VERSIONS = frozenset({"10.0.6"})
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
    version: str,
) -> ReviewFinding:
    """Use the exact bound sheet occurrence; never infer a coordinate from a subject."""
    evidence = finding.evidence
    instance = evidence.get("sheet_instance_path")
    instance_path = instance[0] if instance is not None and len(instance) == 1 else None
    drawing = drawings.get(instance_path) if instance_path is not None else None
    key = _SCHEMATIC_POINT.get(finding.rule_id)
    position = _point(evidence.get(key)) if key is not None else None
    can_map = bool(
        key
        and position
        and drawing
        and drawing.mapping_supported
        and instance_path
        and version in SCHEMATIC_MAPPING_VERSIONS
        and evidence.get("kicad_version") == (version,)
        and drawing.schematic_source is not None
        and source_hashes.get(drawing.schematic_source) is not None
        and evidence.get("schematic") == (drawing.schematic_source,)
        and evidence.get("schematic_sha256") == (source_hashes[drawing.schematic_source],)
    )
    markers: tuple[FindingMarker, ...] = ()
    if can_map and position is not None and drawing is not None and _inside(drawing, *position):
        markers = (
            FindingMarker(
                drawing="schematic",
                drawing_file=drawing.file,
                sheet_instance_path=instance_path,
                x_mm=position[0],
                y_mm=position[1],
                detail="/" + "/".join(drawing.sheet_path) if drawing.sheet_path else "/",
            ),
        )
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
                    drawing="pcb",
                    drawing_file=drawing.file,
                    x_mm=item.x_mm,
                    y_mm=item.y_mm,
                    detail=item.description,
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


def erc_finding(
    finding: KiCadErcViolation,
    report: KiCadErcReport,
    primary_source: str,
    drawings: Mapping[str, ReviewDrawing],
    source_hashes: Mapping[str, str],
) -> ReviewFinding:
    """Place exact KiCad 10.0.6 ERC items on their UUID-bound sheet drawing."""
    drawing = drawings.get(finding.sheet_uuid_path)
    display_path = (
        "/" + "/".join(drawing.sheet_path) + "/" if drawing and drawing.sheet_path else "/"
    )
    supported = bool(
        report.kicad_version in ERC_MAPPING_VERSIONS
        and report.coordinate_units == "mm"
        and report.source
        and PureWindowsPath(report.source).name == PureWindowsPath(primary_source).name
        and finding.sheet_uuid_path
        and drawing is not None
        and drawing.mapping_supported
        and drawing.sheet_instance_path == finding.sheet_uuid_path
        and finding.sheet_path == display_path
        and drawing.schematic_source is not None
        and drawing.schematic_source_sha256 == source_hashes.get(drawing.schematic_source)
    )
    markers: list[FindingMarker] = []
    for item in finding.items:
        if not supported or drawing is None or item.x is None or item.y is None:
            continue
        # Exact KiCad 10.0.6 native fault/control exports show ERC pos fields at
        # 1/100 of source and SVG millimetres despite coordinate_units="mm".
        try:
            x_mm, y_mm = float(item.x) * 100, float(item.y) * 100
        except OverflowError:
            continue
        if math.isfinite(x_mm) and math.isfinite(y_mm) and _inside(drawing, x_mm, y_mm):
            markers.append(
                FindingMarker(
                    drawing="schematic",
                    drawing_file=drawing.file,
                    sheet_instance_path=finding.sheet_uuid_path,
                    x_mm=x_mm,
                    y_mm=y_mm,
                    detail=item.description or finding.type,
                )
            )
    reason = None
    if len(markers) < max(1, len(finding.items)):
        reason = (
            "ERC location needs an exact KiCad 10.0.6 UUID sheet, supported SVG frame, "
            "millimetre report, and in-bounds item position."
        )
    return ReviewFinding(
        origin="ERC",
        rule=finding.type,
        severity=f"{finding.severity}{' / excluded' if finding.excluded else ''}",
        title=finding.description or finding.type,
        description="; ".join(
            part
            for part in (finding.sheet_path, *(item.description for item in finding.items))
            if part
        ),
        evidence={
            "sheet": (finding.sheet_path,) if finding.sheet_path else (),
            "sheet_uuid_path": (finding.sheet_uuid_path,) if finding.sheet_uuid_path else (),
            "native_items": tuple(
                f"{item.description or 'Item'}: {item.x}, {item.y} (raw ERC position)"
                for item in finding.items
            ),
            "coordinate_units": (report.coordinate_units,) if report.coordinate_units else (),
            "coordinate_conversion": ("KiCad 10.0.6 ERC position ×100 to schematic mm",)
            if markers
            else (),
        },
        markers=tuple(markers),
        unmapped_reason=reason,
    )
