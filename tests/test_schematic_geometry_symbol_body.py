"""Focused symbol body schematic geometry regressions."""

from __future__ import annotations

import hashlib

import pytest

from tests.design_lint_fixtures.schematic_geometry_fixtures import (
    TRANSFORM_MIDPOINTS,
    _transform_fixture_point,
    enclosed_connector_body_wire_fixture,
    free_text_objects_fixture,
    free_text_symbol_body_fixture,
    symbol_body_wire_fixture,
    transformed_symbol_body_wire,
)
from tests.design_lint_fixtures.schematic_geometry_test_cases import SchematicGeometryHelpers

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.schematic_lint,
    pytest.mark.schematic_text_lint,
]


class SchematicGeometrySymbolBodyTests(SchematicGeometryHelpers):
    def test_wire_through_symbol_body_is_reported_and_clear_control_is_valid(self) -> None:
        fault = self.scan(symbol_body_wire_fixture(), unconnected_pins=frozenset())
        control = self.scan(
            symbol_body_wire_fixture(((71.12, 82.55), (81.28, 82.55))),
            unconnected_pins=frozenset(),
        )

        assert (fault.status) == ("COMPLETE")
        assert (len(fault.wires_through_symbol_bodies)) == (1)
        finding = fault.wires_through_symbol_bodies[0]
        assert ((finding.reference, finding.symbol_library_id)) == (("R1", "Lint:R"))
        assert (finding.symbol_uuid) == ("b0000000-0000-4000-8000-000000000002")
        assert (finding.wire_uuid) == ("f1000000-0000-4000-8000-000000000001")
        assert (finding.body_box_mm) == ((74.93, 73.66, 77.47, 78.74))
        assert (finding.overlap_start_mm) == ((75.13, 76.2))
        assert (finding.overlap_end_mm) == ((77.27, 76.2))
        assert (finding.overlap_length_mm) == (2.14)
        assert (control.status) == ("COMPLETE")
        assert (control.wires_through_symbol_bodies) == (())

    def test_unsupported_text_limits_only_text_rule_coverage(self) -> None:
        source = symbol_body_wire_fixture()
        text = (
            b'  (text "UNSUPPORTED~{LINE}" (at 25.4 25.4 0) '
            b"(effects (font (size 1.27 1.27))) "
            b'(uuid "f1000000-0000-4000-8000-000000000009"))\n'
        )
        assert (source.count(b"  (sheet_instances")) == (1)
        source = source.replace(b"  (sheet_instances", text + b"  (sheet_instances", 1)

        result = self.scan(source, unconnected_pins=frozenset())

        assert (result.status) == ("PARTIAL")
        assert (len(result.wires_through_symbol_bodies)) == (1)
        assert ("schematic.free_text_overlap") in (result.unsupported_by_rule)
        assert ("schematic.free_text_over_wire") in (result.unsupported_by_rule)
        assert ("schematic.wire_through_symbol_body") not in (result.unsupported_by_rule)

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

        assert (too_short.wires_through_symbol_bodies) == (())
        assert (len(at_minimum.wires_through_symbol_bodies)) == (1)
        assert (at_minimum.wires_through_symbol_bodies[0].overlap_length_mm) == (0.3)
        assert (outside_guard.wires_through_symbol_bodies) == (())

    def test_peer_connector_contacts_inside_symbol_body_remain_review_candidates(self) -> None:
        enclosed = self.scan(
            enclosed_connector_body_wire_fixture(body_offset_x=0.0),
            unconnected_pins=frozenset(),
        )
        outside = self.scan(
            enclosed_connector_body_wire_fixture(body_offset_x=2.54),
            unconnected_pins=frozenset(),
        )

        assert (enclosed.status) == ("COMPLETE")
        assert (
            tuple(
                (candidate.reference, candidate.symbol_library_id, candidate.overlap_length_mm)
                for candidate in enclosed.wires_through_symbol_bodies
            )
        ) == (
            (
                ("J1", "Connector_Generic:Conn_01x01", 2.34),
                ("J2", "Connector_Generic:Conn_01x01", 2.34),
            )
        )
        assert (outside.status) == ("COMPLETE")
        assert (outside.wires_through_symbol_bodies) == (())
        assert (enclosed.source_sha256) != (outside.source_sha256)

    def test_symbol_body_wire_tracks_all_supported_orthogonal_transforms(self) -> None:
        semantic_finding: tuple[str, str, str, str, float, str] | None = None
        source_hashes: set[str] = set()
        for angle, mirror in TRANSFORM_MIDPOINTS:
            source = transformed_symbol_body_wire(angle, mirror)
            result = self.scan(
                source,
                unconnected_pins=frozenset(),
            )
            assert (result.status) == ("COMPLETE")
            assert (len(result.wires_through_symbol_bodies)) == (1)
            finding = result.wires_through_symbol_bodies[0]
            assert (finding.overlap_length_mm) == (2.14)
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
            assert (observed_semantics) == (semantic_finding)
            assert (result.source_sha256) == (hashlib.sha256(source).hexdigest())
            source_hashes.add(result.source_sha256)

            start = _transform_fixture_point((71.12, 76.2), angle, mirror)
            end = _transform_fixture_point((81.28, 76.2), angle, mirror)
            wire_points = f"(xy {start[0]} {start[1]}) (xy {end[0]} {end[1]})".encode()
            reverse_points = f"(xy {end[0]} {end[1]}) (xy {start[0]} {start[1]})".encode()
            assert (source.count(wire_points)) == (1)
            reversed_source = source.replace(wire_points, reverse_points, 1)
            reversed_result = self.scan(reversed_source, unconnected_pins=frozenset())
            assert (reversed_result.status) == ("COMPLETE")
            assert (len(reversed_result.wires_through_symbol_bodies)) == (1)
            reversed_finding = reversed_result.wires_through_symbol_bodies[0]
            assert (
                (
                    reversed_finding.reference,
                    reversed_finding.symbol_library_id,
                    reversed_finding.symbol_uuid,
                    reversed_finding.wire_uuid,
                    reversed_finding.overlap_length_mm,
                    reversed_finding.sheet_instance_path,
                )
            ) == (observed_semantics)

        assert (semantic_finding) is not None
        assert (len(source_hashes)) > (1)

        baseline = transformed_symbol_body_wire(0, None)
        wire_points = b"(xy 71.12 76.2) (xy 81.28 76.2)"
        clear_points = b"(xy 71.12 82.55) (xy 81.28 82.55)"
        assert (baseline.count(wire_points)) == (1)
        clear_source = baseline.replace(wire_points, clear_points, 1)
        clear = self.scan(clear_source, unconnected_pins=frozenset())
        assert (clear.status) == ("COMPLETE")
        assert (clear.wires_through_symbol_bodies) == (())

    def test_free_text_over_symbol_body_is_reported_with_clear_control(self) -> None:
        fault = self.scan(free_text_symbol_body_fixture(), unconnected_pins=frozenset())
        control = self.scan(
            free_text_symbol_body_fixture(point=(88.9, 76.2)),
            unconnected_pins=frozenset(),
        )

        assert (fault.status) == ("COMPLETE")
        assert (len(fault.free_text_symbol_body_overlaps)) == (1)
        finding = fault.free_text_symbol_body_overlaps[0]
        assert (finding.text) == ("BODY NOTE")
        assert (finding.text_uuid) == ("f2000000-0000-4000-8000-000000000001")
        assert ((finding.reference, finding.symbol_library_id)) == (("R1", "Lint:R"))
        assert (finding.body_box_mm) == ((74.93, 73.66, 77.47, 78.74))
        assert (finding.overlap_box_mm) == ((75.08, 74.798987, 77.32, 77.209091))
        assert (finding.overlap_area_mm2) == (5.398633)
        assert (control.status) == ("COMPLETE")
        assert (control.free_text_symbol_body_overlaps) == (())

    def test_text_body_overlap_is_root_order_stable_and_moving_text_clears_candidate(
        self,
    ) -> None:
        source = free_text_symbol_body_fixture()
        baseline = self.scan(source, unconnected_pins=frozenset())
        assert (len(baseline.free_text_symbol_body_overlaps)) == (1)
        text_line = next(
            line
            for line in source.splitlines(keepends=True)
            if b'uuid "f2000000-0000-4000-8000-000000000001"' in line
        )
        assert (source.count(text_line)) == (1)
        without_text = source.replace(text_line, b"", 1)
        reordered_source = without_text.replace(b"  (wire (pts", text_line + b"  (wire (pts", 1)
        reordered = self.scan(reordered_source, unconnected_pins=frozenset())
        assert (reordered.status) == ("COMPLETE")
        assert (len(reordered.free_text_symbol_body_overlaps)) == (1)
        baseline_finding = baseline.free_text_symbol_body_overlaps[0]
        reordered_finding = reordered.free_text_symbol_body_overlaps[0]
        assert (
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
            )
        ) == (
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
            )
        )
        assert (reordered.source_sha256) != (baseline.source_sha256)

        moved_text_line = text_line.replace(
            b"(at 76.2 76.2 0)",
            b"(at 88.9 76.2 0)",
            1,
        )
        moved_source = source.replace(text_line, moved_text_line, 1)
        moved = self.scan(moved_source, unconnected_pins=frozenset())
        assert (moved.status) == ("COMPLETE")
        assert (moved.free_text_symbol_body_overlaps) == (())

    def test_free_text_symbol_body_overlap_uses_area_threshold(self) -> None:
        below = self.scan(
            free_text_symbol_body_fixture(point=(76.2, 72.84)),
            unconnected_pins=frozenset(),
        )
        above = self.scan(
            free_text_symbol_body_fixture(point=(76.2, 72.85)),
            unconnected_pins=frozenset(),
        )

        assert (below.free_text_symbol_body_overlaps) == (())
        assert (len(above.free_text_symbol_body_overlaps)) == (1)
        assert (above.free_text_symbol_body_overlaps[0].overlap_area_mm2) >= (0.1)

    def test_unsupported_symbol_body_primitive_makes_coverage_partial(self) -> None:
        source = symbol_body_wire_fixture().replace(b"(rectangle", b"(arc", 1)
        result = self.scan(source, unconnected_pins=frozenset())

        assert (result.status) == ("PARTIAL")
        assert (result.wires_through_symbol_bodies) == (())
        assert any("primitive 'arc' is unsupported" in item for item in result.unsupported)

    def test_unsupported_free_text_variants_leave_geometry_coverage_partial(self) -> None:
        overlap = (25.4, 25.4)
        base = free_text_objects_fixture("FIRST", overlap, "SECOND", (29.0, 25.4))

        def replace_once(source: bytes, old: bytes, new: bytes) -> bytes:
            start = source.index(b'(text "FIRST"')
            end_marker = b'(uuid "d0000000-0000-4000-8000-000000000001"))'
            end = source.index(end_marker, start) + len(end_marker)
            text_node = source[start:end]
            assert (text_node.count(old)) == (1)
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
            result = self.scan(source, unconnected_pins=frozenset())
            assert (result.status) == ("PARTIAL")
            assert (result.free_text_overlaps) == (())
            assert (result.free_text_wire_overlaps) == (())
            assert (result.free_text_symbol_body_overlaps) == (())
            assert any(expected_issue in issue.casefold() for issue in result.unsupported), (
                result.unsupported
            )
