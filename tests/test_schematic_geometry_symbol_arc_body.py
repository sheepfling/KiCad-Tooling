"""Synthetic arc bounds for the schematic symbol-body review heuristic."""

from __future__ import annotations

import pytest

from tests.design_lint_fixtures.schematic_geometry_arc_fixtures import (
    symbol_arc_body_text_fixture,
    symbol_arc_body_wire_fixture,
)
from tests.design_lint_fixtures.schematic_geometry_fixtures import (
    _transform_fixture_point,
)
from tests.design_lint_fixtures.schematic_geometry_test_cases import SchematicGeometryHelpers

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.schematic_lint,
    pytest.mark.schematic_text_lint,
]


@pytest.mark.design_lint_rule(rule_id="schematic.wire_through_symbol_body")
def test_arc_wire_candidate_uses_the_swept_arc_envelope_and_clear_control() -> None:
    scanner = SchematicGeometryHelpers()
    fault = scanner.scan(
        symbol_arc_body_wire_fixture(local_wire_y=2.54),
        unconnected_pins=frozenset(),
    )
    control = scanner.scan(
        symbol_arc_body_wire_fixture(local_wire_y=-7.62),
        unconnected_pins=frozenset(),
    )

    assert fault.status == "COMPLETE"
    assert len(fault.wires_through_symbol_bodies) == 1
    finding = fault.wires_through_symbol_bodies[0]
    assert finding.body_box_mm == (71.12, 71.12, 81.28, 76.2)
    assert finding.overlap_length_mm == 9.76
    assert control.status == "COMPLETE"
    assert control.wires_through_symbol_bodies == ()


@pytest.mark.design_lint_rule(rule_id="schematic.wire_through_symbol_body")
def test_major_arc_contains_only_extrema_that_lie_on_its_selected_sweep() -> None:
    scanner = SchematicGeometryHelpers()
    major_arc = symbol_arc_body_wire_fixture(
        local_wire_y=0.0,
        arc_points=((5.08, 0.0), (-5.08, 0.0), (0.0, 5.08)),
    )
    result = scanner.scan(major_arc, unconnected_pins=frozenset())

    assert result.status == "COMPLETE"
    assert len(result.wires_through_symbol_bodies) == 1
    assert result.wires_through_symbol_bodies[0].body_box_mm == (
        71.12,
        71.12,
        81.28,
        81.28,
    )


@pytest.mark.design_lint_rule(rule_id="schematic.wire_through_symbol_body")
def test_arc_envelope_is_stable_across_orthogonal_transforms() -> None:
    base_points = ((71.12, 76.2), (76.2, 71.12), (81.28, 76.2))
    for angle in (0, 90, 180, 270):
        for mirror in (None, "x", "y"):
            result = SchematicGeometryHelpers().scan(
                symbol_arc_body_wire_fixture(
                    local_wire_y=2.54,
                    angle=angle,
                    mirror=mirror,
                ),
                unconnected_pins=frozenset(),
            )
            transformed = tuple(
                _transform_fixture_point(point, angle, mirror) for point in base_points
            )
            expected_box = (
                min(point[0] for point in transformed),
                min(point[1] for point in transformed),
                max(point[0] for point in transformed),
                max(point[1] for point in transformed),
            )

            assert result.status == "COMPLETE"
            assert len(result.wires_through_symbol_bodies) == 1
            assert result.wires_through_symbol_bodies[0].body_box_mm == expected_box


@pytest.mark.design_lint_rule(rule_id="schematic.wire_through_symbol_body")
@pytest.mark.design_lint_rule(rule_id="schematic.free_text_over_symbol_body")
def test_collinear_arc_keeps_symbol_body_coverage_partial() -> None:
    source = symbol_arc_body_wire_fixture(local_wire_y=2.54).replace(
        b"(mid 0.0 5.08)",
        b"(mid 0.0 0.0)",
        1,
    )
    result = SchematicGeometryHelpers().scan(source, unconnected_pins=frozenset())

    assert result.status == "PARTIAL"
    assert result.wires_through_symbol_bodies == ()
    assert any("collinear or degenerate" in item for item in result.unsupported)
    assert {
        "schematic.free_text_over_symbol_body",
        "schematic.wire_through_symbol_body",
    } <= set(result.unsupported_by_rule)


@pytest.mark.design_lint_rule(rule_id="schematic.free_text_over_symbol_body")
def test_free_text_arc_body_overlap_has_fault_and_moved_control() -> None:
    scanner = SchematicGeometryHelpers()
    fault = scanner.scan(
        symbol_arc_body_text_fixture(text_point=(76.2, 73.66)),
        unconnected_pins=frozenset(),
    )
    control = scanner.scan(
        symbol_arc_body_text_fixture(text_point=(76.2, 80.01)),
        unconnected_pins=frozenset(),
    )

    assert fault.status == "COMPLETE"
    assert len(fault.free_text_symbol_body_overlaps) == 1
    assert fault.free_text_symbol_body_overlaps[0].reference == "R1"
    assert control.status == "COMPLETE"
    assert control.free_text_symbol_body_overlaps == ()
