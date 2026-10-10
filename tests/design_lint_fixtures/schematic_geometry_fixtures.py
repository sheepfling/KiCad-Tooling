"""Synthetic schematic source builders for geometry regressions."""

from __future__ import annotations

import math
import re
from pathlib import Path

from kicad_tooling.hwrepo.schematic_geometry import (
    SchematicGeometryScan,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures/design_lint"


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
