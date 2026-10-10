"""Focused text schematic geometry regressions."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from tests.design_lint_fixtures.schematic_geometry_fixtures import (
    free_text_anchor_fixture,
    free_text_objects_fixture,
    free_text_wire_fixture,
    justify_first_free_text,
)
from tests.design_lint_fixtures.schematic_geometry_test_cases import SchematicGeometryHelpers

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.schematic_lint,
    pytest.mark.schematic_text_lint,
]


class SchematicGeometryTextTests(SchematicGeometryHelpers):
    def test_coincident_free_text_anchors_are_reported(self) -> None:
        result = self.scan(free_text_anchor_fixture((25.4, 25.4), (25.4, 25.4)))
        assert (result.status) == ("COMPLETE")
        assert (len(result.coincident_text_anchors)) == (1)
        assert (result.free_text_overlaps) == (())
        finding = result.coincident_text_anchors[0]
        assert (finding.anchor_mm) == ((25.4, 25.4))
        assert ((finding.first_text, finding.second_text)) == (("GRAPHIC_A", "GRAPHIC_B"))
        assert ((finding.first_uuid, finding.second_uuid)) == (
            (
                "d0000000-0000-4000-8000-000000000001",
                "d0000000-0000-4000-8000-000000000002",
            )
        )

    def test_coincident_text_anchors_are_translation_invariant_and_separation_clears_pair(
        self,
    ) -> None:
        baseline_source = free_text_anchor_fixture((25.4, 25.4), (25.4, 25.4))
        translated_source = free_text_anchor_fixture((200.0, 200.0), (200.0, 200.0))
        baseline = self.scan(baseline_source, unconnected_pins=frozenset())
        translated = self.scan(translated_source, unconnected_pins=frozenset())

        assert (len(baseline.coincident_text_anchors)) == (1)
        assert (len(translated.coincident_text_anchors)) == (1)
        baseline_finding = baseline.coincident_text_anchors[0]
        translated_finding = translated.coincident_text_anchors[0]
        identity = (
            baseline_finding.first_text,
            baseline_finding.first_uuid,
            baseline_finding.second_text,
            baseline_finding.second_uuid,
            baseline_finding.sheet_instance_path,
        )
        assert (
            (
                translated_finding.first_text,
                translated_finding.first_uuid,
                translated_finding.second_text,
                translated_finding.second_uuid,
                translated_finding.sheet_instance_path,
            )
        ) == (identity)
        assert (translated_finding.anchor_mm) == ((200.0, 200.0))
        assert (baseline.source_sha256) == (hashlib.sha256(baseline_source).hexdigest())
        assert (translated.source_sha256) == (hashlib.sha256(translated_source).hexdigest())
        assert (translated.source_sha256) != (baseline.source_sha256)

        separated_source = free_text_anchor_fixture((200.0, 200.0), (205.0, 200.0))
        separated = self.scan(separated_source, unconnected_pins=frozenset())
        assert (separated.status) == ("COMPLETE")
        assert (separated.coincident_text_anchors) == (())

    def test_separate_free_text_anchors_are_not_reported(self) -> None:
        apart = self.scan(free_text_anchor_fixture((25.4, 25.4), (50.8, 25.4)))
        assert (apart.coincident_text_anchors) == (())
        assert (apart.free_text_overlaps) == (())

        within_tolerance = self.scan(free_text_anchor_fixture((25.4, 25.4), (25.4009, 25.4)))
        assert (len(within_tolerance.coincident_text_anchors)) == (1)

        outside_tolerance = self.scan(free_text_anchor_fixture((25.4, 25.4), (25.4011, 25.4)))
        assert (outside_tolerance.coincident_text_anchors) == (())

    def test_distinct_free_text_overlap_is_reported(self) -> None:
        source = free_text_objects_fixture(
            "LONG_LABEL_ALPHA", (25.4, 25.4), "LONG_LABEL_BETA", (29.0, 25.4)
        )
        result = self.scan(source, unconnected_pins=frozenset())
        assert (result.status) == ("COMPLETE")
        assert (result.coincident_text_anchors) == (())
        assert (len(result.free_text_overlaps)) == (1)
        finding = result.free_text_overlaps[0]
        assert ((finding.first_text, finding.second_text)) == (
            ("LONG_LABEL_ALPHA", "LONG_LABEL_BETA")
        )
        assert ((finding.first_uuid, finding.second_uuid)) == (
            (
                "d0000000-0000-4000-8000-000000000001",
                "d0000000-0000-4000-8000-000000000002",
            )
        )
        assert (finding.overlap_box_mm[2] - finding.overlap_box_mm[0]) > (10.0)

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

        assert (baseline.status) == ("COMPLETE")
        assert (baseline.unsupported_by_rule) == ({})
        assert (len(baseline.free_text_overlaps)) == (1)
        assert (translated.status) == ("COMPLETE")
        assert (translated.unsupported_by_rule) == ({})
        assert (len(translated.free_text_overlaps)) == (1)
        assert (control.status) == ("COMPLETE")
        assert (control.free_text_overlaps) == (())
        original = baseline.free_text_overlaps[0]
        shifted = translated.free_text_overlaps[0]
        assert (
            (shifted.first_text, shifted.first_uuid, shifted.second_text, shifted.second_uuid)
        ) == (
            (original.first_text, original.first_uuid, original.second_text, original.second_uuid)
        )
        for before, after in zip(original.overlap_box_mm, shifted.overlap_box_mm, strict=True):
            assert round((after - before) - (100.0), 6) == 0

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
        assert (len(baseline.free_text_overlaps)) == (1)
        assert (len(translated.free_text_overlaps)) == (1)
        baseline_finding = baseline.free_text_overlaps[0]
        translated_finding = translated.free_text_overlaps[0]
        assert (
            (
                translated_finding.first_text,
                translated_finding.first_uuid,
                translated_finding.second_text,
                translated_finding.second_uuid,
                translated_finding.sheet_instance_path,
            )
        ) == (
            (
                baseline_finding.first_text,
                baseline_finding.first_uuid,
                baseline_finding.second_text,
                baseline_finding.second_uuid,
                baseline_finding.sheet_instance_path,
            )
        )
        for baseline_coordinate, translated_coordinate in zip(
            baseline_finding.overlap_box_mm,
            translated_finding.overlap_box_mm,
            strict=True,
        ):
            assert round((translated_coordinate - baseline_coordinate) - (100.0), 6) == 0
        assert (baseline.source_sha256) == (hashlib.sha256(baseline_source).hexdigest())
        assert (translated.source_sha256) == (hashlib.sha256(translated_source).hexdigest())
        assert (translated.source_sha256) != (baseline.source_sha256)

        separated_source = free_text_objects_fixture(
            "LONG_LABEL_ALPHA", (125.4, 125.4), "LONG_LABEL_BETA", (175.0, 125.4)
        )
        separated = self.scan(separated_source, unconnected_pins=frozenset())
        assert (separated.status) == ("COMPLETE")
        assert (separated.free_text_overlaps) == (())

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
            source = justify_first_free_text(
                free_text_objects_fixture("FIRST", (50.0, 50.0), "SECOND", (second_x, 50.0)),
                justification,
            )
            result = self.scan(source, unconnected_pins=frozenset())

            assert (result.status) == ("COMPLETE")
            assert (result.unsupported_by_rule) == ({})
            assert (len(result.free_text_overlaps)) == (1)
            finding = result.free_text_overlaps[0]
            target_uuid = "d0000000-0000-4000-8000-000000000001"
            text_box = (
                finding.first_box_mm if finding.first_uuid == target_uuid else finding.second_box_mm
            )
            assert (target_uuid) in ((finding.first_uuid, finding.second_uuid))
            assert round((text_box[0]) - (expected_box[0]), 7) == 0
            assert round((text_box[2]) - (expected_box[1]), 7) == 0

    def test_empty_free_text_justification_matches_default_centering(self) -> None:
        default_source = free_text_objects_fixture("FIRST", (50.0, 50.0), "SECOND", (54.0, 50.0))
        empty_justify_source = justify_first_free_text(default_source, "")

        default = self.scan(default_source, unconnected_pins=frozenset())
        explicit_empty = self.scan(empty_justify_source, unconnected_pins=frozenset())

        assert (default.status) == ("COMPLETE")
        assert (explicit_empty.status) == ("COMPLETE")
        assert (default.unsupported_by_rule) == ({})
        assert (explicit_empty.unsupported_by_rule) == ({})
        assert (len(default.free_text_overlaps)) == (1)
        assert (len(explicit_empty.free_text_overlaps)) == (1)
        assert (default.free_text_overlaps[0].first_box_mm) == (
            explicit_empty.free_text_overlaps[0].first_box_mm
        )
        assert (default.free_text_overlaps[0].second_box_mm) == (
            explicit_empty.free_text_overlaps[0].second_box_mm
        )

    def test_separated_free_text_overlap_control_is_clear(self) -> None:
        source = free_text_objects_fixture(
            "LONG_LABEL_ALPHA", (25.4, 25.4), "LONG_LABEL_BETA", (50.8, 25.4)
        )
        result = self.scan(source, unconnected_pins=frozenset())
        assert (result.status) == ("COMPLETE")
        assert (result.free_text_overlaps) == (())

    def test_free_text_crossing_wire_is_reported(self) -> None:
        result = self.scan(free_text_wire_fixture("WIRE CROSSING FAULT", (88.9, 71.12)))

        assert (result.status) == ("COMPLETE")
        assert (len(result.free_text_wire_overlaps)) == (1)
        finding = result.free_text_wire_overlaps[0]
        assert (finding.text) == ("WIRE CROSSING FAULT")
        assert (finding.text_uuid) == ("f0000000-0000-4000-8000-000000000001")
        assert (finding.wire_uuid) == ("b0000000-0000-4000-8000-000000000005")
        assert round((finding.wire_segment_start_mm[1]) - (71.12), 7) == 0
        assert round((finding.wire_segment_end_mm[1]) - (71.12), 7) == 0
        assert (finding.overlap_length_mm) > (20.0)

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
        assert (len(baseline.free_text_wire_overlaps)) == (1)
        assert (len(translated.free_text_wire_overlaps)) == (1)
        baseline_finding = baseline.free_text_wire_overlaps[0]
        translated_finding = translated.free_text_wire_overlaps[0]
        assert (
            (
                translated_finding.text,
                translated_finding.text_uuid,
                translated_finding.wire_uuid,
                translated_finding.overlap_length_mm,
                translated_finding.sheet_instance_path,
            )
        ) == (
            (
                baseline_finding.text,
                baseline_finding.text_uuid,
                baseline_finding.wire_uuid,
                baseline_finding.overlap_length_mm,
                baseline_finding.sheet_instance_path,
            )
        )
        for baseline_box_value, translated_box_value in zip(
            baseline_finding.text_box_mm,
            translated_finding.text_box_mm,
            strict=True,
        ):
            assert round((translated_box_value - baseline_box_value) - (100.0), 6) == 0
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
                assert round((translated_coordinate - baseline_coordinate) - (100.0), 7) == 0
        assert (translated.source_sha256) == (hashlib.sha256(translated_source).hexdigest())
        assert (translated.source_sha256) != (baseline.source_sha256)

        clear_source = free_text_wire_fixture(
            "WIRE CROSSING FAULT",
            (188.9, 171.12),
            wire_points=((176.2, 181.12), (201.6, 181.12)),
        )
        clear = self.scan(clear_source, unconnected_pins=frozenset())
        assert (clear.status) == ("COMPLETE")
        assert (clear.free_text_wire_overlaps) == (())

    def test_free_text_clear_of_wire_is_valid_control(self) -> None:
        result = self.scan(free_text_wire_fixture("WIRE CLEAR CONTROL", (88.9, 80.01)))

        assert (result.status) == ("COMPLETE")
        assert (result.free_text_wire_overlaps) == (())

    def test_plain_multiline_text_uses_fault_and_control_geometry(self) -> None:
        fault_text = "TOP\nWIRE CROSSING FAULT\nBOTTOM"
        fault = self.scan(
            free_text_wire_fixture(fault_text, (88.9, 71.12)), unconnected_pins=frozenset()
        )
        control = self.scan(
            free_text_wire_fixture("TOP\nWIRE CLEAR CONTROL\nBOTTOM", (88.9, 80.01)),
            unconnected_pins=frozenset(),
        )

        assert (fault.status) == ("COMPLETE")
        assert (fault.unsupported_by_rule) == ({})
        assert (len(fault.free_text_wire_overlaps)) == (1)
        assert (fault.free_text_wire_overlaps[0].text) == (fault_text)
        assert (control.status) == ("COMPLETE")
        assert (control.free_text_wire_overlaps) == (())

        overlap_fault = self.scan(
            free_text_objects_fixture("FIRST\nSECOND", (25.4, 25.4), "SECOND", (29.0, 25.4)),
            unconnected_pins=frozenset(),
        )
        overlap_control = self.scan(
            free_text_objects_fixture("FIRST\nSECOND", (25.4, 25.4), "SECOND", (50.8, 25.4)),
            unconnected_pins=frozenset(),
        )
        assert (overlap_fault.status) == ("COMPLETE")
        assert (len(overlap_fault.free_text_overlaps)) == (1)
        assert (overlap_control.status) == ("COMPLETE")
        assert (overlap_control.free_text_overlaps) == (())

    def test_literal_backslash_n_is_not_treated_as_a_line_break(self) -> None:
        result = self.scan(
            free_text_wire_fixture("LITERAL\\nSEQUENCE", (88.9, 80.01)),
            unconnected_pins=frozenset(),
        )

        assert (result.status) == ("COMPLETE")
        assert (result.unsupported_by_rule) == ({})
        assert (result.free_text_wire_overlaps) == (())

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

        assert (too_short.free_text_wire_overlaps) == (())
        assert (len(at_minimum.free_text_wire_overlaps)) == (1)
        assert (at_minimum.free_text_wire_overlaps[0].overlap_length_mm) == (0.2)
        assert (outside_guard.free_text_wire_overlaps) == (())
