"""Synthetic near-miss coverage for the bounded schematic geometry prototype."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from kicad_tooling.hwrepo.schematic_geometry import (
    MAX_PIN_ENDPOINT_GAP_MM,
    SUPPORTED_KICAD_VERSION,
    SUPPORTED_KICAD_VERSIONS,
    SchematicGeometryScan,
    resolve_schematic_sheet_path,
    scan_schematic_geometry_tree,
    scan_wire_ends_on_pin_lines,
    schematic_sheet_references,
)

FIXTURES = Path(__file__).parent / "fixtures/design_lint"
FAULT = FIXTURES / "near-miss-pin-line.kicad_sch"
CONTROL = FIXTURES / "connected-pin-control.kicad_sch"
PIN_ON_WIRE_MIDDLE_FAULT = FIXTURES / "pin-on-wire-middle-no-junction.kicad_sch"
PIN_ON_WIRE_MIDDLE_CONTROL = FIXTURES / "pin-on-wire-middle-junction-control.kicad_sch"
LABEL_NEAR_WIRE_ENDPOINT = FIXTURES / "label-near-wire-endpoint.kicad_sch"
UNMARKED_CROSSING = FIXTURES / "unmarked-orthogonal-crossing.kicad_sch"
JUNCTION_MARKED_CROSSING = FIXTURES / "junction-marked-crossing-control.kicad_sch"
GRAPHICAL_ONLY_CROSSING = FIXTURES / "graphical-only-crossing-control.kicad_sch"
WIRE_END_NEAR_PIN_TIP_FAULT = FIXTURES / "wire-end-near-pin-tip.kicad_sch"
T_JUNCTION_FAULT = FIXTURES / "t-junction/fault-no-junction.kicad_sch"
T_JUNCTION_CONTROL = FIXTURES / "t-junction/control-marked-junction.kicad_sch"
DANGLING_WIRE = FIXTURES / "t-junction/dangling-wire-only.kicad_sch"
REPEATED_SHEET = FIXTURES / "repeated-sheet/repeated-sheet-root.kicad_sch"
REPEATED_CHANNEL = FIXTURES / "repeated-sheet/repeated-channel.kicad_sch"
REPEATED_SHEET_CONTROL = FIXTURES / "repeated-sheet/repeated-sheet-control-root.kicad_sch"
REPEATED_CHANNEL_CONTROL = FIXTURES / "repeated-sheet/repeated-channel-control.kicad_sch"
TRANSFORM_MIDPOINTS: dict[tuple[int, str | None], tuple[float, float]] = {
    (0, None): (76.2, 72.39),
    (0, "x"): (76.2, 80.01),
    (0, "y"): (76.2, 72.39),
    (90, None): (72.39, 76.2),
    (90, "x"): (72.39, 76.2),
    (90, "y"): (80.01, 76.2),
    (180, None): (76.2, 80.01),
    (180, "x"): (76.2, 72.39),
    (180, "y"): (76.2, 80.01),
    (270, None): (80.01, 76.2),
    (270, "x"): (80.01, 76.2),
    (270, "y"): (72.39, 76.2),
}
TRANSFORM_PIN_TIPS: dict[tuple[int, str | None], tuple[float, float]] = {
    (0, None): (76.2, 71.12),
    (0, "x"): (76.2, 81.28),
    (0, "y"): (76.2, 71.12),
    (90, None): (71.12, 76.2),
    (90, "x"): (71.12, 76.2),
    (90, "y"): (81.28, 76.2),
    (180, None): (76.2, 81.28),
    (180, "x"): (76.2, 71.12),
    (180, "y"): (76.2, 81.28),
    (270, None): (81.28, 76.2),
    (270, "x"): (81.28, 76.2),
    (270, "y"): (71.12, 76.2),
}
TRANSFORM_NEAR_PIN_ENDPOINTS: dict[tuple[int, str | None], tuple[float, float]] = {
    (0, None): (76.2, 70.62),
    (0, "x"): (76.2, 81.78),
    (0, "y"): (76.2, 70.62),
    (90, None): (70.62, 76.2),
    (90, "x"): (70.62, 76.2),
    (90, "y"): (81.78, 76.2),
    (180, None): (76.2, 81.78),
    (180, "x"): (76.2, 70.62),
    (180, "y"): (76.2, 81.78),
    (270, None): (81.78, 76.2),
    (270, "x"): (81.78, 76.2),
    (270, "y"): (70.62, 76.2),
}


def _geometry_candidates(scan: SchematicGeometryScan) -> tuple[object, ...]:
    return (
        scan.findings,
        scan.pin_tip_on_wire_interiors,
        scan.wire_endpoints_near_pin_tips,
        scan.labels_near_wire_endpoints,
        scan.unmarked_wire_crossings,
        scan.unmarked_t_junctions,
        scan.coincident_text_anchors,
        scan.free_text_overlaps,
        scan.free_text_wire_overlaps,
        scan.free_text_symbol_body_overlaps,
        scan.wires_through_symbol_bodies,
    )


def _graphical_crossing_baseline() -> bytes:
    source = CONTROL.read_bytes()
    replacements = (
        (b'(project "connected-pin-control"', b'(project "graphical-only-crossing-control"'),
        (b"Synthetic connected-pin control", b"Synthetic graphical-only crossing control"),
        (
            b"NOT FOR MANUFACTURE - tooling regression fixture",
            b"NOT FOR MANUFACTURE - graphic shapes cross an electrical wire",
        ),
    )
    for source_text, baseline_text in replacements:
        if source.count(source_text) != 1:
            raise AssertionError("connected-pin control does not contain one baseline field")
        source = source.replace(source_text, baseline_text, 1)
    return source


def _transform_fixture_point(
    point: tuple[float, float], angle: int, mirror: str | None
) -> tuple[float, float]:
    local_x = point[0] - 76.2
    screen_y = point[1] - 76.2
    radians = math.radians(angle)
    cosine = math.cos(radians)
    sine = math.sin(radians)
    rotated_x = local_x * cosine + screen_y * sine
    rotated_y = -local_x * sine + screen_y * cosine
    if mirror == "x":
        rotated_y = -rotated_y
    elif mirror == "y":
        rotated_x = -rotated_x
    return round(76.2 + rotated_x, 6), round(76.2 + rotated_y, 6)


def transformed_fault(angle: int, mirror: str | None, endpoint: tuple[float, float]) -> bytes:
    text = FAULT.read_text(encoding="utf-8")
    text, symbol_count = re.subn(
        r'\(symbol \(lib_id "Lint:R"\) \(at 76\.2 76\.2 0\) \(unit 1\)',
        f'(symbol (lib_id "Lint:R") (at 76.2 76.2 {angle}) (unit 1)',
        text,
        count=1,
    )
    if symbol_count != 1:
        raise AssertionError("synthetic fixture did not have one expected placed resistor")
    if mirror is not None:
        text = text.replace(
            f"(at 76.2 76.2 {angle}) (unit 1)",
            f"(at 76.2 76.2 {angle}) (unit 1) (mirror {mirror})",
            1,
        )
    text, wire_count = re.subn(
        r"\(wire \(pts \(xy [^)]+\) \(xy 101\.6 72\.39\)\)",
        f"(wire (pts (xy {endpoint[0]} {endpoint[1]}) (xy {endpoint[0] + 25.4} {endpoint[1]}))",
        text,
        count=1,
    )
    if wire_count != 1:
        raise AssertionError("synthetic fixture did not have one expected wire")
    return text.encode("utf-8")


def transformed_pin_tip_wire(angle: int, mirror: str | None, tip: tuple[float, float]) -> bytes:
    text = PIN_ON_WIRE_MIDDLE_FAULT.read_text(encoding="utf-8")
    text, symbol_count = re.subn(
        r'\(symbol \(lib_id "Lint:R"\) \(at 76\.2 76\.2 0\) \(unit 1\)',
        f'(symbol (lib_id "Lint:R") (at 76.2 76.2 {angle}) (unit 1)',
        text,
        count=1,
    )
    if symbol_count != 1:
        raise AssertionError("synthetic wire-interior fixture did not have one placed resistor")
    if mirror is not None:
        text = text.replace(
            f"(at 76.2 76.2 {angle}) (unit 1)",
            f"(at 76.2 76.2 {angle}) (unit 1) (mirror {mirror})",
            1,
        )
    endpoint_start = (round(tip[0] - 25.4, 6), tip[1])
    endpoint_end = (round(tip[0] + 25.4, 6), tip[1])
    text, wire_count = re.subn(
        r"\(wire \(pts \(xy 50\.8 71\.12\) \(xy 101\.6 71\.12\)\)",
        "(wire (pts (xy "
        f"{endpoint_start[0]} {endpoint_start[1]}) (xy {endpoint_end[0]} {endpoint_end[1]}))",
        text,
        count=1,
    )
    if wire_count != 1:
        raise AssertionError("synthetic wire-interior fixture did not have the expected wire")
    return text.encode("utf-8")


def transformed_near_pin_tip_wire(angle: int, mirror: str | None) -> bytes:
    text = WIRE_END_NEAR_PIN_TIP_FAULT.read_text(encoding="utf-8")
    text, symbol_count = re.subn(
        r'\(symbol \(lib_id "Lint:R"\) \(at 76\.2 76\.2 0\) \(unit 1\)',
        f'(symbol (lib_id "Lint:R") (at 76.2 76.2 {angle}) (unit 1)',
        text,
        count=1,
    )
    if symbol_count != 1:
        raise AssertionError("synthetic near-tip fixture did not have one placed resistor")
    if mirror is not None:
        text = text.replace(
            f"(at 76.2 76.2 {angle}) (unit 1)",
            f"(at 76.2 76.2 {angle}) (unit 1) (mirror {mirror})",
            1,
        )
    near = _transform_fixture_point((76.2, 70.62), angle, mirror)
    far = _transform_fixture_point((101.6, 70.62), angle, mirror)
    text, wire_count = re.subn(
        r"\(wire \(pts \(xy 76\.2 70\.62\) \(xy 101\.6 70\.62\)\)",
        f"(wire (pts (xy {near[0]} {near[1]}) (xy {far[0]} {far[1]}))",
        text,
        count=1,
    )
    if wire_count != 1:
        raise AssertionError("synthetic near-tip fixture did not have its expected wire")
    text, label_count = re.subn(
        r'\(label "FAULT_NET" \(at 101\.6 70\.62 0\)',
        f'(label "FAULT_NET" (at {far[0]} {far[1]} 0)',
        text,
        count=1,
    )
    if label_count != 1:
        raise AssertionError("synthetic near-tip fixture did not have its expected label")
    return text.encode("utf-8")


def free_text_anchor_fixture(
    first_point: tuple[float, float], second_point: tuple[float, float]
) -> bytes:
    """Place two synthetic free-text objects on a known valid schematic."""
    return free_text_objects_fixture("GRAPHIC_A", first_point, "GRAPHIC_B", second_point)


def free_text_objects_fixture(
    first_text: str,
    first_point: tuple[float, float],
    second_text: str,
    second_point: tuple[float, float],
) -> bytes:
    """Place two named synthetic free-text objects on a known valid schematic."""
    source = CONTROL.read_text(encoding="utf-8")

    def quoted(value: str) -> str:
        escaped = value.replace("\r\n", "\n").replace("\r", "\n")
        escaped = escaped.replace("\\", "\\\\").replace("\n", "\\n")
        return '"' + escaped.replace('"', '\\"') + '"'

    nodes = "\n".join(
        (
            (
                f"  (text {quoted(first_text)} (at {first_point[0]} {first_point[1]} 0) "
                "(effects (font (size 1.27 1.27))) "
                '(uuid "d0000000-0000-4000-8000-000000000001"))'
            ),
            (
                f"  (text {quoted(second_text)} (at {second_point[0]} {second_point[1]} 0) "
                "(effects (font (size 1.27 1.27))) "
                '(uuid "d0000000-0000-4000-8000-000000000002"))'
            ),
        )
    )
    marker = "  (sheet_instances"
    if marker not in source:
        raise AssertionError("synthetic schematic fixture has no sheet_instances node")
    return source.replace(marker, f"{nodes}\n{marker}", 1).encode("utf-8")


def justify_first_free_text(source: bytes, options: str) -> bytes:
    """Add one explicit justification field to the first synthetic text object."""
    start = source.index(b'(text "FIRST"')
    end_marker = b'(uuid "d0000000-0000-4000-8000-000000000001"))'
    end = source.index(end_marker, start) + len(end_marker)
    text_node = source[start:end]
    default_effects = b"(effects (font (size 1.27 1.27)))"
    if text_node.count(default_effects) != 1:
        raise AssertionError("synthetic text fixture has no unique default effects section")
    justification = f"(justify {options})" if options else "(justify)"
    justified_effects = f"(effects (font (size 1.27 1.27)) {justification})".encode()
    return source[:start] + text_node.replace(default_effects, justified_effects, 1) + source[end:]


def free_text_wire_fixture(
    text: str,
    point: tuple[float, float],
    *,
    wire_points: tuple[tuple[float, float], tuple[float, float]] = (
        (76.2, 71.12),
        (101.6, 71.12),
    ),
) -> bytes:
    """Place one synthetic free-text item over or clear of a known wire."""
    source = CONTROL.read_text(encoding="utf-8")
    original_wire = "(xy 76.2 71.12) (xy 101.6 71.12)"
    replacement_wire = (
        f"(xy {wire_points[0][0]} {wire_points[0][1]}) (xy {wire_points[1][0]} {wire_points[1][1]})"
    )
    if source.count(original_wire) != 1:
        raise AssertionError("synthetic connected control has no unique horizontal wire")
    source = source.replace(original_wire, replacement_wire, 1)

    escaped_text = text.replace("\r\n", "\n").replace("\r", "\n")
    escaped_text = escaped_text.replace("\\", "\\\\").replace("\n", "\\n")
    quoted = '"' + escaped_text.replace('"', '\\"') + '"'
    node = (
        f"  (text {quoted} (at {point[0]} {point[1]} 0) "
        "(effects (font (size 1.27 1.27))) "
        '(uuid "f0000000-0000-4000-8000-000000000001"))'
    )
    marker = "  (sheet_instances"
    if source.count(marker) != 1:
        raise AssertionError("synthetic connected control has no unique sheet_instances node")
    return source.replace(marker, f"{node}\n{marker}", 1).encode("utf-8")


def symbol_body_wire_fixture(
    wire_points: tuple[tuple[float, float], tuple[float, float]] = (
        (71.12, 76.2),
        (81.28, 76.2),
    ),
) -> bytes:
    """Add one synthetic wire through, or clear of, the resistor body."""
    source = CONTROL.read_text(encoding="utf-8")
    wire = (
        f"  (wire (pts (xy {wire_points[0][0]} {wire_points[0][1]}) "
        f"(xy {wire_points[1][0]} {wire_points[1][1]})) "
        "(stroke (width 0) (type default)) "
        '(uuid "f1000000-0000-4000-8000-000000000001"))'
    )
    marker = "  (sheet_instances"
    if source.count(marker) != 1:
        raise AssertionError("synthetic connected control has no unique sheet_instances node")
    return source.replace(marker, f"{wire}\n{marker}", 1).encode("utf-8")


def enclosed_connector_body_wire_fixture(*, body_offset_x: float) -> bytes:
    """Connect peer passive header pins inside or outside their body outlines."""
    source = f"""(kicad_sch (version 20231120) (generator "eeschema")
  (uuid "10000000-0000-4000-8000-000000000001")
  (paper "A4")
  (title_block (title "Synthetic enclosed connector geometry control")
    (comment 1 "NOT FOR MANUFACTURE - tooling regression fixture"))
  (lib_symbols
    (symbol "Connector_Generic:Conn_01x01"
      (pin_names (offset 0) hide)
      (in_bom yes) (on_board yes)
      (property "Reference" "J" (at 0 -7.62 0) (effects (font (size 1.27 1.27))))
      (property "Value" "Synthetic enclosed header" (at 0 7.62 0) (effects (font (size 1.27 1.27))))
      (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (symbol "Conn_01x01_0_1"
        (rectangle (start {body_offset_x - 5.08} -5.08)
          (end {body_offset_x + 5.08} 5.08)
          (stroke (width 0.254) (type default)) (fill (type none))))
      (symbol "Conn_01x01_1_1"
        (pin passive line (at -2.54 0 0) (length 2.54)
          (name "SIGNAL" (effects (font (size 1.27 1.27))))
          (number "1" (effects (font (size 1.27 1.27)))))))
  )
  (symbol (lib_id "Connector_Generic:Conn_01x01") (at 76.2 76.2 0) (unit 1)
    (in_bom yes) (on_board yes) (dnp no)
    (uuid "10000000-0000-4000-8000-000000000002")
    (property "Reference" "J1" (at 76.2 88.9 0) (effects (font (size 1.27 1.27))))
    (property "Value" "Synthetic enclosed header" (at 76.2 91.44 0) (effects (font (size 1.27 1.27))))
    (property "Footprint" "" (at 76.2 76.2 0) (effects (font (size 1.27 1.27)) hide))
    (property "Datasheet" "" (at 76.2 76.2 0) (effects (font (size 1.27 1.27)) hide))
    (pin "1" (uuid "10000000-0000-4000-8000-000000000003"))
    (instances (project "synthetic-enclosed-connector"
    (path "/10000000-0000-4000-8000-000000000001" (reference "J1") (unit 1)))))
  (symbol (lib_id "Connector_Generic:Conn_01x01") (at 120.65 76.2 0) (unit 1)
    (in_bom yes) (on_board yes) (dnp no)
    (uuid "20000000-0000-4000-8000-000000000002")
    (property "Reference" "J2" (at 120.65 88.9 0) (effects (font (size 1.27 1.27))))
    (property "Value" "Synthetic enclosed header" (at 120.65 91.44 0) (effects (font (size 1.27 1.27))))
    (property "Footprint" "" (at 120.65 76.2 0) (effects (font (size 1.27 1.27)) hide))
    (property "Datasheet" "" (at 120.65 76.2 0) (effects (font (size 1.27 1.27)) hide))
    (pin "1" (uuid "20000000-0000-4000-8000-000000000003"))
    (instances (project "synthetic-enclosed-connector"
      (path "/10000000-0000-4000-8000-000000000001" (reference "J2") (unit 1)))))
  (wire (pts (xy 63.5 76.2) (xy 73.66 76.2))
    (stroke (width 0) (type default))
    (uuid "10000000-0000-4000-8000-000000000004"))
  (label "SIGNAL" (at 63.5 76.2 0)
    (effects (font (size 1.27 1.27)) (justify left bottom))
    (uuid "10000000-0000-4000-8000-000000000005"))
  (wire (pts (xy 109.22 76.2) (xy 118.11 76.2))
    (stroke (width 0) (type default))
    (uuid "20000000-0000-4000-8000-000000000004"))
  (label "SIGNAL" (at 109.22 76.2 0)
    (effects (font (size 1.27 1.27)) (justify left bottom))
    (uuid "20000000-0000-4000-8000-000000000005"))
  (sheet_instances (path "/" (page "1")))
)
"""
    return source.encode("utf-8")


def free_text_symbol_body_fixture(
    text: str = "BODY NOTE",
    point: tuple[float, float] = (76.2, 76.2),
) -> bytes:
    """Place one supported top-level free-text item over or clear of a symbol body."""
    source = CONTROL.read_text(encoding="utf-8")
    quoted = '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'
    node = (
        f"  (text {quoted} (at {point[0]} {point[1]} 0) "
        "(effects (font (size 1.27 1.27))) "
        '(uuid "f2000000-0000-4000-8000-000000000001"))'
    )
    marker = "  (sheet_instances"
    if source.count(marker) != 1:
        raise AssertionError("synthetic connected control has no unique sheet_instances node")
    return source.replace(marker, f"{node}\n{marker}", 1).encode("utf-8")


def transformed_symbol_body_wire(angle: int, mirror: str | None) -> bytes:
    """Rotate or mirror a resistor body and keep the synthetic wire crossing it."""
    source = CONTROL.read_text(encoding="utf-8")
    source, symbol_count = re.subn(
        r'\(symbol \(lib_id "Lint:R"\) \(at 76\.2 76\.2 0\) \(unit 1\)',
        f'(symbol (lib_id "Lint:R") (at 76.2 76.2 {angle}) (unit 1)',
        source,
        count=1,
    )
    if symbol_count != 1:
        raise AssertionError("synthetic body fixture did not have one placed resistor")
    if mirror is not None:
        source = source.replace(
            f"(at 76.2 76.2 {angle}) (unit 1)",
            f"(at 76.2 76.2 {angle}) (unit 1) (mirror {mirror})",
            1,
        )
    start = _transform_fixture_point((71.12, 76.2), angle, mirror)
    end = _transform_fixture_point((81.28, 76.2), angle, mirror)
    wire = (
        f"  (wire (pts (xy {start[0]} {start[1]}) (xy {end[0]} {end[1]})) "
        "(stroke (width 0) (type default)) "
        '(uuid "f1000000-0000-4000-8000-000000000001"))'
    )
    marker = "  (sheet_instances"
    if source.count(marker) != 1:
        raise AssertionError("synthetic connected control has no unique sheet_instances node")
    return source.replace(marker, f"{wire}\n{marker}", 1).encode("utf-8")


def calibrated_stroke_text_metrics_fixture() -> bytes:
    """Render every calibrated standard-stroke glyph from one synthetic source."""
    source = CONTROL.read_text(encoding="utf-8")
    characters = " " + "".join(chr(code) for code in range(33, 127)) + "—µΩ°±×"

    def quoted(value: str) -> str:
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'

    nodes = "\n".join(
        f"  (text {quoted(character)} (at 30 30 0) "
        f"(effects (font (size 1.27 1.27))) "
        f'(uuid "e0000000-0000-4000-8000-{index + 1:012x}"))'
        for index, character in enumerate(characters)
    )
    marker = "  (sheet_instances"
    if marker not in source:
        raise AssertionError("synthetic schematic fixture has no sheet_instances node")
    return source.replace(marker, f"{nodes}\n{marker}", 1).encode("utf-8")


def _native_svg_text_strokes(
    svg_root: ET.Element, wanted: str
) -> tuple[tuple[tuple[float, float], tuple[float, float]], ...]:
    """Read KiCad's standard-stroke SVG line segments for one unique text object."""
    matches: list[ET.Element] = []
    for node in svg_root.iter():
        if node.tag.endswith("}g") and node.attrib.get("class") == "stroked-text":
            description = next((child.text for child in node if child.tag.endswith("}desc")), None)
            if description == wanted:
                matches.append(node)
    if len(matches) != 1:
        raise AssertionError(f"native SVG did not contain one stroked-text group for {wanted!r}")

    segments: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for path in matches[0].iter():
        if not path.tag.endswith("}path"):
            continue
        tokens = re.findall(r"[ML]|[-+]?(?:\d+\.\d*|\.\d+|\d+)", path.attrib.get("d", ""))
        current: tuple[float, float] | None = None
        index = 0
        while index < len(tokens):
            command = tokens[index]
            if command not in {"M", "L"}:
                raise AssertionError(f"unsupported KiCad stroked-text path command {command!r}")
            point = (float(tokens[index + 1]), float(tokens[index + 2]))
            if command == "L" and current is not None:
                segments.append((current, point))
            current = point
            index += 3
    return tuple(segments)


def _native_svg_matching_line(
    svg_root: ET.Element,
    start: tuple[float, float],
    end: tuple[float, float],
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Read one exact native SVG line segment by its expected schematic endpoints."""
    matches: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for path in svg_root.iter():
        if not path.tag.endswith("}path"):
            continue
        tokens = re.findall(r"[ML]|[-+]?(?:\d+\.\d*|\.\d+|\d+)", path.attrib.get("d", ""))
        current: tuple[float, float] | None = None
        index = 0
        while index < len(tokens):
            command = tokens[index]
            if command not in {"M", "L"}:
                raise AssertionError(f"unsupported native SVG line command {command!r}")
            point = (float(tokens[index + 1]), float(tokens[index + 2]))
            if command == "L" and current is not None:
                forward = math.dist(current, start) <= 0.0001 and math.dist(point, end) <= 0.0001
                reverse = math.dist(current, end) <= 0.0001 and math.dist(point, start) <= 0.0001
                if forward or reverse:
                    matches.append((current, point))
            current = point
            index += 3
    if len(matches) != 1:
        raise AssertionError(f"native SVG did not contain one expected line segment: {matches!r}")
    return matches[0]


def _native_svg_matching_rect(
    svg_root: ET.Element,
    x: float,
    y: float,
    width: float,
    height: float,
) -> tuple[float, float, float, float]:
    """Read one exact native SVG rectangle by its schematic-space bounds."""
    matches = [
        (
            float(node.attrib["x"]),
            float(node.attrib["y"]),
            float(node.attrib["width"]),
            float(node.attrib["height"]),
        )
        for node in svg_root.iter()
        if node.tag.endswith("}rect")
        and all(
            abs(float(node.attrib[key]) - expected) <= 0.0001
            for key, expected in (
                ("x", x),
                ("y", y),
                ("width", width),
                ("height", height),
            )
        )
    ]
    if len(matches) != 1:
        raise AssertionError(f"native SVG did not contain one expected rectangle: {matches!r}")
    return matches[0]


def _netlist_components_without_sheetfile(netlist: ET.Element) -> bytes:
    """Normalize project-path metadata before comparing native component maps."""
    components = netlist.find("./components")
    if components is None:
        raise AssertionError("native netlist has no components section")
    normalized = ET.fromstring(ET.tostring(components))
    for parent in normalized.iter():
        for child in tuple(parent):
            if child.tag == "property" and child.attrib.get("name") == "Sheetfile":
                parent.remove(child)
    return ET.tostring(normalized)


def _segment_distance(
    first_start: tuple[float, float],
    first_end: tuple[float, float],
    second_start: tuple[float, float],
    second_end: tuple[float, float],
) -> float:
    def subtract(first: tuple[float, float], second: tuple[float, float]) -> tuple[float, float]:
        return first[0] - second[0], first[1] - second[1]

    def cross(first: tuple[float, float], second: tuple[float, float]) -> float:
        return first[0] * second[1] - first[1] * second[0]

    def point_segment(
        point: tuple[float, float], start: tuple[float, float], end: tuple[float, float]
    ) -> float:
        direction = subtract(end, start)
        length_squared = direction[0] ** 2 + direction[1] ** 2
        if length_squared == 0.0:
            return math.dist(point, start)
        projection = (
            (point[0] - start[0]) * direction[0] + (point[1] - start[1]) * direction[1]
        ) / length_squared
        parameter = min(1.0, max(0.0, projection))
        nearest = (
            start[0] + parameter * direction[0],
            start[1] + parameter * direction[1],
        )
        return math.dist(point, nearest)

    first_direction = subtract(first_end, first_start)
    second_direction = subtract(second_end, second_start)
    denominator = cross(first_direction, second_direction)
    offset = subtract(second_start, first_start)
    if denominator != 0.0:
        first_parameter = cross(offset, second_direction) / denominator
        second_parameter = cross(offset, first_direction) / denominator
        if 0.0 <= first_parameter <= 1.0 and 0.0 <= second_parameter <= 1.0:
            return 0.0
    return min(
        point_segment(first_start, second_start, second_end),
        point_segment(first_end, second_start, second_end),
        point_segment(second_start, first_start, first_end),
        point_segment(second_end, first_start, first_end),
    )


class SchematicGeometryTests(unittest.TestCase):
    def scan(
        self,
        source: bytes,
        *,
        unconnected_pins: frozenset[str] = frozenset({"R1.1"}),
        version: str = SUPPORTED_KICAD_VERSION,
    ):
        return scan_wire_ends_on_pin_lines(
            source,
            source_path="synthetic/near-miss-pin-line.kicad_sch",
            kicad_version=version,
            unconnected_pins=unconnected_pins,
        )

    def test_fault_is_localized_to_the_native_unconnected_pin(self) -> None:
        source = FAULT.read_bytes()
        result = self.scan(source)

        self.assertEqual(result.status, "COMPLETE")
        self.assertEqual(result.source_sha256, hashlib.sha256(source).hexdigest())
        self.assertEqual(len(result.findings), 1)
        finding = result.findings[0]
        self.assertEqual((finding.reference, finding.pin_number), ("R1", "1"))
        self.assertEqual(finding.pin_tip_mm, (76.2, 71.12))
        self.assertEqual(finding.wire_endpoint_mm, (76.2, 72.39))
        self.assertEqual(finding.distance_to_pin_tip_mm, 1.27)
        self.assertEqual(finding.distance_along_pin_mm, 1.27)

    def test_connected_control_and_non_native_open_pin_are_excluded(self) -> None:
        control = self.scan(CONTROL.read_bytes(), unconnected_pins=frozenset({"R1.2"}))
        self.assertEqual(control.findings, ())

        not_open = self.scan(FAULT.read_bytes(), unconnected_pins=frozenset({"R1.2"}))
        self.assertEqual(not_open.findings, ())

    def test_coincident_free_text_anchors_are_reported(self) -> None:
        result = self.scan(free_text_anchor_fixture((25.4, 25.4), (25.4, 25.4)))
        self.assertEqual(result.status, "COMPLETE")
        self.assertEqual(len(result.coincident_text_anchors), 1)
        self.assertEqual(result.free_text_overlaps, ())
        finding = result.coincident_text_anchors[0]
        self.assertEqual(finding.anchor_mm, (25.4, 25.4))
        self.assertEqual((finding.first_text, finding.second_text), ("GRAPHIC_A", "GRAPHIC_B"))
        self.assertEqual(
            (finding.first_uuid, finding.second_uuid),
            (
                "d0000000-0000-4000-8000-000000000001",
                "d0000000-0000-4000-8000-000000000002",
            ),
        )

    def test_coincident_text_anchors_are_translation_invariant_and_separation_clears_pair(
        self,
    ) -> None:
        baseline_source = free_text_anchor_fixture((25.4, 25.4), (25.4, 25.4))
        translated_source = free_text_anchor_fixture((200.0, 200.0), (200.0, 200.0))
        baseline = self.scan(baseline_source, unconnected_pins=frozenset())
        translated = self.scan(translated_source, unconnected_pins=frozenset())

        self.assertEqual(len(baseline.coincident_text_anchors), 1)
        self.assertEqual(len(translated.coincident_text_anchors), 1)
        baseline_finding = baseline.coincident_text_anchors[0]
        translated_finding = translated.coincident_text_anchors[0]
        identity = (
            baseline_finding.first_text,
            baseline_finding.first_uuid,
            baseline_finding.second_text,
            baseline_finding.second_uuid,
            baseline_finding.sheet_instance_path,
        )
        self.assertEqual(
            (
                translated_finding.first_text,
                translated_finding.first_uuid,
                translated_finding.second_text,
                translated_finding.second_uuid,
                translated_finding.sheet_instance_path,
            ),
            identity,
        )
        self.assertEqual(translated_finding.anchor_mm, (200.0, 200.0))
        self.assertEqual(baseline.source_sha256, hashlib.sha256(baseline_source).hexdigest())
        self.assertEqual(translated.source_sha256, hashlib.sha256(translated_source).hexdigest())
        self.assertNotEqual(translated.source_sha256, baseline.source_sha256)

        separated_source = free_text_anchor_fixture((200.0, 200.0), (205.0, 200.0))
        separated = self.scan(separated_source, unconnected_pins=frozenset())
        self.assertEqual(separated.status, "COMPLETE")
        self.assertEqual(separated.coincident_text_anchors, ())

    def test_separate_free_text_anchors_are_not_reported(self) -> None:
        apart = self.scan(free_text_anchor_fixture((25.4, 25.4), (50.8, 25.4)))
        self.assertEqual(apart.coincident_text_anchors, ())
        self.assertEqual(apart.free_text_overlaps, ())

        within_tolerance = self.scan(free_text_anchor_fixture((25.4, 25.4), (25.4009, 25.4)))
        self.assertEqual(len(within_tolerance.coincident_text_anchors), 1)

        outside_tolerance = self.scan(free_text_anchor_fixture((25.4, 25.4), (25.4011, 25.4)))
        self.assertEqual(outside_tolerance.coincident_text_anchors, ())

    def test_distinct_free_text_overlap_is_reported(self) -> None:
        source = free_text_objects_fixture(
            "LONG_LABEL_ALPHA", (25.4, 25.4), "LONG_LABEL_BETA", (29.0, 25.4)
        )
        result = self.scan(source, unconnected_pins=frozenset())
        self.assertEqual(result.status, "COMPLETE")
        self.assertEqual(result.coincident_text_anchors, ())
        self.assertEqual(len(result.free_text_overlaps), 1)
        finding = result.free_text_overlaps[0]
        self.assertEqual(
            (finding.first_text, finding.second_text),
            ("LONG_LABEL_ALPHA", "LONG_LABEL_BETA"),
        )
        self.assertEqual(
            (finding.first_uuid, finding.second_uuid),
            (
                "d0000000-0000-4000-8000-000000000001",
                "d0000000-0000-4000-8000-000000000002",
            ),
        )
        self.assertGreater(finding.overlap_box_mm[2] - finding.overlap_box_mm[0], 10.0)

    def test_measured_electrical_glyphs_have_fault_control_and_translation_coverage(self) -> None:
        first_text = "10µF ±5V"
        second_text = "4.7Ω"
        baseline_source = free_text_objects_fixture(
            first_text, (25.4, 25.4), second_text, (29.0, 25.4)
        )
        translated_source = free_text_objects_fixture(
            first_text, (125.4, 125.4), second_text, (129.0, 125.4)
        )
        control_source = free_text_objects_fixture(
            first_text, (25.4, 25.4), second_text, (50.8, 25.4)
        )

        baseline = self.scan(baseline_source, unconnected_pins=frozenset())
        translated = self.scan(translated_source, unconnected_pins=frozenset())
        control = self.scan(control_source, unconnected_pins=frozenset())

        self.assertEqual(baseline.status, "COMPLETE")
        self.assertEqual(baseline.unsupported_by_rule, {})
        self.assertEqual(len(baseline.free_text_overlaps), 1)
        self.assertEqual(translated.status, "COMPLETE")
        self.assertEqual(translated.unsupported_by_rule, {})
        self.assertEqual(len(translated.free_text_overlaps), 1)
        self.assertEqual(control.status, "COMPLETE")
        self.assertEqual(control.free_text_overlaps, ())
        original = baseline.free_text_overlaps[0]
        shifted = translated.free_text_overlaps[0]
        self.assertEqual(
            (shifted.first_text, shifted.first_uuid, shifted.second_text, shifted.second_uuid),
            (original.first_text, original.first_uuid, original.second_text, original.second_uuid),
        )
        for before, after in zip(original.overlap_box_mm, shifted.overlap_box_mm, strict=True):
            self.assertAlmostEqual(after - before, 100.0, places=6)

    def test_free_text_overlap_is_translation_invariant_and_separation_clears_pair(
        self,
    ) -> None:
        baseline_source = free_text_objects_fixture(
            "LONG_LABEL_ALPHA", (25.4, 25.4), "LONG_LABEL_BETA", (29.0, 25.4)
        )
        translated_source = free_text_objects_fixture(
            "LONG_LABEL_ALPHA", (125.4, 125.4), "LONG_LABEL_BETA", (129.0, 125.4)
        )
        baseline = self.scan(baseline_source, unconnected_pins=frozenset())
        translated = self.scan(translated_source, unconnected_pins=frozenset())
        self.assertEqual(len(baseline.free_text_overlaps), 1)
        self.assertEqual(len(translated.free_text_overlaps), 1)
        baseline_finding = baseline.free_text_overlaps[0]
        translated_finding = translated.free_text_overlaps[0]
        self.assertEqual(
            (
                translated_finding.first_text,
                translated_finding.first_uuid,
                translated_finding.second_text,
                translated_finding.second_uuid,
                translated_finding.sheet_instance_path,
            ),
            (
                baseline_finding.first_text,
                baseline_finding.first_uuid,
                baseline_finding.second_text,
                baseline_finding.second_uuid,
                baseline_finding.sheet_instance_path,
            ),
        )
        for baseline_coordinate, translated_coordinate in zip(
            baseline_finding.overlap_box_mm,
            translated_finding.overlap_box_mm,
            strict=True,
        ):
            self.assertAlmostEqual(translated_coordinate - baseline_coordinate, 100.0, places=6)
        self.assertEqual(baseline.source_sha256, hashlib.sha256(baseline_source).hexdigest())
        self.assertEqual(translated.source_sha256, hashlib.sha256(translated_source).hexdigest())
        self.assertNotEqual(translated.source_sha256, baseline.source_sha256)

        separated_source = free_text_objects_fixture(
            "LONG_LABEL_ALPHA", (125.4, 125.4), "LONG_LABEL_BETA", (175.0, 125.4)
        )
        separated = self.scan(separated_source, unconnected_pins=frozenset())
        self.assertEqual(separated.status, "COMPLETE")
        self.assertEqual(separated.free_text_overlaps, ())

    def test_horizontal_free_text_justification_uses_its_insertion_anchor(self) -> None:
        metrics_path = (
            Path(__file__).parents[1] / "kicad_tooling/hwrepo/schematic-text-metrics.json"
        )
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        width = sum(metrics["advances_mm"][character] for character in "FIRST")
        width += metrics["line_end_spacing_mm"]

        for justification, second_x, expected_box in (
            ("left", 54.0, (50.0, 50.0 + width)),
            ("right", 46.0, (50.0 - width, 50.0)),
        ):
            with self.subTest(justification=justification):
                source = justify_first_free_text(
                    free_text_objects_fixture("FIRST", (50.0, 50.0), "SECOND", (second_x, 50.0)),
                    justification,
                )
                result = self.scan(source, unconnected_pins=frozenset())

                self.assertEqual(result.status, "COMPLETE")
                self.assertEqual(result.unsupported_by_rule, {})
                self.assertEqual(len(result.free_text_overlaps), 1)
                finding = result.free_text_overlaps[0]
                target_uuid = "d0000000-0000-4000-8000-000000000001"
                text_box = (
                    finding.first_box_mm
                    if finding.first_uuid == target_uuid
                    else finding.second_box_mm
                )
                self.assertIn(target_uuid, (finding.first_uuid, finding.second_uuid))
                self.assertAlmostEqual(text_box[0], expected_box[0])
                self.assertAlmostEqual(text_box[2], expected_box[1])

    def test_empty_free_text_justification_matches_default_centering(self) -> None:
        default_source = free_text_objects_fixture("FIRST", (50.0, 50.0), "SECOND", (54.0, 50.0))
        empty_justify_source = justify_first_free_text(default_source, "")

        default = self.scan(default_source, unconnected_pins=frozenset())
        explicit_empty = self.scan(empty_justify_source, unconnected_pins=frozenset())

        self.assertEqual(default.status, "COMPLETE")
        self.assertEqual(explicit_empty.status, "COMPLETE")
        self.assertEqual(default.unsupported_by_rule, {})
        self.assertEqual(explicit_empty.unsupported_by_rule, {})
        self.assertEqual(len(default.free_text_overlaps), 1)
        self.assertEqual(len(explicit_empty.free_text_overlaps), 1)
        self.assertEqual(
            default.free_text_overlaps[0].first_box_mm,
            explicit_empty.free_text_overlaps[0].first_box_mm,
        )
        self.assertEqual(
            default.free_text_overlaps[0].second_box_mm,
            explicit_empty.free_text_overlaps[0].second_box_mm,
        )

    def test_separated_free_text_overlap_control_is_clear(self) -> None:
        source = free_text_objects_fixture(
            "LONG_LABEL_ALPHA", (25.4, 25.4), "LONG_LABEL_BETA", (50.8, 25.4)
        )
        result = self.scan(source, unconnected_pins=frozenset())
        self.assertEqual(result.status, "COMPLETE")
        self.assertEqual(result.free_text_overlaps, ())

    def test_free_text_crossing_wire_is_reported(self) -> None:
        result = self.scan(free_text_wire_fixture("WIRE CROSSING FAULT", (88.9, 71.12)))

        self.assertEqual(result.status, "COMPLETE")
        self.assertEqual(len(result.free_text_wire_overlaps), 1)
        finding = result.free_text_wire_overlaps[0]
        self.assertEqual(finding.text, "WIRE CROSSING FAULT")
        self.assertEqual(finding.text_uuid, "f0000000-0000-4000-8000-000000000001")
        self.assertEqual(finding.wire_uuid, "b0000000-0000-4000-8000-000000000005")
        self.assertAlmostEqual(finding.wire_segment_start_mm[1], 71.12)
        self.assertAlmostEqual(finding.wire_segment_end_mm[1], 71.12)
        self.assertGreater(finding.overlap_length_mm, 20.0)

    def test_free_text_wire_overlap_is_translation_invariant_and_wire_move_clears_candidate(
        self,
    ) -> None:
        baseline_source = free_text_wire_fixture("WIRE CROSSING FAULT", (88.9, 71.12))
        translated_source = free_text_wire_fixture(
            "WIRE CROSSING FAULT",
            (188.9, 171.12),
            wire_points=((176.2, 171.12), (201.6, 171.12)),
        )
        baseline = self.scan(baseline_source, unconnected_pins=frozenset())
        translated = self.scan(translated_source, unconnected_pins=frozenset())
        self.assertEqual(len(baseline.free_text_wire_overlaps), 1)
        self.assertEqual(len(translated.free_text_wire_overlaps), 1)
        baseline_finding = baseline.free_text_wire_overlaps[0]
        translated_finding = translated.free_text_wire_overlaps[0]
        self.assertEqual(
            (
                translated_finding.text,
                translated_finding.text_uuid,
                translated_finding.wire_uuid,
                translated_finding.overlap_length_mm,
                translated_finding.sheet_instance_path,
            ),
            (
                baseline_finding.text,
                baseline_finding.text_uuid,
                baseline_finding.wire_uuid,
                baseline_finding.overlap_length_mm,
                baseline_finding.sheet_instance_path,
            ),
        )
        for baseline_box_value, translated_box_value in zip(
            baseline_finding.text_box_mm,
            translated_finding.text_box_mm,
            strict=True,
        ):
            self.assertAlmostEqual(translated_box_value - baseline_box_value, 100.0, places=6)
        for baseline_point, translated_point in zip(
            (baseline_finding.wire_segment_start_mm, baseline_finding.wire_segment_end_mm),
            (translated_finding.wire_segment_start_mm, translated_finding.wire_segment_end_mm),
            strict=True,
        ):
            for baseline_coordinate, translated_coordinate in zip(
                baseline_point,
                translated_point,
                strict=True,
            ):
                self.assertAlmostEqual(translated_coordinate - baseline_coordinate, 100.0)
        self.assertEqual(translated.source_sha256, hashlib.sha256(translated_source).hexdigest())
        self.assertNotEqual(translated.source_sha256, baseline.source_sha256)

        clear_source = free_text_wire_fixture(
            "WIRE CROSSING FAULT",
            (188.9, 171.12),
            wire_points=((176.2, 181.12), (201.6, 181.12)),
        )
        clear = self.scan(clear_source, unconnected_pins=frozenset())
        self.assertEqual(clear.status, "COMPLETE")
        self.assertEqual(clear.free_text_wire_overlaps, ())

    def test_free_text_clear_of_wire_is_valid_control(self) -> None:
        result = self.scan(free_text_wire_fixture("WIRE CLEAR CONTROL", (88.9, 80.01)))

        self.assertEqual(result.status, "COMPLETE")
        self.assertEqual(result.free_text_wire_overlaps, ())

    def test_plain_multiline_text_uses_fault_and_control_geometry(self) -> None:
        fault_text = "TOP\nWIRE CROSSING FAULT\nBOTTOM"
        fault = self.scan(
            free_text_wire_fixture(fault_text, (88.9, 71.12)), unconnected_pins=frozenset()
        )
        control = self.scan(
            free_text_wire_fixture("TOP\nWIRE CLEAR CONTROL\nBOTTOM", (88.9, 80.01)),
            unconnected_pins=frozenset(),
        )

        self.assertEqual(fault.status, "COMPLETE")
        self.assertEqual(fault.unsupported_by_rule, {})
        self.assertEqual(len(fault.free_text_wire_overlaps), 1)
        self.assertEqual(fault.free_text_wire_overlaps[0].text, fault_text)
        self.assertEqual(control.status, "COMPLETE")
        self.assertEqual(control.free_text_wire_overlaps, ())

        overlap_fault = self.scan(
            free_text_objects_fixture("FIRST\nSECOND", (25.4, 25.4), "SECOND", (29.0, 25.4)),
            unconnected_pins=frozenset(),
        )
        overlap_control = self.scan(
            free_text_objects_fixture("FIRST\nSECOND", (25.4, 25.4), "SECOND", (50.8, 25.4)),
            unconnected_pins=frozenset(),
        )
        self.assertEqual(overlap_fault.status, "COMPLETE")
        self.assertEqual(len(overlap_fault.free_text_overlaps), 1)
        self.assertEqual(overlap_control.status, "COMPLETE")
        self.assertEqual(overlap_control.free_text_overlaps, ())

    def test_literal_backslash_n_is_not_treated_as_a_line_break(self) -> None:
        result = self.scan(
            free_text_wire_fixture("LITERAL\\nSEQUENCE", (88.9, 80.01)),
            unconnected_pins=frozenset(),
        )

        self.assertEqual(result.status, "COMPLETE")
        self.assertEqual(result.unsupported_by_rule, {})
        self.assertEqual(result.free_text_wire_overlaps, ())

    def test_free_text_wire_overlap_uses_guard_and_minimum_length(self) -> None:
        too_short = self.scan(
            free_text_wire_fixture(
                "WIRE CROSSING FAULT",
                (88.9, 71.12),
                wire_points=((88.0, 71.12), (88.199, 71.12)),
            )
        )
        at_minimum = self.scan(
            free_text_wire_fixture(
                "WIRE CROSSING FAULT",
                (88.9, 71.12),
                wire_points=((88.0, 71.12), (88.2, 71.12)),
            )
        )
        outside_guard = self.scan(
            free_text_wire_fixture(
                "WIRE CROSSING FAULT",
                (88.9, 71.12),
                wire_points=((88.0, 69.45), (88.5, 69.45)),
            )
        )

        self.assertEqual(too_short.free_text_wire_overlaps, ())
        self.assertEqual(len(at_minimum.free_text_wire_overlaps), 1)
        self.assertEqual(at_minimum.free_text_wire_overlaps[0].overlap_length_mm, 0.2)
        self.assertEqual(outside_guard.free_text_wire_overlaps, ())

    def test_wire_through_symbol_body_is_reported_and_clear_control_is_valid(self) -> None:
        fault = self.scan(symbol_body_wire_fixture(), unconnected_pins=frozenset())
        control = self.scan(
            symbol_body_wire_fixture(((71.12, 82.55), (81.28, 82.55))),
            unconnected_pins=frozenset(),
        )

        self.assertEqual(fault.status, "COMPLETE")
        self.assertEqual(len(fault.wires_through_symbol_bodies), 1)
        finding = fault.wires_through_symbol_bodies[0]
        self.assertEqual((finding.reference, finding.symbol_library_id), ("R1", "Lint:R"))
        self.assertEqual(finding.symbol_uuid, "b0000000-0000-4000-8000-000000000002")
        self.assertEqual(finding.wire_uuid, "f1000000-0000-4000-8000-000000000001")
        self.assertEqual(finding.body_box_mm, (74.93, 73.66, 77.47, 78.74))
        self.assertEqual(finding.overlap_start_mm, (75.13, 76.2))
        self.assertEqual(finding.overlap_end_mm, (77.27, 76.2))
        self.assertEqual(finding.overlap_length_mm, 2.14)
        self.assertEqual(control.status, "COMPLETE")
        self.assertEqual(control.wires_through_symbol_bodies, ())

    def test_unsupported_text_limits_only_text_rule_coverage(self) -> None:
        source = symbol_body_wire_fixture()
        text = (
            b'  (text "UNSUPPORTED~{LINE}" (at 25.4 25.4 0) '
            b"(effects (font (size 1.27 1.27))) "
            b'(uuid "f1000000-0000-4000-8000-000000000009"))\n'
        )
        self.assertEqual(source.count(b"  (sheet_instances"), 1)
        source = source.replace(b"  (sheet_instances", text + b"  (sheet_instances", 1)

        result = self.scan(source, unconnected_pins=frozenset())

        self.assertEqual(result.status, "PARTIAL")
        self.assertEqual(len(result.wires_through_symbol_bodies), 1)
        self.assertIn("schematic.free_text_overlap", result.unsupported_by_rule)
        self.assertIn("schematic.free_text_over_wire", result.unsupported_by_rule)
        self.assertNotIn("schematic.wire_through_symbol_body", result.unsupported_by_rule)

    def test_symbol_body_wire_overlap_uses_guard_and_minimum_length(self) -> None:
        too_short = self.scan(
            symbol_body_wire_fixture(((76.0, 76.2), (76.299, 76.2))),
            unconnected_pins=frozenset(),
        )
        at_minimum = self.scan(
            symbol_body_wire_fixture(((76.0, 76.2), (76.3, 76.2))),
            unconnected_pins=frozenset(),
        )
        outside_guard = self.scan(
            symbol_body_wire_fixture(((74.0, 73.85), (76.0, 73.85))),
            unconnected_pins=frozenset(),
        )

        self.assertEqual(too_short.wires_through_symbol_bodies, ())
        self.assertEqual(len(at_minimum.wires_through_symbol_bodies), 1)
        self.assertEqual(at_minimum.wires_through_symbol_bodies[0].overlap_length_mm, 0.3)
        self.assertEqual(outside_guard.wires_through_symbol_bodies, ())

    def test_peer_connector_contacts_inside_symbol_body_remain_review_candidates(self) -> None:
        enclosed = self.scan(
            enclosed_connector_body_wire_fixture(body_offset_x=0.0),
            unconnected_pins=frozenset(),
        )
        outside = self.scan(
            enclosed_connector_body_wire_fixture(body_offset_x=2.54),
            unconnected_pins=frozenset(),
        )

        self.assertEqual(enclosed.status, "COMPLETE")
        self.assertEqual(
            tuple(
                (candidate.reference, candidate.symbol_library_id, candidate.overlap_length_mm)
                for candidate in enclosed.wires_through_symbol_bodies
            ),
            (
                ("J1", "Connector_Generic:Conn_01x01", 2.34),
                ("J2", "Connector_Generic:Conn_01x01", 2.34),
            ),
        )
        self.assertEqual(outside.status, "COMPLETE")
        self.assertEqual(outside.wires_through_symbol_bodies, ())
        self.assertNotEqual(enclosed.source_sha256, outside.source_sha256)

    def test_symbol_body_wire_tracks_all_supported_orthogonal_transforms(self) -> None:
        semantic_finding: tuple[str, str, str, str, float, str] | None = None
        source_hashes: set[str] = set()
        for angle, mirror in TRANSFORM_MIDPOINTS:
            with self.subTest(angle=angle, mirror=mirror):
                source = transformed_symbol_body_wire(angle, mirror)
                result = self.scan(
                    source,
                    unconnected_pins=frozenset(),
                )
                self.assertEqual(result.status, "COMPLETE")
                self.assertEqual(len(result.wires_through_symbol_bodies), 1)
                finding = result.wires_through_symbol_bodies[0]
                self.assertEqual(finding.overlap_length_mm, 2.14)
                observed_semantics = (
                    finding.reference,
                    finding.symbol_library_id,
                    finding.symbol_uuid,
                    finding.wire_uuid,
                    finding.overlap_length_mm,
                    finding.sheet_instance_path,
                )
                if semantic_finding is None:
                    semantic_finding = observed_semantics
                self.assertEqual(observed_semantics, semantic_finding)
                self.assertEqual(result.source_sha256, hashlib.sha256(source).hexdigest())
                source_hashes.add(result.source_sha256)

                start = _transform_fixture_point((71.12, 76.2), angle, mirror)
                end = _transform_fixture_point((81.28, 76.2), angle, mirror)
                wire_points = f"(xy {start[0]} {start[1]}) (xy {end[0]} {end[1]})".encode()
                reverse_points = f"(xy {end[0]} {end[1]}) (xy {start[0]} {start[1]})".encode()
                self.assertEqual(source.count(wire_points), 1)
                reversed_source = source.replace(wire_points, reverse_points, 1)
                reversed_result = self.scan(reversed_source, unconnected_pins=frozenset())
                self.assertEqual(reversed_result.status, "COMPLETE")
                self.assertEqual(len(reversed_result.wires_through_symbol_bodies), 1)
                reversed_finding = reversed_result.wires_through_symbol_bodies[0]
                self.assertEqual(
                    (
                        reversed_finding.reference,
                        reversed_finding.symbol_library_id,
                        reversed_finding.symbol_uuid,
                        reversed_finding.wire_uuid,
                        reversed_finding.overlap_length_mm,
                        reversed_finding.sheet_instance_path,
                    ),
                    observed_semantics,
                )

        self.assertIsNotNone(semantic_finding)
        self.assertGreater(len(source_hashes), 1)

        baseline = transformed_symbol_body_wire(0, None)
        wire_points = b"(xy 71.12 76.2) (xy 81.28 76.2)"
        clear_points = b"(xy 71.12 82.55) (xy 81.28 82.55)"
        self.assertEqual(baseline.count(wire_points), 1)
        clear_source = baseline.replace(wire_points, clear_points, 1)
        clear = self.scan(clear_source, unconnected_pins=frozenset())
        self.assertEqual(clear.status, "COMPLETE")
        self.assertEqual(clear.wires_through_symbol_bodies, ())

    def test_free_text_over_symbol_body_is_reported_with_clear_control(self) -> None:
        fault = self.scan(free_text_symbol_body_fixture(), unconnected_pins=frozenset())
        control = self.scan(
            free_text_symbol_body_fixture(point=(88.9, 76.2)),
            unconnected_pins=frozenset(),
        )

        self.assertEqual(fault.status, "COMPLETE")
        self.assertEqual(len(fault.free_text_symbol_body_overlaps), 1)
        finding = fault.free_text_symbol_body_overlaps[0]
        self.assertEqual(finding.text, "BODY NOTE")
        self.assertEqual(finding.text_uuid, "f2000000-0000-4000-8000-000000000001")
        self.assertEqual((finding.reference, finding.symbol_library_id), ("R1", "Lint:R"))
        self.assertEqual(finding.body_box_mm, (74.93, 73.66, 77.47, 78.74))
        self.assertEqual(finding.overlap_box_mm, (75.08, 74.798987, 77.32, 77.209091))
        self.assertEqual(finding.overlap_area_mm2, 5.398633)
        self.assertEqual(control.status, "COMPLETE")
        self.assertEqual(control.free_text_symbol_body_overlaps, ())

    def test_text_body_overlap_is_root_order_stable_and_moving_text_clears_candidate(
        self,
    ) -> None:
        source = free_text_symbol_body_fixture()
        baseline = self.scan(source, unconnected_pins=frozenset())
        self.assertEqual(len(baseline.free_text_symbol_body_overlaps), 1)
        text_line = next(
            line
            for line in source.splitlines(keepends=True)
            if b'uuid "f2000000-0000-4000-8000-000000000001"' in line
        )
        self.assertEqual(source.count(text_line), 1)
        without_text = source.replace(text_line, b"", 1)
        reordered_source = without_text.replace(b"  (wire (pts", text_line + b"  (wire (pts", 1)
        reordered = self.scan(reordered_source, unconnected_pins=frozenset())
        self.assertEqual(reordered.status, "COMPLETE")
        self.assertEqual(len(reordered.free_text_symbol_body_overlaps), 1)
        baseline_finding = baseline.free_text_symbol_body_overlaps[0]
        reordered_finding = reordered.free_text_symbol_body_overlaps[0]
        self.assertEqual(
            (
                reordered_finding.text,
                reordered_finding.text_uuid,
                reordered_finding.reference,
                reordered_finding.symbol_library_id,
                reordered_finding.symbol_uuid,
                reordered_finding.body_box_mm,
                reordered_finding.overlap_box_mm,
                reordered_finding.overlap_area_mm2,
                reordered_finding.sheet_instance_path,
            ),
            (
                baseline_finding.text,
                baseline_finding.text_uuid,
                baseline_finding.reference,
                baseline_finding.symbol_library_id,
                baseline_finding.symbol_uuid,
                baseline_finding.body_box_mm,
                baseline_finding.overlap_box_mm,
                baseline_finding.overlap_area_mm2,
                baseline_finding.sheet_instance_path,
            ),
        )
        self.assertNotEqual(reordered.source_sha256, baseline.source_sha256)

        moved_text_line = text_line.replace(
            b"(at 76.2 76.2 0)",
            b"(at 88.9 76.2 0)",
            1,
        )
        moved_source = source.replace(text_line, moved_text_line, 1)
        moved = self.scan(moved_source, unconnected_pins=frozenset())
        self.assertEqual(moved.status, "COMPLETE")
        self.assertEqual(moved.free_text_symbol_body_overlaps, ())

    def test_free_text_symbol_body_overlap_uses_area_threshold(self) -> None:
        below = self.scan(
            free_text_symbol_body_fixture(point=(76.2, 72.84)),
            unconnected_pins=frozenset(),
        )
        above = self.scan(
            free_text_symbol_body_fixture(point=(76.2, 72.85)),
            unconnected_pins=frozenset(),
        )

        self.assertEqual(below.free_text_symbol_body_overlaps, ())
        self.assertEqual(len(above.free_text_symbol_body_overlaps), 1)
        self.assertGreaterEqual(above.free_text_symbol_body_overlaps[0].overlap_area_mm2, 0.1)

    def test_unsupported_symbol_body_primitive_makes_coverage_partial(self) -> None:
        source = symbol_body_wire_fixture().replace(b"(rectangle", b"(arc", 1)
        result = self.scan(source, unconnected_pins=frozenset())

        self.assertEqual(result.status, "PARTIAL")
        self.assertEqual(result.wires_through_symbol_bodies, ())
        self.assertTrue(
            any("primitive 'arc' is unsupported" in item for item in result.unsupported)
        )

    def test_unsupported_free_text_variants_leave_geometry_coverage_partial(self) -> None:
        overlap = (25.4, 25.4)
        base = free_text_objects_fixture("FIRST", overlap, "SECOND", (29.0, 25.4))

        def replace_once(source: bytes, old: bytes, new: bytes) -> bytes:
            start = source.index(b'(text "FIRST"')
            end_marker = b'(uuid "d0000000-0000-4000-8000-000000000001"))'
            end = source.index(end_marker, start) + len(end_marker)
            text_node = source[start:end]
            self.assertEqual(text_node.count(old), 1)
            return source[:start] + text_node.replace(old, new, 1) + source[end:]

        variants = (
            (
                "custom face",
                replace_once(
                    base,
                    b"(font (size 1.27 1.27))",
                    b'(font (face "Synthetic Custom Font") (size 1.27 1.27))',
                ),
                "custom",
            ),
            (
                "bold",
                replace_once(
                    base,
                    b"(font (size 1.27 1.27))",
                    b"(font (bold yes) (size 1.27 1.27))",
                ),
                "bold",
            ),
            (
                "italic",
                replace_once(
                    base,
                    b"(font (size 1.27 1.27))",
                    b"(font (italic yes) (size 1.27 1.27))",
                ),
                "italic",
            ),
            (
                "thick stroke",
                replace_once(
                    base,
                    b"(font (size 1.27 1.27))",
                    b"(font (size 1.27 1.27) (thickness 0.2))",
                ),
                "thick",
            ),
            (
                "vertical justification",
                replace_once(
                    base,
                    b"(effects (font (size 1.27 1.27)))",
                    b"(effects (font (size 1.27 1.27)) (justify top))",
                ),
                "vertical alignment",
            ),
            (
                "combined justification",
                replace_once(
                    base,
                    b"(effects (font (size 1.27 1.27)))",
                    b"(effects (font (size 1.27 1.27)) (justify left right))",
                ),
                "horizontal left or right",
            ),
            (
                "mirrored text",
                replace_once(
                    base,
                    b"(effects (font (size 1.27 1.27)))",
                    b"(effects (font (size 1.27 1.27)) (justify mirror))",
                ),
                "mirrored text",
            ),
            (
                "rotation",
                replace_once(
                    base,
                    b'(text "FIRST" (at 25.4 25.4 0)',
                    b'(text "FIRST" (at 25.4 25.4 45)',
                ),
                "rotation",
            ),
            (
                "formatted text",
                free_text_objects_fixture("F~{IR}ST", overlap, "SECOND", (29.0, 25.4)),
                "formatted",
            ),
            (
                "literal source newline",
                replace_once(base, b'"FIRST"', b'"FIRST\nSECOND"'),
                "literal source line breaks",
            ),
            (
                "glyph outside calibrated set",
                free_text_objects_fixture("FÜRST", overlap, "SECOND", (29.0, 25.4)),
                "glyphs outside",
            ),
        )

        for name, source, expected_issue in variants:
            with self.subTest(name=name):
                result = self.scan(source, unconnected_pins=frozenset())
                self.assertEqual(result.status, "PARTIAL")
                self.assertEqual(result.free_text_overlaps, ())
                self.assertEqual(result.free_text_wire_overlaps, ())
                self.assertEqual(result.free_text_symbol_body_overlaps, ())
                self.assertTrue(
                    any(expected_issue in issue.casefold() for issue in result.unsupported),
                    result.unsupported,
                )

    def test_pin_on_wire_middle_without_junction_is_localized(self) -> None:
        result = self.scan(
            PIN_ON_WIRE_MIDDLE_FAULT.read_bytes(),
        )
        self.assertEqual(result.status, "COMPLETE")
        self.assertEqual(result.findings, ())
        self.assertEqual(len(result.pin_tip_on_wire_interiors), 1)
        finding = result.pin_tip_on_wire_interiors[0]
        self.assertEqual((finding.reference, finding.pin_number), ("R1", "1"))
        self.assertEqual(finding.pin_tip_mm, (76.2, 71.12))
        self.assertEqual(finding.wire_segment_start_mm, (50.8, 71.12))
        self.assertEqual(finding.wire_segment_end_mm, (101.6, 71.12))

    def test_wire_endpoint_just_short_of_pin_tip_is_localized(self) -> None:
        source = WIRE_END_NEAR_PIN_TIP_FAULT.read_bytes()
        result = self.scan(source)
        self.assertEqual(result.status, "COMPLETE")
        self.assertEqual(result.findings, ())
        self.assertEqual(result.pin_tip_on_wire_interiors, ())
        self.assertEqual(len(result.wire_endpoints_near_pin_tips), 1)
        finding = result.wire_endpoints_near_pin_tips[0]
        self.assertEqual((finding.reference, finding.pin_number), ("R1", "1"))
        self.assertEqual(finding.pin_tip_mm, (76.2, 71.12))
        self.assertEqual(finding.wire_endpoint_mm, (76.2, 70.62))
        self.assertEqual(finding.distance_to_pin_tip_mm, MAX_PIN_ENDPOINT_GAP_MM)

    def test_wire_endpoint_gap_boundary_and_controls(self) -> None:
        fixture = WIRE_END_NEAR_PIN_TIP_FAULT.read_bytes()
        self.assertEqual(len(self.scan(fixture).wire_endpoints_near_pin_tips), 1)

        outside = fixture.replace(b"76.2 70.62", b"76.2 70.619", 1)
        outside = outside.replace(b"101.6 70.62", b"101.6 70.619", 1)
        self.assertEqual(self.scan(outside).wire_endpoints_near_pin_tips, ())

        on_pin_segment = fixture.replace(b"76.2 70.62", b"76.2 71.42", 1)
        self.assertEqual(self.scan(on_pin_segment).wire_endpoints_near_pin_tips, ())
        self.assertEqual(len(self.scan(on_pin_segment).findings), 1)

        connected = self.scan(CONTROL.read_bytes(), unconnected_pins=frozenset())
        self.assertEqual(connected.wire_endpoints_near_pin_tips, ())

        non_native_open_pin = self.scan(fixture, unconnected_pins=frozenset({"R1.2"}))
        self.assertEqual(non_native_open_pin.wire_endpoints_near_pin_tips, ())

    def test_wire_endpoint_near_pin_tip_tracks_all_supported_symbol_transforms(self) -> None:
        semantic_finding: tuple[str, str, float] | None = None
        source_hashes: set[str] = set()
        for transform, expected_endpoint in TRANSFORM_NEAR_PIN_ENDPOINTS.items():
            with self.subTest(transform=transform):
                source = transformed_near_pin_tip_wire(*transform)
                result = self.scan(source)
                self.assertEqual(result.status, "COMPLETE")
                self.assertEqual(result.findings, ())
                self.assertEqual(result.pin_tip_on_wire_interiors, ())
                self.assertEqual(len(result.wire_endpoints_near_pin_tips), 1)
                finding = result.wire_endpoints_near_pin_tips[0]
                observed_semantics = (
                    finding.reference,
                    finding.pin_number,
                    finding.distance_to_pin_tip_mm,
                )
                if semantic_finding is None:
                    semantic_finding = observed_semantics
                self.assertEqual(observed_semantics, semantic_finding)
                self.assertEqual(result.source_sha256, hashlib.sha256(source).hexdigest())
                source_hashes.add(result.source_sha256)
                self.assertEqual(finding.pin_tip_mm, TRANSFORM_PIN_TIPS[transform])
                self.assertEqual(finding.wire_endpoint_mm, expected_endpoint)
                self.assertEqual(
                    finding.distance_to_pin_tip_mm,
                    MAX_PIN_ENDPOINT_GAP_MM,
                )
        self.assertGreater(len(source_hashes), 1)

        baseline = transformed_near_pin_tip_wire(0, None)
        outside = baseline.replace(b"(xy 76.2 70.62)", b"(xy 76.2 70.619)", 1)
        outside = outside.replace(b"(xy 101.6 70.62)", b"(xy 101.6 70.619)", 1)
        outside = outside.replace(
            b'(label "FAULT_NET" (at 101.6 70.62 0)',
            b'(label "FAULT_NET" (at 101.6 70.619 0)',
            1,
        )
        repaired = self.scan(outside)
        self.assertEqual(repaired.status, "COMPLETE")
        self.assertEqual(repaired.wire_endpoints_near_pin_tips, ())

    def test_no_connect_marker_excludes_wire_endpoint_near_pin_tip(self) -> None:
        source = WIRE_END_NEAR_PIN_TIP_FAULT.read_bytes().replace(
            b"  (wire (pts",
            b'  (no_connect (at 76.2 71.12) (uuid "c0000000-0000-4000-8000-000000000007"))\n'
            b"  (wire (pts",
            1,
        )
        self.assertEqual(self.scan(source).wire_endpoints_near_pin_tips, ())

    def test_junction_control_is_excluded_when_native_netlist_marks_pin_connected(self) -> None:
        result = self.scan(
            PIN_ON_WIRE_MIDDLE_CONTROL.read_bytes(),
            unconnected_pins=frozenset(),
        )
        self.assertEqual(result.status, "COMPLETE")
        self.assertEqual(result.findings, ())
        self.assertEqual(result.pin_tip_on_wire_interiors, ())

    def test_label_near_wire_endpoint_is_localized(self) -> None:
        source = LABEL_NEAR_WIRE_ENDPOINT.read_bytes()
        result = self.scan(source, unconnected_pins=frozenset())

        self.assertEqual(result.status, "COMPLETE")
        self.assertEqual(result.source_sha256, hashlib.sha256(source).hexdigest())
        self.assertEqual(len(result.labels_near_wire_endpoints), 1)
        finding = result.labels_near_wire_endpoints[0]
        self.assertEqual(finding.label_kind, "label")
        self.assertEqual(finding.text, "CONTROL_NET")
        self.assertEqual(finding.label_uuid, "b0000000-0000-4000-8000-000000000006")
        self.assertEqual(finding.anchor_mm, (102.1, 71.12))
        self.assertEqual(len(finding.candidates), 1)
        self.assertEqual(finding.candidates[0].wire_uuid, "b0000000-0000-4000-8000-000000000005")
        self.assertEqual(finding.candidates[0].wire_endpoint_mm, (101.6, 71.12))
        self.assertEqual(finding.candidates[0].distance_mm, 0.5)

    def test_label_near_endpoint_is_translation_invariant_and_attachment_clears_candidate(
        self,
    ) -> None:
        source = LABEL_NEAR_WIRE_ENDPOINT.read_bytes()
        baseline = self.scan(source, unconnected_pins=frozenset())
        self.assertEqual(len(baseline.labels_near_wire_endpoints), 1)

        wire_points = b"(xy 76.2 71.12) (xy 101.6 71.12)"
        translated_wire_points = b"(xy 126.2 121.12) (xy 151.6 121.12)"
        label_anchor = b'(label "CONTROL_NET" (at 102.1 71.12 0)'
        translated_anchor = b'(label "CONTROL_NET" (at 152.1 121.12 0)'
        self.assertEqual(source.count(wire_points), 1)
        self.assertEqual(source.count(label_anchor), 1)
        translated_source = source.replace(wire_points, translated_wire_points, 1).replace(
            label_anchor,
            translated_anchor,
            1,
        )
        translated = self.scan(translated_source, unconnected_pins=frozenset())
        self.assertEqual(translated.status, "COMPLETE")
        self.assertEqual(len(translated.labels_near_wire_endpoints), 1)
        baseline_finding = baseline.labels_near_wire_endpoints[0]
        translated_finding = translated.labels_near_wire_endpoints[0]
        baseline_semantics = (
            baseline_finding.label_kind,
            baseline_finding.text,
            baseline_finding.label_uuid,
            tuple((item.wire_uuid, item.distance_mm) for item in baseline_finding.candidates),
        )
        translated_semantics = (
            translated_finding.label_kind,
            translated_finding.text,
            translated_finding.label_uuid,
            tuple((item.wire_uuid, item.distance_mm) for item in translated_finding.candidates),
        )
        self.assertEqual(translated_semantics, baseline_semantics)
        self.assertEqual(translated_finding.anchor_mm, (152.1, 121.12))
        self.assertEqual(translated_finding.candidates[0].wire_endpoint_mm, (151.6, 121.12))
        self.assertEqual(translated.source_sha256, hashlib.sha256(translated_source).hexdigest())
        self.assertNotEqual(translated.source_sha256, baseline.source_sha256)

        attached_source = translated_source.replace(
            translated_anchor,
            b'(label "CONTROL_NET" (at 151.6 121.12 0)',
            1,
        )
        attached = self.scan(attached_source, unconnected_pins=frozenset())
        self.assertEqual(attached.status, "COMPLETE")
        self.assertEqual(attached.labels_near_wire_endpoints, ())

    def test_unmarked_orthogonal_wire_interiors_are_review_candidates(self) -> None:
        source = UNMARKED_CROSSING.read_bytes()
        result = self.scan(source, unconnected_pins=frozenset())

        self.assertEqual(result.status, "COMPLETE")
        self.assertEqual(result.source_sha256, hashlib.sha256(source).hexdigest())
        self.assertEqual(len(result.unmarked_wire_crossings), 1)
        finding = result.unmarked_wire_crossings[0]
        self.assertEqual(finding.crossing_mm, (127.0, 127.0))
        self.assertEqual(
            finding.wire_uuids,
            (
                "c0000000-0000-4000-8000-000000000008",
                "c0000000-0000-4000-8000-000000000009",
            ),
        )

    def test_unmarked_crossing_is_stable_under_wire_order_and_marker_repairs_it(self) -> None:
        source = UNMARKED_CROSSING.read_bytes()
        wire_blocks = {
            match.group(1).decode("ascii"): match
            for match in re.finditer(rb'(?ms)^  \(wire\b.*?^    \(uuid "([^"]+)"\)\)', source)
        }
        horizontal = wire_blocks["c0000000-0000-4000-8000-000000000008"]
        vertical = wire_blocks["c0000000-0000-4000-8000-000000000009"]
        self.assertLess(horizontal.start(), vertical.start())
        reordered_source = (
            source[: horizontal.start()]
            + vertical.group(0)
            + source[horizontal.end() : vertical.start()]
            + horizontal.group(0)
            + source[vertical.end() :]
        )

        original = self.scan(source, unconnected_pins=frozenset())
        reordered = self.scan(reordered_source, unconnected_pins=frozenset())
        self.assertNotEqual(original.source_sha256, reordered.source_sha256)
        self.assertEqual(original.unmarked_wire_crossings, reordered.unmarked_wire_crossings)
        self.assertEqual(len(reordered.unmarked_wire_crossings), 1)

        sheet_instances = b"  (sheet_instances"
        self.assertEqual(source.count(sheet_instances), 1)
        junction = (
            b"  (junction (at 127 127) (diameter 0) (color 0 0 0 0)\n"
            b'    (uuid "c0000000-0000-4000-8000-000000000010"))\n'
        )
        repaired_source = source.replace(sheet_instances, junction + sheet_instances, 1)
        repaired = self.scan(repaired_source, unconnected_pins=frozenset())
        self.assertEqual(repaired.status, "COMPLETE")
        self.assertEqual(repaired.unmarked_wire_crossings, ())

    def test_explicit_junction_and_endpoint_touch_are_excluded(self) -> None:
        marked = self.scan(JUNCTION_MARKED_CROSSING.read_bytes(), unconnected_pins=frozenset())
        self.assertEqual(marked.status, "COMPLETE")
        self.assertEqual(marked.unmarked_wire_crossings, ())

        endpoint_touch = UNMARKED_CROSSING.read_bytes().replace(
            b"(xy 114.3 127)", b"(xy 127 127)", 1
        )
        touched = self.scan(endpoint_touch, unconnected_pins=frozenset())
        self.assertEqual(touched.unmarked_wire_crossings, ())

    def test_graphical_polyline_crossing_a_wire_is_not_an_electrical_candidate(self) -> None:
        source = GRAPHICAL_ONLY_CROSSING.read_bytes()
        baseline_source = _graphical_crossing_baseline()
        result = self.scan(source, unconnected_pins=frozenset())
        baseline = self.scan(baseline_source, unconnected_pins=frozenset())

        self.assertEqual(source.count(b"(polyline "), 1)
        self.assertEqual(source.count(b"(rectangle (start 85.09 69.85)"), 1)
        self.assertEqual(source.count(b"(circle (center 95.25 71.12)"), 1)
        self.assertEqual(result.status, "COMPLETE")
        self.assertEqual(result.unsupported_by_rule, {})
        self.assertEqual(_geometry_candidates(result), _geometry_candidates(baseline))

    def test_unmarked_t_junction_is_review_candidate(self) -> None:
        result = self.scan(T_JUNCTION_FAULT.read_bytes(), unconnected_pins=frozenset({"R1.2"}))

        self.assertEqual(result.status, "COMPLETE")
        self.assertEqual(len(result.unmarked_t_junctions), 1)
        finding = result.unmarked_t_junctions[0]
        self.assertEqual(finding.endpoint_wire_uuid, "c0000000-0000-4000-8000-000000000012")
        self.assertEqual(finding.interior_wire_uuid, "b0000000-0000-4000-8000-000000000005")
        self.assertEqual(finding.junction_mm, (88.9, 71.12))

    def test_unmarked_t_junction_is_wire_order_stable_and_marker_clears_candidate(self) -> None:
        source = T_JUNCTION_FAULT.read_bytes()

        def semantic_findings(result: SchematicGeometryScan) -> tuple[tuple[object, ...], ...]:
            return tuple(
                (
                    finding.endpoint_wire_uuid,
                    finding.interior_wire_uuid,
                    finding.junction_mm,
                    finding.sheet_instance_path,
                )
                for finding in result.unmarked_t_junctions
            )

        fault = self.scan(source, unconnected_pins=frozenset({"R1.2"}))
        self.assertEqual(fault.status, "COMPLETE")
        self.assertEqual(len(fault.unmarked_t_junctions), 1)
        self.assertEqual(fault.source_sha256, hashlib.sha256(source).hexdigest())
        expected = semantic_findings(fault)

        wire_records = re.findall(rb"(?m)^  \(wire .*\n", source)
        self.assertEqual(len(wire_records), 3)
        t_wire_records = wire_records[-2:]
        reordered_source = source
        for record in t_wire_records:
            self.assertEqual(reordered_source.count(record), 1)
            reordered_source = reordered_source.replace(record, b"", 1)
        reordered_source = reordered_source.replace(
            b"  (sheet_instances",
            b"".join(reversed(t_wire_records)) + b"  (sheet_instances",
            1,
        )
        reordered = self.scan(reordered_source, unconnected_pins=frozenset({"R1.2"}))
        self.assertEqual(reordered.status, "COMPLETE")
        self.assertEqual(semantic_findings(reordered), expected)
        self.assertNotEqual(reordered.source_sha256, fault.source_sha256)

        marker = (
            b"  (junction (at 88.9 71.12) (diameter 0) (color 0 0 0 0)\n"
            b'    (uuid "c0000000-0000-4000-8000-000000000099"))\n'
        )
        marked_source = source.replace(b"  (sheet_instances", marker + b"  (sheet_instances", 1)
        marked = self.scan(marked_source, unconnected_pins=frozenset({"R1.2"}))
        self.assertEqual(marked.status, "COMPLETE")
        self.assertEqual(marked.unmarked_t_junctions, ())

    def test_explicit_t_junction_marker_is_excluded(self) -> None:
        result = self.scan(T_JUNCTION_CONTROL.read_bytes(), unconnected_pins=frozenset())

        self.assertEqual(result.status, "COMPLETE")
        self.assertEqual(result.unmarked_t_junctions, ())

    def test_t_junction_tolerance_and_segment_endpoint_boundary(self) -> None:
        source = T_JUNCTION_FAULT.read_bytes()
        within_tolerance = source.replace(
            b"(xy 88.9 71.12) (xy 88.9 81.28)",
            b"(xy 88.9 71.121) (xy 88.9 81.28)",
            1,
        )
        near = self.scan(within_tolerance, unconnected_pins=frozenset({"R1.2"}))
        self.assertEqual(len(near.unmarked_t_junctions), 1)
        self.assertEqual(near.unmarked_t_junctions[0].junction_mm, (88.9, 71.121))

        outside_tolerance = source.replace(
            b"(xy 88.9 71.12) (xy 88.9 81.28)",
            b"(xy 88.9 71.122) (xy 88.9 81.28)",
            1,
        )
        far = self.scan(outside_tolerance, unconnected_pins=frozenset({"R1.2"}))
        self.assertEqual(far.unmarked_t_junctions, ())

        endpoint_contact = source.replace(
            b"(xy 88.9 71.12) (xy 88.9 81.28)",
            b"(xy 76.2 71.12) (xy 76.2 81.28)",
            1,
        )
        endpoint = self.scan(endpoint_contact, unconnected_pins=frozenset({"R1.2"}))
        self.assertEqual(endpoint.unmarked_t_junctions, ())

    def test_attached_interior_and_far_labels_are_excluded(self) -> None:
        attached = self.scan(CONTROL.read_bytes(), unconnected_pins=frozenset())
        self.assertEqual(attached.labels_near_wire_endpoints, ())

        fixture = LABEL_NEAR_WIRE_ENDPOINT.read_bytes()
        on_wire_interior = fixture.replace(b"(at 102.1 71.12 0)", b"(at 90 71.12 0)", 1)
        self.assertEqual(
            self.scan(on_wire_interior, unconnected_pins=frozenset()).labels_near_wire_endpoints,
            (),
        )

        on_pin_tip = fixture.replace(b"(at 102.1 71.12 0)", b"(at 76.2 71.12 0)", 1)
        self.assertEqual(
            self.scan(on_pin_tip, unconnected_pins=frozenset()).labels_near_wire_endpoints,
            (),
        )

        far_from_wire = fixture.replace(b"(at 102.1 71.12 0)", b"(at 103.21 71.12 0)", 1)
        self.assertEqual(
            self.scan(far_from_wire, unconnected_pins=frozenset()).labels_near_wire_endpoints,
            (),
        )

    def test_label_endpoint_search_radius_includes_boundary_only(self) -> None:
        control = CONTROL.read_bytes()
        at_boundary = control.replace(b"(at 101.6 71.12 0)", b"(at 102.87 71.12 0)", 1)
        boundary_result = self.scan(at_boundary, unconnected_pins=frozenset())
        self.assertEqual(len(boundary_result.labels_near_wire_endpoints), 1)
        candidate = boundary_result.labels_near_wire_endpoints[0].candidates[0]
        self.assertEqual(candidate.distance_mm, 1.27)

        outside_boundary = control.replace(b"(at 101.6 71.12 0)", b"(at 102.871 71.12 0)", 1)
        self.assertEqual(
            self.scan(outside_boundary, unconnected_pins=frozenset()).labels_near_wire_endpoints,
            (),
        )

    def test_no_connect_marker_excludes_pin_tip_on_wire_interior(self) -> None:
        source = PIN_ON_WIRE_MIDDLE_FAULT.read_bytes().replace(
            b"  (sheet_instances",
            b'  (no_connect (at 76.2 71.12) (uuid "e0000000-0000-4000-8000-000000000009"))\n'
            b"  (sheet_instances",
            1,
        )
        result = self.scan(source)
        self.assertEqual(result.findings, ())
        self.assertEqual(result.pin_tip_on_wire_interiors, ())

    def test_pin_tip_on_wire_interior_tracks_all_supported_symbol_transforms(self) -> None:
        semantic_finding: tuple[str, str, str, str, float, str] | None = None
        source_hashes: set[str] = set()
        for transform, pin_tip in TRANSFORM_PIN_TIPS.items():
            with self.subTest(transform=transform):
                source = transformed_pin_tip_wire(*transform, pin_tip)
                result = self.scan(source)
                self.assertEqual(result.status, "COMPLETE")
                self.assertEqual(result.findings, ())
                self.assertEqual(len(result.pin_tip_on_wire_interiors), 1)
                finding = result.pin_tip_on_wire_interiors[0]
                observed_semantics = (
                    finding.reference,
                    finding.pin_number,
                    finding.pin_name,
                    finding.wire_uuid,
                    finding.distance_to_wire_mm,
                    finding.sheet_instance_path,
                )
                if semantic_finding is None:
                    semantic_finding = observed_semantics
                self.assertEqual(observed_semantics, semantic_finding)
                self.assertEqual(result.source_sha256, hashlib.sha256(source).hexdigest())
                source_hashes.add(result.source_sha256)
                self.assertEqual(finding.pin_tip_mm, pin_tip)
                self.assertEqual(
                    finding.wire_segment_start_mm,
                    (round(pin_tip[0] - 25.4, 6), pin_tip[1]),
                )
                self.assertEqual(
                    finding.wire_segment_end_mm,
                    (round(pin_tip[0] + 25.4, 6), pin_tip[1]),
                )

                # Segment direction is incidental: reversing its endpoints must
                # preserve the same pin-to-wire observation.
                start_x = round(pin_tip[0] - 25.4, 6)
                end_x = round(pin_tip[0] + 25.4, 6)
                y = round(pin_tip[1], 6)
                forward = f"(xy {start_x} {y}) (xy {end_x} {y})".encode()
                reverse = f"(xy {end_x} {y}) (xy {start_x} {y})".encode()
                self.assertEqual(source.count(forward), 1)
                reversed_source = source.replace(forward, reverse, 1)
                reversed_result = self.scan(reversed_source)
                self.assertEqual(reversed_result.status, "COMPLETE")
                self.assertEqual(
                    tuple(
                        (
                            item.reference,
                            item.pin_number,
                            item.pin_name,
                            item.wire_uuid,
                            item.distance_to_wire_mm,
                            item.sheet_instance_path,
                        )
                        for item in reversed_result.pin_tip_on_wire_interiors
                    ),
                    (semantic_finding,),
                )

                # A small causal offset removes the geometric contact while
                # leaving the pin's native unconnected state unchanged.
                offset_y = round(y + 0.01, 6)
                moved = source.replace(
                    forward,
                    f"(xy {start_x} {offset_y}) (xy {end_x} {offset_y})".encode(),
                    1,
                )
                self.assertNotEqual(moved, source)
                repaired = self.scan(moved)
                self.assertEqual(repaired.status, "COMPLETE")
                self.assertEqual(repaired.pin_tip_on_wire_interiors, ())

        self.assertIsNotNone(semantic_finding)
        self.assertGreater(len(source_hashes), 1)

    def test_no_connect_marker_and_off_line_endpoint_are_excluded(self) -> None:
        source = FAULT.read_bytes()
        source = source.replace(
            b"  (wire (pts",
            b'  (no_connect (at 76.2 71.12) (uuid "a0000000-0000-4000-8000-000000000007"))\n'
            b"  (wire (pts",
            1,
        )
        self.assertEqual(self.scan(source).findings, ())

        offset = FAULT.read_bytes().replace(b"76.2 72.39", b"76.21 72.39", 1)
        self.assertEqual(self.scan(offset).findings, ())

    def test_exact_kicad_version_format_and_sheet_scope_are_enforced(self) -> None:
        supported_patch_version = self.scan(FAULT.read_bytes(), version="10.0.5")
        self.assertEqual(supported_patch_version.status, "COMPLETE")
        self.assertEqual(len(supported_patch_version.findings), 1)

        wrong_version = self.scan(FAULT.read_bytes(), version="10.0.0")
        self.assertEqual(wrong_version.status, "UNSUPPORTED")
        self.assertFalse(wrong_version.findings)
        self.assertIn("10.0.5", wrong_version.unsupported[0])
        self.assertIn("10.0.6", wrong_version.unsupported[0])

        wrong_format = self.scan(FAULT.read_bytes().replace(b"20231120", b"20250101", 1))
        self.assertEqual(wrong_format.status, "UNSUPPORTED")
        self.assertEqual(wrong_format.schematic_version, "20250101")

        hierarchical = self.scan(
            FAULT.read_bytes().replace(
                b"  (sheet_instances",
                b"  (sheet (at 0 0) (size 10 10))\n  (sheet_instances",
                1,
            )
        )
        self.assertEqual(hierarchical.status, "UNSUPPORTED")
        self.assertIn("Hierarchical", hierarchical.unsupported[0])

    def test_single_file_scanner_rejects_hierarchy_without_tree_context(self) -> None:
        result = self.scan(
            REPEATED_SHEET.read_bytes(),
            unconnected_pins=frozenset({"R1.2", "R2.2"}),
        )

        self.assertEqual(result.status, "UNSUPPORTED")
        self.assertIn("Hierarchical", result.unsupported[0])
        self.assertEqual(result.findings, ())
        control = self.scan(
            REPEATED_SHEET_CONTROL.read_bytes(),
            unconnected_pins=frozenset(),
        )
        self.assertEqual(control.status, "UNSUPPORTED")

    def test_kicad8_sheet_property_names_bind_reused_child_instances(self) -> None:
        legacy_root = (
            REPEATED_SHEET.read_bytes()
            .replace(b'"Sheet name"', b'"Sheetname"')
            .replace(b'"Sheet file"', b'"Sheetfile"')
        )
        result = scan_schematic_geometry_tree(
            {
                REPEATED_SHEET.name: legacy_root,
                REPEATED_CHANNEL.name: REPEATED_CHANNEL.read_bytes(),
            },
            root_path=REPEATED_SHEET.name,
            project_directory=".",
            project_name=REPEATED_SHEET.stem,
            kicad_version=SUPPORTED_KICAD_VERSION,
            unconnected_pins=frozenset({"R1.2", "R2.2"}),
        )

        self.assertEqual(result.status, "COMPLETE")
        self.assertEqual(len(result.source_bindings), 3)
        self.assertEqual(
            {binding.sheet_path for binding in result.source_bindings},
            {(), ("InstanceA",), ("InstanceB",)},
        )

    def test_duplicate_legacy_and_current_sheet_property_aliases_fail_closed(self) -> None:
        source = REPEATED_SHEET.read_bytes().replace(b'"Sheet name"', b'"Sheetname"', 1)
        duplicate = (
            b'(property "Sheet name" "InstanceA" (id 2) (at 50 49.3 0) '
            b"(effects (font (size 1.27 1.27))))\n    "
        )
        source = source.replace(
            b'(property "Sheetname" "InstanceA"',
            duplicate + b'(property "Sheetname" "InstanceA"',
            1,
        )

        with self.assertRaisesRegex(ValueError, "Duplicate KiCad property aliases"):
            schematic_sheet_references(source)

    def test_reused_sheet_tree_maps_geometry_to_each_instance_reference(self) -> None:
        repeated_channel = REPEATED_CHANNEL.read_text(encoding="utf-8").replace(
            "  (sheet_instances",
            '  (text "CHANNEL_A" (at 25.4 25.4 0) '
            "(effects (font (size 1.27 1.27))) "
            '(uuid "e0000000-0000-4000-8000-000000000001"))\n'
            '  (text "CHANNEL_B" (at 25.4 25.4 0) '
            "(effects (font (size 1.27 1.27))) "
            '(uuid "e0000000-0000-4000-8000-000000000002"))\n'
            '  (text "LONG_LABEL_ALPHA" (at 120 25.4 0) '
            "(effects (font (size 1.27 1.27))) "
            '(uuid "e0000000-0000-4000-8000-000000000003"))\n'
            '  (text "LONG_LABEL_BETA" (at 123.6 25.4 0) '
            "(effects (font (size 1.27 1.27))) "
            '(uuid "e0000000-0000-4000-8000-000000000004"))\n'
            "  (sheet_instances",
            1,
        )
        fault = scan_schematic_geometry_tree(
            {
                REPEATED_SHEET.name: REPEATED_SHEET.read_bytes(),
                REPEATED_CHANNEL.name: repeated_channel.encode("utf-8"),
            },
            root_path=REPEATED_SHEET.name,
            project_directory=".",
            project_name=REPEATED_SHEET.stem,
            kicad_version=SUPPORTED_KICAD_VERSION,
            unconnected_pins=frozenset({"R1.2", "R2.2"}),
        )

        self.assertEqual(fault.status, "COMPLETE")
        self.assertEqual(len(fault.unmarked_t_junctions), 2)
        self.assertEqual(
            {item.sheet_instance_path for item in fault.unmarked_t_junctions},
            {
                "/d0000000-0000-4000-8000-000000000001/d0000000-0000-4000-8000-000000000002",
                "/d0000000-0000-4000-8000-000000000001/d0000000-0000-4000-8000-000000000003",
            },
        )
        self.assertEqual(len(fault.source_bindings), 3)
        self.assertEqual(len(fault.source_tree_sha256 or ""), 64)
        self.assertEqual(len(fault.coincident_text_anchors), 2)
        self.assertEqual(
            {item.sheet_instance_path for item in fault.coincident_text_anchors},
            {
                "/d0000000-0000-4000-8000-000000000001/d0000000-0000-4000-8000-000000000002",
                "/d0000000-0000-4000-8000-000000000001/d0000000-0000-4000-8000-000000000003",
            },
        )
        self.assertEqual(len(fault.free_text_overlaps), 2)
        self.assertEqual(
            {item.sheet_instance_path for item in fault.free_text_overlaps},
            {
                "/d0000000-0000-4000-8000-000000000001/d0000000-0000-4000-8000-000000000002",
                "/d0000000-0000-4000-8000-000000000001/d0000000-0000-4000-8000-000000000003",
            },
        )

        control = scan_schematic_geometry_tree(
            {
                REPEATED_SHEET_CONTROL.name: REPEATED_SHEET_CONTROL.read_bytes(),
                REPEATED_CHANNEL_CONTROL.name: REPEATED_CHANNEL_CONTROL.read_bytes(),
            },
            root_path=REPEATED_SHEET_CONTROL.name,
            project_directory=".",
            project_name=REPEATED_SHEET_CONTROL.stem,
            kicad_version=SUPPORTED_KICAD_VERSION,
            unconnected_pins=frozenset(),
        )
        self.assertEqual(control.status, "COMPLETE")
        self.assertEqual(control.unmarked_t_junctions, ())
        self.assertEqual(control.free_text_overlaps, ())
        self.assertNotEqual(fault.source_tree_sha256, control.source_tree_sha256)

    def test_reused_sheet_without_exact_instance_references_is_partial(self) -> None:
        child = REPEATED_CHANNEL.read_text(encoding="utf-8").replace(
            'project "repeated-sheet-root"', 'project "different-project"'
        )
        result = scan_schematic_geometry_tree(
            {
                REPEATED_SHEET.name: REPEATED_SHEET.read_bytes(),
                REPEATED_CHANNEL.name: child.encode("utf-8"),
            },
            root_path=REPEATED_SHEET.name,
            project_directory=".",
            project_name=REPEATED_SHEET.stem,
            kicad_version=SUPPORTED_KICAD_VERSION,
            unconnected_pins=frozenset({"R1.2", "R2.2"}),
        )

        self.assertEqual(result.status, "PARTIAL")
        self.assertEqual(len(result.unmarked_t_junctions), 2)
        self.assertEqual(len(result.source_bindings), 3)
        self.assertEqual(len(result.unsupported), 4)
        self.assertTrue(
            all(
                "no unique" in item.casefold() and "reference" in item.casefold()
                for item in result.unsupported
            )
        )
        self.assertEqual(len(result.unsupported_by_rule["schematic.pin_tip_on_wire_interior"]), 4)
        self.assertNotIn("schematic.free_text_overlap", result.unsupported_by_rule)

    def test_hierarchical_sheet_resolution_rejects_project_escape(self) -> None:
        with self.assertRaisesRegex(ValueError, "escapes its project directory"):
            resolve_schematic_sheet_path(
                "projects/controller/main.kicad_sch",
                "projects/controller",
                "../sibling/child.kicad_sch",
            )

    def test_rotated_and_mirrored_pin_line_transforms(self) -> None:
        # Pin-1 midpoint coordinates were checked against KiCad 10.0.6 native
        # netlist coordinates for each orthogonal orientation and mirror mode.
        semantic_finding: tuple[str, str, str, str, str, float, float, str] | None = None
        source_hashes: set[str] = set()
        for (angle, mirror), endpoint in TRANSFORM_MIDPOINTS.items():
            with self.subTest(angle=angle, mirror=mirror):
                source = transformed_fault(angle, mirror, endpoint)
                result = self.scan(source)
                self.assertEqual(result.status, "COMPLETE")
                self.assertEqual(len(result.findings), 1)
                finding = result.findings[0]
                self.assertEqual(finding.wire_endpoint_mm, endpoint)
                observed_semantics = (
                    finding.reference,
                    finding.symbol_library_id,
                    finding.pin_number,
                    finding.pin_name,
                    finding.wire_uuid,
                    finding.distance_to_pin_tip_mm,
                    finding.distance_along_pin_mm,
                    finding.sheet_instance_path,
                )
                if semantic_finding is None:
                    semantic_finding = observed_semantics
                self.assertEqual(observed_semantics, semantic_finding)
                self.assertEqual(result.source_sha256, hashlib.sha256(source).hexdigest())
                source_hashes.add(result.source_sha256)

                # Match the fixture helper's source spelling exactly; some
                # binary floats are emitted with their full Python repr.
                wire_end = (endpoint[0] + 25.4, endpoint[1])
                wire_points = (
                    f"(xy {endpoint[0]} {endpoint[1]}) (xy {wire_end[0]} {wire_end[1]})"
                ).encode()
                reverse_points = (
                    f"(xy {wire_end[0]} {wire_end[1]}) (xy {endpoint[0]} {endpoint[1]})"
                ).encode()
                self.assertEqual(source.count(wire_points), 1)
                reversed_source = source.replace(wire_points, reverse_points, 1)
                reversed_result = self.scan(reversed_source)
                self.assertEqual(reversed_result.status, "COMPLETE")
                self.assertEqual(len(reversed_result.findings), 1)
                reversed_finding = reversed_result.findings[0]
                self.assertEqual(
                    (
                        reversed_finding.reference,
                        reversed_finding.symbol_library_id,
                        reversed_finding.pin_number,
                        reversed_finding.pin_name,
                        reversed_finding.wire_uuid,
                        reversed_finding.distance_to_pin_tip_mm,
                        reversed_finding.distance_along_pin_mm,
                        reversed_finding.sheet_instance_path,
                    ),
                    observed_semantics,
                )
                self.assertEqual(reversed_finding.wire_endpoint_mm, endpoint)

                # Translating the whole wire slightly off the pin axis removes
                # the candidate without changing the unconnected-pin input.
                if finding.pin_tip_mm[0] == finding.pin_body_end_mm[0]:
                    delta_x, delta_y = 0.01, 0.0
                else:
                    delta_x, delta_y = 0.0, 0.01
                shifted_start = (round(endpoint[0] + delta_x, 6), round(endpoint[1] + delta_y, 6))
                shifted_end = (round(wire_end[0] + delta_x, 6), round(wire_end[1] + delta_y, 6))
                shifted_points = (
                    f"(xy {shifted_start[0]} {shifted_start[1]}) "
                    f"(xy {shifted_end[0]} {shifted_end[1]})"
                ).encode()
                shifted_source = source.replace(wire_points, shifted_points, 1)
                shifted_result = self.scan(shifted_source)
                self.assertEqual(shifted_result.status, "COMPLETE")
                self.assertEqual(shifted_result.findings, ())

        self.assertIsNotNone(semantic_finding)
        self.assertGreater(len(source_hashes), 1)


class NativeSchematicGeometryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cli_value = os.environ.get("KICAD_GEOMETRY_TEST_CLI")
        if not cli_value:
            raise unittest.SkipTest("set KICAD_GEOMETRY_TEST_CLI for native KiCad parity tests")
        expected_version = os.environ.get("KICAD_GEOMETRY_TEST_VERSION", SUPPORTED_KICAD_VERSION)
        if expected_version not in SUPPORTED_KICAD_VERSIONS:
            raise ValueError(f"unsupported native geometry test version: {expected_version}")
        cli = Path(cli_value).expanduser()
        if not cli.is_file():
            raise FileNotFoundError("KICAD_GEOMETRY_TEST_CLI does not point to a file")
        version = subprocess.run((str(cli), "version"), capture_output=True, text=True, check=False)
        if version.returncode != 0 or version.stdout.strip() != expected_version:
            raise AssertionError(
                f"native geometry test requires KiCad {expected_version}; "
                f"reported {version.stdout.strip()!r}"
            )
        cls.cli = cli
        cls.kicad_version = expected_version

    def native_scan(
        self,
        fixture: Path | bytes,
        *,
        source_name: str | None = None,
        related_sources: tuple[Path, ...] = (),
        scan_hierarchy: bool = False,
    ) -> tuple[object, dict[str, object], dict[str, object]]:
        with tempfile.TemporaryDirectory(prefix="schematic-geometry-native-") as directory:
            root = Path(directory)
            if isinstance(fixture, Path):
                source_path = root / fixture.name
                shutil.copyfile(fixture, source_path)
                for related_source in related_sources:
                    shutil.copyfile(related_source, root / related_source.name)
            else:
                source_path = root / (source_name or "synthetic.kicad_sch")
                source_path.write_bytes(fixture)
                if related_sources:
                    raise ValueError("Related schematic files require a path-backed root fixture")
            netlist_path = root / "netlist.xml"
            erc_path = root / "erc.json"
            commands = (
                (
                    str(self.cli),
                    "sch",
                    "export",
                    "netlist",
                    "--format",
                    "kicadxml",
                    "--output",
                    str(netlist_path),
                    str(source_path),
                ),
                (
                    str(self.cli),
                    "sch",
                    "erc",
                    "--format",
                    "json",
                    "--output",
                    str(erc_path),
                    str(source_path),
                ),
            )
            for command in commands:
                result = subprocess.run(command, capture_output=True, text=True, check=False)
                self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

            netlist_root = ET.parse(netlist_path).getroot()
            unconnected = frozenset(
                f"{node.attrib['ref']}.{node.attrib['pin']}"
                for net in netlist_root.findall("./nets/net")
                if net.attrib.get("name", "").startswith("unconnected-")
                for node in net.findall("node")
            )
            erc = json.loads(erc_path.read_text(encoding="utf-8"))
            source = source_path.read_bytes()
            if scan_hierarchy:
                source_files = {source_path.name: source}
                source_files.update(
                    {related.name: related.read_bytes() for related in related_sources}
                )
                scan = scan_schematic_geometry_tree(
                    source_files,
                    root_path=source_path.name,
                    project_directory=".",
                    project_name=source_path.stem,
                    kicad_version=self.kicad_version,
                    unconnected_pins=unconnected,
                )
            else:
                scan = scan_wire_ends_on_pin_lines(
                    source,
                    source_path=source_path.name,
                    kicad_version=self.kicad_version,
                    unconnected_pins=unconnected,
                )
            return scan, netlist_root, erc

    def native_svg(self, fixture: bytes, *, source_name: str) -> ET.Element:
        with tempfile.TemporaryDirectory(prefix="schematic-text-svg-") as directory:
            root = Path(directory)
            source_path = root / source_name
            source_path.write_bytes(fixture)
            output = root / "svg"
            result = subprocess.run(
                (
                    str(self.cli),
                    "sch",
                    "export",
                    "svg",
                    str(source_path),
                    "--output",
                    str(output),
                ),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
            svg_path = output / f"{source_path.stem}.svg"
            return ET.parse(svg_path).getroot()

    def test_coincident_text_anchor_fixture_adds_no_native_erc_diagnostic(self) -> None:
        separated, _separated_netlist, separated_erc = self.native_scan(
            free_text_anchor_fixture((25.4, 25.4), (50.8, 25.4))
        )
        coincident, _coincident_netlist, coincident_erc = self.native_scan(
            free_text_anchor_fixture((25.4, 25.4), (25.4, 25.4))
        )
        self.assertEqual(separated.coincident_text_anchors, ())
        self.assertEqual(len(coincident.coincident_text_anchors), 1)

        def violations(report: dict[str, object]) -> list[dict[str, object]]:
            return [
                item for sheet in report.get("sheets", []) for item in sheet.get("violations", [])
            ]

        self.assertEqual(violations(coincident_erc), violations(separated_erc))

    def test_free_text_overlap_matches_native_svg_and_erc_control(self) -> None:
        fault_text = "10µF ±5V"
        second_text = "4.7Ω"
        fault_source = free_text_objects_fixture(
            fault_text, (25.4, 25.4), second_text, (29.0, 25.4)
        )
        control_source = free_text_objects_fixture(
            fault_text, (25.4, 25.4), second_text, (50.8, 25.4)
        )
        fault, fault_netlist, fault_erc = self.native_scan(
            fault_source, source_name="text-overlap.kicad_sch", scan_hierarchy=False
        )
        control, control_netlist, control_erc = self.native_scan(
            control_source, source_name="text-overlap.kicad_sch", scan_hierarchy=False
        )
        self.assertEqual(fault.status, "COMPLETE")
        self.assertEqual(len(fault.free_text_overlaps), 1)
        self.assertEqual(control.free_text_overlaps, ())
        self.assertEqual(
            _netlist_components_without_sheetfile(fault_netlist),
            _netlist_components_without_sheetfile(control_netlist),
        )
        fault_nets = fault_netlist.find("./nets")
        control_nets = control_netlist.find("./nets")
        self.assertIsNotNone(fault_nets)
        self.assertIsNotNone(control_nets)
        self.assertEqual(ET.tostring(fault_nets), ET.tostring(control_nets))

        def violation_signatures(report: dict[str, object]) -> tuple[tuple[object, ...], ...]:
            violations = [
                violation
                for sheet in report.get("sheets", [])
                for violation in sheet.get("violations", [])
            ]
            return tuple(
                sorted(
                    (
                        violation["type"],
                        violation["severity"],
                        tuple(item.get("uuid") for item in violation["items"]),
                    )
                    for violation in violations
                )
            )

        self.assertEqual(violation_signatures(fault_erc), violation_signatures(control_erc))
        fault_svg = self.native_svg(fault_source, source_name="fault-text-overlap.kicad_sch")
        control_svg = self.native_svg(control_source, source_name="control-text-overlap.kicad_sch")
        fault_alpha = _native_svg_text_strokes(fault_svg, fault_text)
        fault_beta = _native_svg_text_strokes(fault_svg, second_text)
        control_alpha = _native_svg_text_strokes(control_svg, fault_text)
        control_beta = _native_svg_text_strokes(control_svg, second_text)
        fault_gap = min(
            _segment_distance(*first, *second) for first in fault_alpha for second in fault_beta
        )
        control_gap = min(
            _segment_distance(*first, *second) for first in control_alpha for second in control_beta
        )
        self.assertLessEqual(fault_gap, 0.1524)
        self.assertGreater(control_gap, 0.1524)

        metrics_path = (
            Path(__file__).parents[1] / "kicad_tooling/hwrepo/schematic-text-metrics.json"
        )
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        for svg_root, expected_text in (
            (fault_svg, fault_text),
            (fault_svg, second_text),
        ):
            text_nodes = [
                node
                for node in svg_root.iter()
                if node.tag.endswith("}text") and node.text == expected_text
            ]
            self.assertEqual(len(text_nodes), 1)
            expected_width = sum(metrics["advances_mm"][char] for char in expected_text)
            expected_width += metrics["line_end_spacing_mm"]
            self.assertAlmostEqual(
                float(text_nodes[0].attrib["textLength"]), expected_width, delta=0.01
            )

    def test_horizontal_justification_matches_native_svg_and_erc_control(self) -> None:
        for justification, second_x in (("left", 54.0), ("right", 46.0)):
            with self.subTest(justification=justification):
                fault_source = justify_first_free_text(
                    free_text_objects_fixture("FIRST", (50.0, 50.0), "SECOND", (second_x, 50.0)),
                    justification,
                )
                control_source = justify_first_free_text(
                    free_text_objects_fixture("FIRST", (50.0, 50.0), "SECOND", (90.0, 50.0)),
                    justification,
                )
                fault, fault_netlist, fault_erc = self.native_scan(
                    fault_source,
                    source_name="justified-text-fault.kicad_sch",
                    scan_hierarchy=False,
                )
                control, control_netlist, control_erc = self.native_scan(
                    control_source,
                    source_name="justified-text-control.kicad_sch",
                    scan_hierarchy=False,
                )

                self.assertEqual(fault.status, "COMPLETE")
                self.assertEqual(len(fault.free_text_overlaps), 1)
                self.assertEqual(control.status, "COMPLETE")
                self.assertEqual(control.free_text_overlaps, ())
                self.assertEqual(
                    _netlist_components_without_sheetfile(fault_netlist),
                    _netlist_components_without_sheetfile(control_netlist),
                )
                self.assertEqual(
                    ET.tostring(fault_netlist.find("./nets")),
                    ET.tostring(control_netlist.find("./nets")),
                )

                def erc_signatures(report: dict[str, object]) -> tuple[tuple[object, ...], ...]:
                    violations = [
                        item
                        for sheet in report.get("sheets", [])
                        for item in sheet.get("violations", [])
                    ]
                    return tuple(
                        sorted(
                            (
                                item["type"],
                                item["severity"],
                                tuple(entry.get("uuid") for entry in item["items"]),
                            )
                            for item in violations
                        )
                    )

                self.assertEqual(erc_signatures(fault_erc), erc_signatures(control_erc))
                first_box = fault.free_text_overlaps[0].first_box_mm
                svg_root = self.native_svg(
                    fault_source, source_name="justified-text-fault.kicad_sch"
                )
                strokes = _native_svg_text_strokes(svg_root, "FIRST")
                stroke_x = tuple(point[0] for segment in strokes for point in segment)
                self.assertGreaterEqual(min(stroke_x), first_box[0] - 0.01)
                self.assertLessEqual(max(stroke_x), first_box[2] + 0.01)

    def test_empty_justification_matches_native_default_centering(self) -> None:
        default_source = free_text_objects_fixture("FIRST", (50.0, 50.0), "SECOND", (54.0, 50.0))
        empty_source = justify_first_free_text(default_source, "")
        default, default_netlist, default_erc = self.native_scan(
            default_source,
            source_name="empty-justify.kicad_sch",
            scan_hierarchy=False,
        )
        empty, empty_netlist, empty_erc = self.native_scan(
            empty_source,
            source_name="empty-justify.kicad_sch",
            scan_hierarchy=False,
        )

        self.assertEqual(default.status, "COMPLETE")
        self.assertEqual(empty.status, "COMPLETE")
        self.assertEqual(default.unsupported_by_rule, {})
        self.assertEqual(empty.unsupported_by_rule, {})
        self.assertEqual(default.free_text_overlaps, empty.free_text_overlaps)
        self.assertEqual(
            ET.tostring(default_netlist.find("./nets")),
            ET.tostring(empty_netlist.find("./nets")),
        )

        def erc_signatures(report: dict[str, object]) -> tuple[tuple[object, ...], ...]:
            return tuple(
                sorted(
                    (
                        item["type"],
                        item["severity"],
                        tuple(entry.get("uuid") for entry in item["items"]),
                    )
                    for sheet in report.get("sheets", [])
                    for item in sheet.get("violations", [])
                )
            )

        self.assertEqual(erc_signatures(default_erc), erc_signatures(empty_erc))
        default_svg = self.native_svg(default_source, source_name="empty-justify.kicad_sch")
        empty_svg = self.native_svg(empty_source, source_name="empty-justify.kicad_sch")

        def first_text_svg_geometry(
            svg_root: ET.Element,
        ) -> tuple[dict[str, str], tuple[tuple[tuple[float, float], tuple[float, float]], ...]]:
            text_nodes = [
                node
                for node in svg_root.iter()
                if node.tag.endswith("}text") and node.text == "FIRST"
            ]
            self.assertEqual(len(text_nodes), 1)
            return text_nodes[0].attrib, _native_svg_text_strokes(svg_root, "FIRST")

        self.assertEqual(first_text_svg_geometry(default_svg), first_text_svg_geometry(empty_svg))

    def test_unsupported_free_text_variants_preserve_native_connectivity(self) -> None:
        text_anchor = (25.4, 25.4)
        base = free_text_objects_fixture("FIRST", text_anchor, "SECOND", (29.0, 25.4))
        baseline, baseline_netlist, baseline_erc = self.native_scan(
            base, source_name="text-variant.kicad_sch", scan_hierarchy=False
        )
        self.assertEqual(baseline.status, "COMPLETE")
        self.assertEqual(len(baseline.free_text_overlaps), 1)

        def replace_first_text(source: bytes, old: bytes, new: bytes) -> bytes:
            start = source.index(b'(text "FIRST"')
            end_marker = b'(uuid "d0000000-0000-4000-8000-000000000001"))'
            end = source.index(end_marker, start) + len(end_marker)
            text_node = source[start:end]
            if text_node.count(old) != 1:
                raise AssertionError("expected a unique text-node style to replace")
            return source[:start] + text_node.replace(old, new, 1) + source[end:]

        variants = (
            replace_first_text(
                base,
                b"(font (size 1.27 1.27))",
                b'(font (face "Synthetic Custom Font") (size 1.27 1.27))',
            ),
            replace_first_text(
                base,
                b"(font (size 1.27 1.27))",
                b"(font (bold yes) (size 1.27 1.27))",
            ),
            replace_first_text(
                base,
                b"(font (size 1.27 1.27))",
                b"(font (italic yes) (size 1.27 1.27))",
            ),
            replace_first_text(
                base,
                b"(font (size 1.27 1.27))",
                b"(font (size 1.27 1.27) (thickness 0.2))",
            ),
            replace_first_text(
                base,
                b"(effects (font (size 1.27 1.27)))",
                b"(effects (font (size 1.27 1.27)) (justify top))",
            ),
            replace_first_text(
                base,
                b"(at 25.4 25.4 0)",
                b"(at 25.4 25.4 45)",
            ),
            free_text_objects_fixture("F~{IR}ST", text_anchor, "SECOND", (29.0, 25.4)),
            free_text_objects_fixture("FÜRST", text_anchor, "SECOND", (29.0, 25.4)),
        )

        def netlist_connectivity(root: ET.Element) -> tuple[object, ...]:
            components = tuple(
                sorted(
                    (
                        component.get("ref", ""),
                        component.findtext("value", ""),
                        component.findtext("footprint", ""),
                        (
                            component.find("libsource").get("lib", "")
                            if component.find("libsource") is not None
                            else ""
                        ),
                        (
                            component.find("libsource").get("part", "")
                            if component.find("libsource") is not None
                            else ""
                        ),
                    )
                    for component in root.findall("./components/comp")
                )
            )
            assignments = tuple(
                sorted(
                    (
                        net.get("name", ""),
                        node.get("ref", ""),
                        node.get("pin", ""),
                    )
                    for net in root.findall("./nets/net")
                    for node in net.findall("node")
                )
            )
            return components, assignments

        def erc_signatures(report: dict[str, object]) -> tuple[tuple[object, ...], ...]:
            violations = [
                item for sheet in report.get("sheets", []) for item in sheet.get("violations", [])
            ]
            return tuple(
                sorted(
                    (
                        item["type"],
                        item["severity"],
                        tuple(entry.get("uuid") for entry in item["items"]),
                    )
                    for item in violations
                )
            )

        for index, source in enumerate(variants):
            with self.subTest(variant=index):
                result, netlist, erc = self.native_scan(
                    source, source_name="text-variant.kicad_sch", scan_hierarchy=False
                )
                self.assertEqual(result.status, "PARTIAL")
                self.assertEqual(result.free_text_overlaps, ())
                self.assertEqual(
                    netlist_connectivity(netlist), netlist_connectivity(baseline_netlist)
                )
                self.assertEqual(erc_signatures(erc), erc_signatures(baseline_erc))

    def test_free_text_over_wire_matches_native_svg_and_erc_control(self) -> None:
        fault_source = free_text_wire_fixture("WIRE CROSSING FAULT", (88.9, 71.12))
        control_source = free_text_wire_fixture("WIRE CLEAR CONTROL", (88.9, 80.01))
        fault, fault_netlist, fault_erc = self.native_scan(
            fault_source,
            source_name="free-text-wire.kicad_sch",
            scan_hierarchy=False,
        )
        control, control_netlist, control_erc = self.native_scan(
            control_source,
            source_name="free-text-wire.kicad_sch",
            scan_hierarchy=False,
        )
        self.assertEqual(fault.status, "COMPLETE")
        self.assertEqual(len(fault.free_text_wire_overlaps), 1)
        self.assertEqual(control.free_text_wire_overlaps, ())
        self.assertEqual(
            _netlist_components_without_sheetfile(fault_netlist),
            _netlist_components_without_sheetfile(control_netlist),
        )
        fault_nets = fault_netlist.find("./nets")
        control_nets = control_netlist.find("./nets")
        self.assertIsNotNone(fault_nets)
        self.assertIsNotNone(control_nets)
        self.assertEqual(ET.tostring(fault_nets), ET.tostring(control_nets))

        def violation_signatures(report: dict[str, object]) -> tuple[tuple[object, ...], ...]:
            violations = [
                violation
                for sheet in report.get("sheets", [])
                for violation in sheet.get("violations", [])
            ]
            return tuple(
                sorted(
                    (
                        violation["type"],
                        violation["severity"],
                        tuple(item.get("uuid") for item in violation["items"]),
                    )
                    for violation in violations
                )
            )

        self.assertEqual(violation_signatures(fault_erc), violation_signatures(control_erc))
        fault_svg = self.native_svg(fault_source, source_name="free-text-wire-fault.kicad_sch")
        control_svg = self.native_svg(
            control_source, source_name="free-text-wire-control.kicad_sch"
        )
        fault_text = _native_svg_text_strokes(fault_svg, "WIRE CROSSING FAULT")
        control_text = _native_svg_text_strokes(control_svg, "WIRE CLEAR CONTROL")
        fault_wire = _native_svg_matching_line(fault_svg, (76.2, 71.12), (101.6, 71.12))
        control_wire = _native_svg_matching_line(control_svg, (76.2, 71.12), (101.6, 71.12))
        fault_gap = min(_segment_distance(*segment, *fault_wire) for segment in fault_text)
        control_gap = min(_segment_distance(*segment, *control_wire) for segment in control_text)
        self.assertAlmostEqual(fault_gap, 0.0, delta=1e-6)
        self.assertGreater(control_gap, 7.9)

    def test_multiline_text_spacing_and_wire_geometry_match_native_svg(self) -> None:
        fault_text = "TOP\nWIRE CROSSING FAULT\nBOTTOM"
        control_text = "TOP\nWIRE CLEAR CONTROL\nBOTTOM"
        fault_source = free_text_wire_fixture(fault_text, (88.9, 71.12))
        control_source = free_text_wire_fixture(control_text, (88.9, 80.01))
        fault, fault_netlist, fault_erc = self.native_scan(
            fault_source, source_name="multiline-text-wire.kicad_sch", scan_hierarchy=False
        )
        control, control_netlist, control_erc = self.native_scan(
            control_source, source_name="multiline-text-wire.kicad_sch", scan_hierarchy=False
        )

        self.assertEqual(fault.status, "COMPLETE")
        self.assertEqual(len(fault.free_text_wire_overlaps), 1)
        self.assertEqual(control.status, "COMPLETE")
        self.assertEqual(control.free_text_wire_overlaps, ())
        self.assertEqual(
            _netlist_components_without_sheetfile(fault_netlist),
            _netlist_components_without_sheetfile(control_netlist),
        )
        fault_nets = fault_netlist.find("./nets")
        control_nets = control_netlist.find("./nets")
        self.assertIsNotNone(fault_nets)
        self.assertIsNotNone(control_nets)
        self.assertEqual(ET.tostring(fault_nets), ET.tostring(control_nets))

        def violation_signatures(report: dict[str, object]) -> tuple[tuple[object, ...], ...]:
            violations = [
                violation
                for sheet in report.get("sheets", [])
                for violation in sheet.get("violations", [])
            ]
            return tuple(
                sorted(
                    (
                        violation["type"],
                        violation["severity"],
                        tuple(item.get("uuid") for item in violation["items"]),
                    )
                    for violation in violations
                )
            )

        self.assertEqual(violation_signatures(fault_erc), violation_signatures(control_erc))
        fault_svg = self.native_svg(fault_source, source_name="multiline-text-fault.kicad_sch")
        control_svg = self.native_svg(
            control_source, source_name="multiline-text-control.kicad_sch"
        )
        fault_strokes = tuple(
            segment
            for line in fault_text.split("\n")
            for segment in _native_svg_text_strokes(fault_svg, line)
        )
        control_strokes = tuple(
            segment
            for line in control_text.split("\n")
            for segment in _native_svg_text_strokes(control_svg, line)
        )
        fault_wire = _native_svg_matching_line(fault_svg, (76.2, 71.12), (101.6, 71.12))
        control_wire = _native_svg_matching_line(control_svg, (76.2, 71.12), (101.6, 71.12))
        fault_gap = min(_segment_distance(*segment, *fault_wire) for segment in fault_strokes)
        control_gap = min(_segment_distance(*segment, *control_wire) for segment in control_strokes)
        self.assertAlmostEqual(fault_gap, 0.0, delta=1e-6)
        self.assertGreater(control_gap, 5.0)

        text_nodes = [
            node
            for node in fault_svg.iter()
            if node.tag.endswith("}text") and node.text in {"TOP", "WIRE CROSSING FAULT", "BOTTOM"}
        ]
        self.assertEqual(len(text_nodes), 3)
        baselines = sorted(float(node.attrib["y"]) for node in text_nodes)
        metrics_path = (
            Path(__file__).parents[1] / "kicad_tooling/hwrepo/schematic-text-metrics.json"
        )
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        measured_spacing = metrics["multiline_line_spacing_mm"]
        self.assertAlmostEqual(baselines[1] - baselines[0], measured_spacing, delta=0.0001)
        self.assertAlmostEqual(baselines[2] - baselines[1], measured_spacing, delta=0.0001)

        finding = next(
            item
            for item in fault.free_text_wire_overlaps
            if item.text_uuid == "f0000000-0000-4000-8000-000000000001"
        )
        x_values = [coordinate[0] for segment in fault_strokes for coordinate in segment]
        y_values = [coordinate[1] for segment in fault_strokes for coordinate in segment]
        stroke_margin = metrics["stroke_width_mm"] / 2.0
        self.assertLessEqual(finding.text_box_mm[0], min(x_values) - stroke_margin)
        self.assertGreaterEqual(finding.text_box_mm[2], max(x_values) + stroke_margin)
        self.assertLessEqual(finding.text_box_mm[1], min(y_values) - stroke_margin)
        self.assertGreaterEqual(finding.text_box_mm[3], max(y_values) + stroke_margin)

    def test_symbol_body_wire_matches_native_svg_and_erc_control(self) -> None:
        fault_source = symbol_body_wire_fixture()
        control_source = symbol_body_wire_fixture(((71.12, 82.55), (81.28, 82.55)))
        fault, fault_netlist, fault_erc = self.native_scan(
            fault_source,
            source_name="symbol-body-wire.kicad_sch",
            scan_hierarchy=False,
        )
        control, control_netlist, control_erc = self.native_scan(
            control_source,
            source_name="symbol-body-wire.kicad_sch",
            scan_hierarchy=False,
        )
        self.assertEqual(fault.status, "COMPLETE")
        self.assertEqual(len(fault.wires_through_symbol_bodies), 1)
        self.assertEqual(control.wires_through_symbol_bodies, ())
        self.assertEqual(
            _netlist_components_without_sheetfile(fault_netlist),
            _netlist_components_without_sheetfile(control_netlist),
        )
        fault_nets = fault_netlist.find("./nets")
        control_nets = control_netlist.find("./nets")
        self.assertIsNotNone(fault_nets)
        self.assertIsNotNone(control_nets)
        self.assertEqual(ET.tostring(fault_nets), ET.tostring(control_nets))

        def violation_signatures(report: dict[str, object]) -> tuple[tuple[object, ...], ...]:
            violations = [
                violation
                for sheet in report.get("sheets", [])
                for violation in sheet.get("violations", [])
            ]
            return tuple(
                sorted(
                    (
                        violation["type"],
                        violation["severity"],
                        tuple(item.get("uuid") for item in violation["items"]),
                    )
                    for violation in violations
                )
            )

        fault_signatures = violation_signatures(fault_erc)
        control_signatures = violation_signatures(control_erc)
        self.assertEqual(len(fault_signatures), 6)
        self.assertEqual(fault_signatures, control_signatures)
        fault_svg = self.native_svg(fault_source, source_name="symbol-body-wire-fault.kicad_sch")
        control_svg = self.native_svg(
            control_source, source_name="symbol-body-wire-control.kicad_sch"
        )
        body_rect = _native_svg_matching_rect(fault_svg, 74.93, 73.66, 2.54, 5.08)
        fault_wire = _native_svg_matching_line(fault_svg, (71.12, 76.2), (81.28, 76.2))
        _native_svg_matching_line(control_svg, (71.12, 82.55), (81.28, 82.55))
        self.assertLess(body_rect[1], fault_wire[0][1])
        self.assertGreater(body_rect[1] + body_rect[3], fault_wire[0][1])
        self.assertGreater(max(point[0] for point in fault_wire), body_rect[0])
        self.assertLess(min(point[0] for point in fault_wire), body_rect[0] + body_rect[2])

    def test_valid_peer_connector_contacts_inside_symbol_body_remain_review_candidates(
        self,
    ) -> None:
        enclosed_source = enclosed_connector_body_wire_fixture(body_offset_x=0.0)
        clear_source = enclosed_connector_body_wire_fixture(body_offset_x=2.54)
        enclosed, enclosed_netlist, enclosed_erc = self.native_scan(
            enclosed_source,
            source_name="synthetic-enclosed-connector.kicad_sch",
        )
        clear, clear_netlist, clear_erc = self.native_scan(
            clear_source,
            source_name="synthetic-enclosed-connector.kicad_sch",
        )

        self.assertEqual(enclosed.status, "COMPLETE")
        self.assertEqual(
            {
                (finding.reference, finding.symbol_library_id)
                for finding in enclosed.wires_through_symbol_bodies
            },
            {
                ("J1", "Connector_Generic:Conn_01x01"),
                ("J2", "Connector_Generic:Conn_01x01"),
            },
        )
        self.assertEqual(clear.status, "COMPLETE")
        self.assertEqual(clear.wires_through_symbol_bodies, ())
        self.assertEqual(
            _netlist_components_without_sheetfile(enclosed_netlist),
            _netlist_components_without_sheetfile(clear_netlist),
        )
        enclosed_nets = enclosed_netlist.find("./nets")
        clear_nets = clear_netlist.find("./nets")
        self.assertIsNotNone(enclosed_nets)
        self.assertIsNotNone(clear_nets)
        self.assertEqual(ET.tostring(enclosed_nets), ET.tostring(clear_nets))
        signal_nodes = {
            node.attrib["ref"]
            for net in enclosed_netlist.findall("./nets/net")
            if net.attrib.get("name") == "/SIGNAL"
            for node in net.findall("./node")
            if node.attrib.get("ref") in {"J1", "J2"} and node.attrib.get("pin") == "1"
        }
        self.assertEqual(signal_nodes, {"J1", "J2"})

        def violation_signatures(report: dict[str, object]) -> tuple[tuple[object, ...], ...]:
            violations = [
                violation
                for sheet in report.get("sheets", [])
                for violation in sheet.get("violations", [])
            ]
            return tuple(
                sorted(
                    (
                        violation["type"],
                        violation["severity"],
                        tuple(item.get("uuid") for item in violation["items"]),
                    )
                    for violation in violations
                )
            )

        enclosed_erc_signatures = violation_signatures(enclosed_erc)
        clear_erc_signatures = violation_signatures(clear_erc)
        self.assertEqual(enclosed_erc_signatures, clear_erc_signatures)
        self.assertEqual(
            {signature[0] for signature in enclosed_erc_signatures},
            {"lib_symbol_issues"},
            "standalone native scans lack a project sym-lib-table; no electrical ERC warning is expected",
        )

        enclosed_svg = self.native_svg(
            enclosed_source, source_name="synthetic-enclosed-connector.kicad_sch"
        )
        clear_svg = self.native_svg(
            clear_source, source_name="synthetic-enclosed-connector.kicad_sch"
        )
        enclosed_body = _native_svg_matching_rect(enclosed_svg, 71.12, 71.12, 10.16, 10.16)
        enclosed_second_body = _native_svg_matching_rect(enclosed_svg, 115.57, 71.12, 10.16, 10.16)
        clear_body = _native_svg_matching_rect(clear_svg, 73.66, 71.12, 10.16, 10.16)
        clear_second_body = _native_svg_matching_rect(clear_svg, 118.11, 71.12, 10.16, 10.16)
        enclosed_wire = _native_svg_matching_line(enclosed_svg, (63.5, 76.2), (73.66, 76.2))
        enclosed_second_wire = _native_svg_matching_line(
            enclosed_svg, (109.22, 76.2), (118.11, 76.2)
        )
        clear_wire = _native_svg_matching_line(clear_svg, (63.5, 76.2), (73.66, 76.2))
        clear_second_wire = _native_svg_matching_line(clear_svg, (109.22, 76.2), (118.11, 76.2))
        self.assertLess(enclosed_body[0], max(point[0] for point in enclosed_wire))
        self.assertGreater(
            enclosed_body[0] + enclosed_body[2], min(point[0] for point in enclosed_wire)
        )
        self.assertLess(enclosed_second_body[0], max(point[0] for point in enclosed_second_wire))
        self.assertGreater(
            enclosed_second_body[0] + enclosed_second_body[2],
            min(point[0] for point in enclosed_second_wire),
        )
        self.assertEqual((enclosed_body[2], enclosed_body[3]), (clear_body[2], clear_body[3]))
        self.assertEqual(
            (enclosed_second_body[2], enclosed_second_body[3]),
            (clear_second_body[2], clear_second_body[3]),
        )
        self.assertAlmostEqual(clear_body[0], max(point[0] for point in clear_wire))
        self.assertAlmostEqual(clear_second_body[0], max(point[0] for point in clear_second_wire))

    def test_unsupported_formatted_text_does_not_reduce_native_wire_body_coverage(self) -> None:
        fault_source = symbol_body_wire_fixture()
        source_with_text = fault_source.replace(
            b"  (sheet_instances",
            b'  (text "UNSUPPORTED~{LINE}" (at 25.4 25.4 0) '
            b"(effects (font (size 1.27 1.27))) "
            b'(uuid "f1000000-0000-4000-8000-000000000009"))\n'
            b"  (sheet_instances",
            1,
        )
        with_text, with_text_netlist, with_text_erc = self.native_scan(
            source_with_text,
            source_name="symbol-body-wire-multiline.kicad_sch",
            scan_hierarchy=False,
        )
        _, baseline_netlist, baseline_erc = self.native_scan(
            fault_source,
            source_name="symbol-body-wire-multiline.kicad_sch",
            scan_hierarchy=False,
        )

        self.assertEqual(with_text.status, "PARTIAL")
        self.assertEqual(len(with_text.wires_through_symbol_bodies), 1)
        self.assertNotIn("schematic.wire_through_symbol_body", with_text.unsupported_by_rule)
        self.assertIn("schematic.free_text_overlap", with_text.unsupported_by_rule)
        self.assertEqual(
            ET.tostring(with_text_netlist.find("./nets")),
            ET.tostring(baseline_netlist.find("./nets")),
        )

        def erc_signatures(report: dict[str, object]) -> tuple[tuple[object, ...], ...]:
            violations = [
                violation
                for sheet in report.get("sheets", [])
                for violation in sheet.get("violations", [])
            ]
            return tuple(
                sorted(
                    (
                        violation["type"],
                        violation["severity"],
                        tuple(item.get("uuid") for item in violation["items"]),
                    )
                    for violation in violations
                )
            )

        self.assertEqual(erc_signatures(with_text_erc), erc_signatures(baseline_erc))

    def test_free_text_symbol_body_overlap_matches_native_svg_and_erc_control(self) -> None:
        fault_source = free_text_symbol_body_fixture()
        control_source = free_text_symbol_body_fixture(point=(88.9, 76.2))
        fault, fault_netlist, fault_erc = self.native_scan(
            fault_source,
            source_name="text-symbol-body.kicad_sch",
            scan_hierarchy=False,
        )
        control, control_netlist, control_erc = self.native_scan(
            control_source,
            source_name="text-symbol-body.kicad_sch",
            scan_hierarchy=False,
        )
        self.assertEqual(fault.status, "COMPLETE")
        self.assertEqual(len(fault.free_text_symbol_body_overlaps), 1)
        self.assertEqual(control.free_text_symbol_body_overlaps, ())
        self.assertEqual(
            _netlist_components_without_sheetfile(fault_netlist),
            _netlist_components_without_sheetfile(control_netlist),
        )
        fault_nets = fault_netlist.find("./nets")
        control_nets = control_netlist.find("./nets")
        self.assertIsNotNone(fault_nets)
        self.assertIsNotNone(control_nets)
        self.assertEqual(ET.tostring(fault_nets), ET.tostring(control_nets))

        def violation_signatures(report: dict[str, object]) -> tuple[tuple[object, ...], ...]:
            violations = [
                violation
                for sheet in report.get("sheets", [])
                for violation in sheet.get("violations", [])
            ]
            return tuple(
                sorted(
                    (
                        violation["type"],
                        violation["severity"],
                        tuple(item.get("uuid") for item in violation["items"]),
                    )
                    for violation in violations
                )
            )

        fault_signatures = violation_signatures(fault_erc)
        control_signatures = violation_signatures(control_erc)
        self.assertEqual(len(fault_signatures), 3)
        self.assertEqual(fault_signatures, control_signatures)

        fault_svg = self.native_svg(fault_source, source_name="text-symbol-body-fault.kicad_sch")
        control_svg = self.native_svg(
            control_source, source_name="text-symbol-body-control.kicad_sch"
        )
        body = _native_svg_matching_rect(fault_svg, 74.93, 73.66, 2.54, 5.08)
        body_box = (body[0], body[1], body[0] + body[2], body[1] + body[3])
        fault_strokes = _native_svg_text_strokes(fault_svg, "BODY NOTE")
        control_strokes = _native_svg_text_strokes(control_svg, "BODY NOTE")
        fault_points = [point for segment in fault_strokes for point in segment]
        control_points = [point for segment in control_strokes for point in segment]

        def stroke_bounds(
            points: list[tuple[float, float]],
        ) -> tuple[float, float, float, float]:
            return (
                min(point[0] for point in points),
                min(point[1] for point in points),
                max(point[0] for point in points),
                max(point[1] for point in points),
            )

        fault_bounds = stroke_bounds(fault_points)
        control_bounds = stroke_bounds(control_points)
        self.assertLess(fault_bounds[0], body_box[2])
        self.assertGreater(fault_bounds[2], body_box[0])
        self.assertLess(fault_bounds[1], body_box[3])
        self.assertGreater(fault_bounds[3], body_box[1])
        self.assertGreater(control_bounds[0], body_box[2])
        guarded_body = (
            body_box[0] + 0.15,
            body_box[1] + 0.15,
            body_box[2] - 0.15,
            body_box[3] - 0.15,
        )

        def any_stroke_midpoint_inside(
            strokes: tuple[tuple[tuple[float, float], tuple[float, float]], ...],
        ) -> bool:
            return any(
                guarded_body[0] < (start[0] + end[0]) / 2.0 < guarded_body[2]
                and guarded_body[1] < (start[1] + end[1]) / 2.0 < guarded_body[3]
                for start, end in strokes
            )

        self.assertTrue(any_stroke_midpoint_inside(fault_strokes))
        self.assertFalse(any_stroke_midpoint_inside(control_strokes))

    def test_schematic_text_metrics_match_native_svg_for_calibrated_glyphs(self) -> None:
        svg_root = self.native_svg(
            calibrated_stroke_text_metrics_fixture(), source_name="text-metrics.kicad_sch"
        )
        metrics_path = (
            Path(__file__).parents[1] / "kicad_tooling/hwrepo/schematic-text-metrics.json"
        )
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        rendered: dict[str, float] = {}
        for node in svg_root.iter():
            if (
                node.tag.endswith("}text")
                and node.attrib.get("x") == "30.0000"
                and node.attrib.get("y") == "30.3850"
            ):
                character = node.text or ""
                if character in metrics["advances_mm"]:
                    rendered[character] = float(node.attrib["textLength"])
        self.assertEqual(set(rendered), set(metrics["advances_mm"]))
        for character, advance in metrics["advances_mm"].items():
            measured_width = advance + metrics["single_glyph_svg_end_spacing_mm"]
            self.assertAlmostEqual(rendered[character], measured_width, delta=0.0001)

        top_ratio, bottom_ratio = metrics["vertical_ink_envelope_ratio"]
        expected_ink_envelope = (
            30.0 + top_ratio * metrics["reference_size_mm"] - metrics["stroke_width_mm"] / 2.0,
            30.0 + bottom_ratio * metrics["reference_size_mm"] + metrics["stroke_width_mm"] / 2.0,
        )
        for character in "—µΩ°±×":
            with self.subTest(character=character):
                strokes = _native_svg_text_strokes(svg_root, character)
                points = tuple(point for segment in strokes for point in segment)
                self.assertTrue(points)
                self.assertGreaterEqual(min(point[1] for point in points), expected_ink_envelope[0])
                self.assertLessEqual(max(point[1] for point in points), expected_ink_envelope[1])

    def test_near_pin_endpoint_transforms_match_native_netlist_and_erc(self) -> None:
        for transform, expected_endpoint in TRANSFORM_NEAR_PIN_ENDPOINTS.items():
            with self.subTest(transform=transform):
                source = transformed_near_pin_tip_wire(*transform)
                scan, netlist, erc = self.native_scan(
                    source,
                    source_name="transformed-near-pin-tip.kicad_sch",
                )
                self.assertEqual(scan.status, "COMPLETE")
                self.assertEqual(len(scan.wire_endpoints_near_pin_tips), 1)
                finding = scan.wire_endpoints_near_pin_tips[0]
                self.assertEqual(finding.pin_tip_mm, TRANSFORM_PIN_TIPS[transform])
                self.assertEqual(finding.wire_endpoint_mm, expected_endpoint)
                self.assertEqual(finding.distance_to_pin_tip_mm, MAX_PIN_ENDPOINT_GAP_MM)
                open_pins = {
                    f"{node.attrib['ref']}.{node.attrib['pin']}"
                    for net in netlist.findall("./nets/net")
                    if net.attrib.get("name", "").startswith("unconnected-")
                    for node in net.findall("node")
                }
                self.assertIn("R1.1", open_pins)
                violations = [
                    violation
                    for sheet in erc.get("sheets", [])
                    for violation in sheet.get("violations", [])
                ]
                self.assertTrue(
                    any(
                        item.get("type") == "pin_not_connected"
                        and any(
                            detail.get("uuid") == finding.pin_uuid
                            for detail in item.get("items", [])
                        )
                        for item in violations
                    )
                )
                self.assertTrue(
                    any(
                        item.get("type") == "unconnected_wire_endpoint"
                        and any(
                            detail.get("uuid") == finding.wire_uuid
                            for detail in item.get("items", [])
                        )
                        for item in violations
                    )
                )

    def test_near_miss_matches_native_netlist_and_erc_fault_and_control(self) -> None:
        fault, fault_netlist, fault_erc = self.native_scan(FAULT)
        self.assertEqual(len(fault.findings), 1)
        self.assertIn(
            "R1.1",
            {
                f"{node.attrib['ref']}.{node.attrib['pin']}"
                for net in fault_netlist.findall("./nets/net")
                if net.attrib.get("name", "").startswith("unconnected-")
                for node in net.findall("node")
            },
        )
        fault_violations = [
            violation
            for sheet in fault_erc.get("sheets", [])
            for violation in sheet.get("violations", [])
        ]
        finding = fault.findings[0]
        self.assertTrue(
            any(
                item.get("type") == "pin_not_connected"
                and any(detail.get("uuid") == finding.pin_uuid for detail in item.get("items", []))
                for item in fault_violations
            )
        )
        self.assertTrue(
            any(
                item.get("type") == "unconnected_wire_endpoint"
                and any(detail.get("uuid") == finding.wire_uuid for detail in item.get("items", []))
                for item in fault_violations
            )
        )

        control, control_netlist, control_erc = self.native_scan(CONTROL)
        self.assertFalse(control.findings)
        control_open_pins = {
            f"{node.attrib['ref']}.{node.attrib['pin']}"
            for net in control_netlist.findall("./nets/net")
            if net.attrib.get("name", "").startswith("unconnected-")
            for node in net.findall("node")
        }
        self.assertNotIn("R1.1", control_open_pins)
        control_violations = [
            violation
            for sheet in control_erc.get("sheets", [])
            for violation in sheet.get("violations", [])
        ]
        self.assertFalse(
            any(
                item.get("type") == "pin_not_connected"
                and any(
                    detail.get("uuid") == "b0000000-0000-4000-8000-000000000003"
                    for detail in item.get("items", [])
                )
                for item in control_violations
            )
        )

    def test_pin_on_wire_middle_without_junction_matches_native_open_pin_and_erc(self) -> None:
        scan, netlist, erc = self.native_scan(PIN_ON_WIRE_MIDDLE_FAULT)
        self.assertEqual(scan.status, "COMPLETE")
        self.assertEqual(scan.findings, ())
        self.assertEqual(len(scan.pin_tip_on_wire_interiors), 1)
        self.assertEqual(
            scan.pin_tip_on_wire_interiors[0].wire_uuid,
            "b0000000-0000-4000-8000-000000000005",
        )
        open_pins = {
            f"{node.attrib['ref']}.{node.attrib['pin']}"
            for net in netlist.findall("./nets/net")
            if net.attrib.get("name", "").startswith("unconnected-")
            for node in net.findall("node")
        }
        self.assertIn("R1.1", open_pins)
        violations = [
            violation
            for sheet in erc.get("sheets", [])
            for violation in sheet.get("violations", [])
        ]
        self.assertTrue(
            any(
                item.get("type") == "pin_not_connected"
                and any(
                    detail.get("uuid") == "b0000000-0000-4000-8000-000000000003"
                    for detail in item.get("items", [])
                )
                for item in violations
            )
        )
        self.assertTrue(
            any(
                item.get("type") == "unconnected_wire_endpoint"
                and any(
                    detail.get("uuid") == "b0000000-0000-4000-8000-000000000005"
                    for detail in item.get("items", [])
                )
                for item in violations
            )
        )

    def test_no_connect_marker_on_wire_crossing_preserves_native_pin_isolation(self) -> None:
        source = PIN_ON_WIRE_MIDDLE_FAULT.read_bytes()
        marked_source = source.replace(
            b"  (sheet_instances",
            b'  (no_connect (at 76.2 71.12) (uuid "b0000000-0000-4000-8000-000000000007"))\n'
            b"  (sheet_instances",
            1,
        )
        self.assertNotEqual(marked_source, source)

        scan, netlist, erc = self.native_scan(
            marked_source,
            source_name="pin-on-wire-middle-no-connect.kicad_sch",
        )
        self.assertEqual(scan.status, "COMPLETE")
        self.assertFalse(scan.findings)
        self.assertEqual(scan.pin_tip_on_wire_interiors, ())
        forced_unconnected_scan = scan_wire_ends_on_pin_lines(
            marked_source,
            source_path="synthetic/pin-on-wire-middle-no-connect.kicad_sch",
            kicad_version=self.kicad_version,
            unconnected_pins=frozenset({"R1.1"}),
        )
        self.assertEqual(forced_unconnected_scan.pin_tip_on_wire_interiors, ())

        assignments = {
            net.attrib.get("name", ""): {
                f"{node.attrib['ref']}.{node.attrib['pin']}" for node in net.findall("node")
            }
            for net in netlist.findall("./nets/net")
        }
        self.assertNotIn("R1.1", assignments.get("/CONTROL_NET", set()))
        violations = [
            item for sheet in erc.get("sheets", []) for item in sheet.get("violations", [])
        ]
        self.assertFalse(
            any(
                item.get("type") == "pin_not_connected"
                and any(
                    detail.get("uuid") == "b0000000-0000-4000-8000-000000000003"
                    for detail in item.get("items", [])
                )
                for item in violations
            )
        )

    def test_pin_on_wire_middle_junction_control_matches_native_connectivity(self) -> None:
        scan, netlist, erc = self.native_scan(PIN_ON_WIRE_MIDDLE_CONTROL)
        self.assertEqual(scan.status, "COMPLETE")
        self.assertEqual(scan.findings, ())
        self.assertEqual(scan.pin_tip_on_wire_interiors, ())
        open_pins = {
            f"{node.attrib['ref']}.{node.attrib['pin']}"
            for net in netlist.findall("./nets/net")
            if net.attrib.get("name", "").startswith("unconnected-")
            for node in net.findall("node")
        }
        self.assertNotIn("R1.1", open_pins)
        nets = {
            net.attrib.get("name"): {
                f"{node.attrib['ref']}.{node.attrib['pin']}" for node in net.findall("node")
            }
            for net in netlist.findall("./nets/net")
        }
        self.assertIn("R1.1", nets["/CONTROL_NET"])
        violations = [
            violation
            for sheet in erc.get("sheets", [])
            for violation in sheet.get("violations", [])
        ]
        self.assertFalse(
            any(
                item.get("type") == "pin_not_connected"
                and any(
                    detail.get("uuid") == "b0000000-0000-4000-8000-000000000003"
                    for detail in item.get("items", [])
                )
                for item in violations
            )
        )

    def test_wire_endpoint_near_pin_tip_matches_native_erc_fault_and_control(self) -> None:
        fault, fault_netlist, fault_erc = self.native_scan(WIRE_END_NEAR_PIN_TIP_FAULT)
        self.assertEqual(fault.status, "COMPLETE")
        self.assertEqual(len(fault.wire_endpoints_near_pin_tips), 1)
        finding = fault.wire_endpoints_near_pin_tips[0]
        self.assertEqual((finding.reference, finding.pin_number), ("R1", "1"))
        self.assertEqual(finding.distance_to_pin_tip_mm, MAX_PIN_ENDPOINT_GAP_MM)
        open_pins = {
            f"{node.attrib['ref']}.{node.attrib['pin']}"
            for net in fault_netlist.findall("./nets/net")
            if net.attrib.get("name", "").startswith("unconnected-")
            for node in net.findall("node")
        }
        self.assertIn("R1.1", open_pins)
        fault_violations = [
            violation
            for sheet in fault_erc.get("sheets", [])
            for violation in sheet.get("violations", [])
        ]
        self.assertTrue(
            any(
                item.get("type") == "pin_not_connected"
                and any(detail.get("uuid") == finding.pin_uuid for detail in item.get("items", []))
                for item in fault_violations
            )
        )
        self.assertTrue(
            any(
                item.get("type") == "unconnected_wire_endpoint"
                and any(detail.get("uuid") == finding.wire_uuid for detail in item.get("items", []))
                for item in fault_violations
            )
        )

        control, control_netlist, control_erc = self.native_scan(CONTROL)
        self.assertEqual(control.wire_endpoints_near_pin_tips, ())
        connected_nets = {
            net.attrib.get("name", ""): {
                f"{node.attrib['ref']}.{node.attrib['pin']}" for node in net.findall("node")
            }
            for net in control_netlist.findall("./nets/net")
        }
        self.assertNotIn(
            "R1.1",
            {
                f"{node.attrib['ref']}.{node.attrib['pin']}"
                for net in control_netlist.findall("./nets/net")
                if net.attrib.get("name", "").startswith("unconnected-")
                for node in net.findall("node")
            },
        )
        self.assertIn("R1.1", connected_nets["/CONTROL_NET"])
        control_violations = [
            violation
            for sheet in control_erc.get("sheets", [])
            for violation in sheet.get("violations", [])
        ]
        self.assertFalse(
            any(
                item.get("type") == "pin_not_connected"
                and any(
                    detail.get("uuid") == "b0000000-0000-4000-8000-000000000003"
                    for detail in item.get("items", [])
                )
                for item in control_violations
            )
        )

    def test_label_near_wire_endpoint_matches_native_erc_fault_and_control(self) -> None:
        fault, _fault_netlist, fault_erc = self.native_scan(LABEL_NEAR_WIRE_ENDPOINT)
        self.assertEqual(fault.status, "COMPLETE")
        self.assertEqual(len(fault.labels_near_wire_endpoints), 1)
        finding = fault.labels_near_wire_endpoints[0]
        self.assertEqual(finding.label_uuid, "b0000000-0000-4000-8000-000000000006")
        fault_violations = [
            violation
            for sheet in fault_erc.get("sheets", [])
            for violation in sheet.get("violations", [])
        ]
        self.assertTrue(
            any(
                item.get("type") == "label_dangling"
                and any(
                    detail.get("uuid") == finding.label_uuid for detail in item.get("items", [])
                )
                for item in fault_violations
            )
        )

        control, _control_netlist, control_erc = self.native_scan(CONTROL)
        self.assertEqual(control.labels_near_wire_endpoints, ())
        control_violations = [
            violation
            for sheet in control_erc.get("sheets", [])
            for violation in sheet.get("violations", [])
        ]
        self.assertFalse(
            any(
                item.get("type") == "label_dangling"
                and any(
                    detail.get("uuid") == "b0000000-0000-4000-8000-000000000006"
                    for detail in item.get("items", [])
                )
                for item in control_violations
            )
        )

    def test_unmarked_crossing_has_native_wire_diagnostics_and_marked_control_does_not_lint(
        self,
    ) -> None:
        fault, _fault_netlist, fault_erc = self.native_scan(UNMARKED_CROSSING)
        control, _control_netlist, control_erc = self.native_scan(JUNCTION_MARKED_CROSSING)

        self.assertEqual(fault.status, "COMPLETE")
        self.assertEqual(len(fault.unmarked_wire_crossings), 1)
        crossing = fault.unmarked_wire_crossings[0]
        self.assertEqual(crossing.crossing_mm, (127.0, 127.0))
        self.assertEqual(
            crossing.wire_uuids,
            (
                "c0000000-0000-4000-8000-000000000008",
                "c0000000-0000-4000-8000-000000000009",
            ),
        )
        self.assertEqual(control.status, "COMPLETE")
        self.assertEqual(control.unmarked_wire_crossings, ())

        for erc in (fault_erc, control_erc):
            violations = [
                violation
                for sheet in erc.get("sheets", [])
                for violation in sheet.get("violations", [])
            ]
            native_wire_uuids = {
                item.get("uuid")
                for violation in violations
                if violation.get("type") in {"wire_dangling", "unconnected_wire_endpoint"}
                for item in violation.get("items", [])
            }
            self.assertTrue(set(crossing.wire_uuids).issubset(native_wire_uuids))

    def test_graphical_polyline_crossing_preserves_native_connectivity_and_erc(self) -> None:
        baseline_source = _graphical_crossing_baseline()
        graphical_source = GRAPHICAL_ONLY_CROSSING.read_bytes()
        source_name = "graphical-only-crossing-control.kicad_sch"
        baseline, baseline_netlist, baseline_erc = self.native_scan(
            baseline_source, source_name=source_name
        )
        graphical, graphical_netlist, graphical_erc = self.native_scan(
            graphical_source, source_name=source_name
        )

        self.assertEqual(graphical.status, "COMPLETE")
        self.assertEqual(_geometry_candidates(graphical), _geometry_candidates(baseline))
        self.assertTrue(all(not group for group in _geometry_candidates(graphical)))
        self.assertEqual(
            _netlist_components_without_sheetfile(graphical_netlist),
            _netlist_components_without_sheetfile(baseline_netlist),
        )
        graphical_nets = graphical_netlist.find("./nets")
        baseline_nets = baseline_netlist.find("./nets")
        self.assertIsNotNone(graphical_nets)
        self.assertIsNotNone(baseline_nets)
        self.assertEqual(ET.tostring(graphical_nets), ET.tostring(baseline_nets))

        def violation_signatures(report: dict[str, object]) -> tuple[tuple[object, ...], ...]:
            violations = [
                violation
                for sheet in report.get("sheets", [])
                for violation in sheet.get("violations", [])
            ]
            return tuple(
                sorted(
                    (
                        violation["type"],
                        violation["severity"],
                        tuple(item.get("uuid") for item in violation["items"]),
                    )
                    for violation in violations
                )
            )

        self.assertEqual(violation_signatures(graphical_erc), violation_signatures(baseline_erc))
        graphical_svg = self.native_svg(graphical_source, source_name=source_name)
        baseline_svg = self.native_svg(baseline_source, source_name=source_name)
        _native_svg_matching_line(graphical_svg, (82.55, 68.58), (82.55, 73.66))
        _native_svg_matching_rect(graphical_svg, 85.09, 69.85, 5.08, 2.54)
        circle_source = (
            b"  (circle (center 95.25 71.12) (radius 1.27)\n"
            b"    (stroke (width 0) (type default)) (fill (type none))\n"
            b'    (uuid "d0000000-0000-4000-8000-000000000003"))\n'
        )
        self.assertEqual(graphical_source.count(circle_source), 1)
        without_circle_svg = self.native_svg(
            graphical_source.replace(circle_source, b"", 1), source_name=source_name
        )
        svg_geometry_tags = {"path", "rect", "circle", "ellipse", "polygon", "line"}

        def svg_geometry_count(root: ET.Element) -> int:
            return sum(
                1 for element in root.iter() if element.tag.rsplit("}", 1)[-1] in svg_geometry_tags
            )

        self.assertEqual(svg_geometry_count(graphical_svg), svg_geometry_count(baseline_svg) + 3)
        self.assertGreater(
            svg_geometry_count(graphical_svg), svg_geometry_count(without_circle_svg)
        )

    def test_unmarked_t_junction_matches_native_netlist_and_erc_control(self) -> None:
        fault, fault_netlist, fault_erc = self.native_scan(T_JUNCTION_FAULT)
        control, control_netlist, control_erc = self.native_scan(T_JUNCTION_CONTROL)

        self.assertEqual(fault.status, "COMPLETE")
        self.assertEqual(len(fault.unmarked_t_junctions), 1)
        finding = fault.unmarked_t_junctions[0]
        self.assertEqual(finding.junction_mm, (88.9, 71.12))
        self.assertEqual(control.status, "COMPLETE")
        self.assertEqual(control.unmarked_t_junctions, ())

        def pin_nets(netlist: ET.Element) -> dict[str, str]:
            return {
                f"{node.attrib['ref']}.{node.attrib['pin']}": net.attrib["name"]
                for net in netlist.findall("./nets/net")
                for node in net.findall("node")
            }

        fault_nets = pin_nets(fault_netlist)
        control_nets = pin_nets(control_netlist)
        self.assertEqual(fault_nets["R1.1"], "/CONTROL_NET")
        self.assertTrue(fault_nets["R1.2"].startswith("unconnected-("))
        self.assertEqual(control_nets["R1.1"], "/CONTROL_NET")
        self.assertEqual(control_nets["R1.2"], "/CONTROL_NET")

        def violations(report: dict[str, object]) -> list[dict[str, object]]:
            return [
                item for sheet in report.get("sheets", []) for item in sheet.get("violations", [])
            ]

        fault_violations = violations(fault_erc)
        self.assertTrue(
            any(
                item.get("type") == "unconnected_wire_endpoint"
                and any(
                    detail.get("uuid") == finding.endpoint_wire_uuid
                    for detail in item.get("items", [])
                )
                for item in fault_violations
            )
        )
        self.assertTrue(
            any(
                item.get("type") == "pin_not_connected"
                and any(
                    detail.get("uuid") == "b0000000-0000-4000-8000-000000000004"
                    for detail in item.get("items", [])
                )
                for item in fault_violations
            )
        )
        control_violations = violations(control_erc)
        self.assertFalse(
            any(
                item.get("type") in {"pin_not_connected", "unconnected_wire_endpoint"}
                for item in control_violations
            )
        )

    def test_reused_child_sheet_netlist_expansion_and_erc_fault_control(self) -> None:
        scan, netlist, erc = self.native_scan(
            REPEATED_SHEET,
            related_sources=(REPEATED_CHANNEL,),
            scan_hierarchy=True,
        )

        self.assertEqual(scan.status, "COMPLETE")
        self.assertEqual(len(scan.unmarked_t_junctions), 2)
        self.assertEqual(len(scan.source_bindings), 3)
        self.assertEqual(
            [component.attrib["ref"] for component in netlist.findall("./components/comp")],
            ["R1", "R2"],
        )
        net_assignments = {
            (node.attrib["ref"], node.attrib["pin"]): net.attrib["name"]
            for net in netlist.findall("./nets/net")
            for node in net.findall("node")
        }
        self.assertEqual(net_assignments[("R1", "1")], "/InstanceA/CONTROL_NET")
        self.assertEqual(net_assignments[("R2", "1")], "/InstanceB/CONTROL_NET")
        self.assertEqual(
            {pin for pin, net in net_assignments.items() if net.startswith("unconnected-")},
            {("R1", "2"), ("R2", "2")},
        )

        pin_uuids = {
            detail["uuid"]
            for sheet in erc.get("sheets", [])
            for violation in sheet.get("violations", [])
            if violation.get("type") == "pin_not_connected"
            for detail in violation.get("items", [])
        }
        self.assertEqual(pin_uuids, {"b0000000-0000-4000-8000-000000000004"})

        control_scan, control_netlist, control_erc = self.native_scan(
            REPEATED_SHEET_CONTROL,
            related_sources=(REPEATED_CHANNEL_CONTROL,),
            scan_hierarchy=True,
        )
        self.assertEqual(control_scan.status, "COMPLETE")
        self.assertEqual(control_scan.unmarked_t_junctions, ())
        control_assignments = {
            (node.attrib["ref"], node.attrib["pin"]): net.attrib["name"]
            for net in control_netlist.findall("./nets/net")
            for node in net.findall("node")
        }
        self.assertEqual(control_assignments[("R1", "2")], "/InstanceA/CONTROL_NET")
        self.assertEqual(control_assignments[("R2", "2")], "/InstanceB/CONTROL_NET")
        control_pin_violations = [
            violation
            for sheet in control_erc.get("sheets", [])
            for violation in sheet.get("violations", [])
            if violation.get("type") == "pin_not_connected"
        ]
        self.assertEqual(control_pin_violations, [])

    def test_free_dangling_wire_is_already_localized_by_native_erc(self) -> None:
        scan, _netlist, erc = self.native_scan(DANGLING_WIRE)

        self.assertEqual(scan.status, "COMPLETE")
        self.assertEqual(scan.findings, ())
        self.assertEqual(scan.pin_tip_on_wire_interiors, ())
        self.assertEqual(scan.wire_endpoints_near_pin_tips, ())
        self.assertEqual(scan.labels_near_wire_endpoints, ())
        self.assertEqual(scan.unmarked_wire_crossings, ())
        self.assertEqual(scan.unmarked_t_junctions, ())

        violations = [
            item for sheet in erc.get("sheets", []) for item in sheet.get("violations", [])
        ]
        wire_uuid = "e0000000-0000-4000-8000-000000000001"
        native_wire_findings = [
            item
            for item in violations
            if item.get("type") in {"wire_dangling", "unconnected_wire_endpoint"}
            and any(detail.get("uuid") == wire_uuid for detail in item.get("items", []))
        ]
        self.assertTrue(any(item.get("type") == "wire_dangling" for item in native_wire_findings))
        self.assertTrue(
            any(item.get("type") == "unconnected_wire_endpoint" for item in native_wire_findings)
        )

    def test_all_supported_symbol_transforms_match_native_open_pin_netlists(self) -> None:
        for (angle, mirror), endpoint in TRANSFORM_MIDPOINTS.items():
            with self.subTest(angle=angle, mirror=mirror):
                source = transformed_fault(angle, mirror, endpoint)
                with tempfile.TemporaryDirectory(
                    prefix="schematic-geometry-transform-"
                ) as directory:
                    root = Path(directory)
                    schematic = root / "transformed-near-miss.kicad_sch"
                    netlist = root / "netlist.xml"
                    erc_path = root / "erc.json"
                    schematic.write_bytes(source)
                    result = subprocess.run(
                        (
                            str(self.cli),
                            "sch",
                            "export",
                            "netlist",
                            "--format",
                            "kicadxml",
                            "--output",
                            str(netlist),
                            str(schematic),
                        ),
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
                    erc_result = subprocess.run(
                        (
                            str(self.cli),
                            "sch",
                            "erc",
                            "--format",
                            "json",
                            "--output",
                            str(erc_path),
                            str(schematic),
                        ),
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    self.assertEqual(
                        erc_result.returncode, 0, erc_result.stderr or erc_result.stdout
                    )
                    root_xml = ET.parse(netlist).getroot()
                    open_pins = {
                        f"{node.attrib['ref']}.{node.attrib['pin']}"
                        for net in root_xml.findall("./nets/net")
                        if net.attrib.get("name", "").startswith("unconnected-")
                        for node in net.findall("node")
                    }
                    self.assertIn("R1.1", open_pins)
                    scan = scan_wire_ends_on_pin_lines(
                        source,
                        source_path=schematic.name,
                        kicad_version=self.kicad_version,
                        unconnected_pins=frozenset(open_pins),
                    )
                    self.assertEqual(len(scan.findings), 1)
                    self.assertEqual(scan.findings[0].wire_endpoint_mm, endpoint)
                    pin_uuid = scan.findings[0].pin_uuid
                    self.assertIsNotNone(pin_uuid)
                    erc = json.loads(erc_path.read_text(encoding="utf-8"))
                    native_pin_positions = [
                        detail["pos"]
                        for sheet in erc.get("sheets", [])
                        for violation in sheet.get("violations", [])
                        if violation.get("type") == "pin_not_connected"
                        for detail in violation.get("items", [])
                        if detail.get("uuid") == pin_uuid
                    ]
                    self.assertEqual(len(native_pin_positions), 1)
                    self.assertAlmostEqual(
                        native_pin_positions[0]["x"] * 100,
                        scan.findings[0].pin_tip_mm[0],
                        places=6,
                    )
                    self.assertAlmostEqual(
                        native_pin_positions[0]["y"] * 100,
                        scan.findings[0].pin_tip_mm[1],
                        places=6,
                    )


if __name__ == "__main__":
    unittest.main()
