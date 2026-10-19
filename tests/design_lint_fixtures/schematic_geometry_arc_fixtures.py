"""Small synthetic symbol-arc mutations for schematic geometry regressions."""

from __future__ import annotations

import re

from tests.design_lint_fixtures.schematic_geometry_fixtures import (
    CONTROL,
    _transform_fixture_point,
)

_RECTANGLE = b"""(rectangle (start -1.27 2.54) (end 1.27 -2.54)
          (stroke (width 0.254) (type default)) (fill (type none)))"""
_ARC_TEMPLATE = (
    "(arc (start {start_x} {start_y}) (mid {mid_x} {mid_y}) "
    "(end {end_x} {end_y}) "
    "(stroke (width 0.254) (type default)) (fill (type none)))"
)


def symbol_arc_body_wire_fixture(
    *,
    local_wire_y: float,
    arc_points: tuple[tuple[float, float], tuple[float, float], tuple[float, float]] = (
        (-5.08, 0.0),
        (0.0, 5.08),
        (5.08, 0.0),
    ),
    angle: int = 0,
    mirror: str | None = None,
) -> bytes:
    """Add a line crossing a three-point arc in a known symbol transform."""
    source = CONTROL.read_bytes()
    if source.count(_RECTANGLE) != 1:
        raise AssertionError("connected-pin control has no unique rectangle body primitive")
    coordinates = {
        name: point for name, point in zip(("start", "mid", "end"), arc_points, strict=True)
    }
    arc = _ARC_TEMPLATE.format(
        start_x=coordinates["start"][0],
        start_y=coordinates["start"][1],
        mid_x=coordinates["mid"][0],
        mid_y=coordinates["mid"][1],
        end_x=coordinates["end"][0],
        end_y=coordinates["end"][1],
    ).encode("ascii")
    source = source.replace(_RECTANGLE, arc, 1)

    source_text = source.decode("utf-8")
    source_text, symbol_count = re.subn(
        r'\(symbol \(lib_id "Lint:R"\) \(at 76\.2 76\.2 0\) \(unit 1\)',
        f'(symbol (lib_id "Lint:R") (at 76.2 76.2 {angle}) (unit 1)',
        source_text,
        count=1,
    )
    if symbol_count != 1:
        raise AssertionError("connected-pin control has no unique placed resistor")
    if mirror is not None:
        source_text = source_text.replace(
            f"(at 76.2 76.2 {angle}) (unit 1)",
            f"(at 76.2 76.2 {angle}) (unit 1) (mirror {mirror})",
            1,
        )

    start = _transform_fixture_point((71.12, 76.2 - local_wire_y), angle, mirror)
    end = _transform_fixture_point((81.28, 76.2 - local_wire_y), angle, mirror)
    wire = (
        f"  (wire (pts (xy {start[0]} {start[1]}) (xy {end[0]} {end[1]})) "
        "(stroke (width 0) (type default)) "
        '(uuid "f3000000-0000-4000-8000-000000000001"))'
    )
    marker = "  (sheet_instances"
    if source_text.count(marker) != 1:
        raise AssertionError("connected-pin control has no unique sheet_instances node")
    return source_text.replace(marker, f"{wire}\n{marker}", 1).encode("utf-8")


def symbol_arc_body_text_fixture(
    *,
    text_point: tuple[float, float],
    local_wire_y: float = 2.54,
) -> bytes:
    """Place one supported free-text object over or clear of the same arc body."""
    source = symbol_arc_body_wire_fixture(local_wire_y=local_wire_y).decode("utf-8")
    text = (
        f'  (text "ARC NOTE" (at {text_point[0]} {text_point[1]} 0) '
        "(effects (font (size 1.27 1.27))) "
        '(uuid "f4000000-0000-4000-8000-000000000001"))'
    )
    marker = "  (sheet_instances"
    if source.count(marker) != 1:
        raise AssertionError("arc source has no unique sheet_instances node")
    return source.replace(marker, f"{text}\n{marker}", 1).encode("utf-8")
