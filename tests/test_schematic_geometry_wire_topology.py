"""Focused wire topology schematic geometry regressions."""

from __future__ import annotations

import hashlib
import re

import pytest

from kicad_tooling.hwrepo.schematic_geometry import (
    SchematicGeometryScan,
)
from tests.design_lint_fixtures.schematic_geometry_fixtures import (
    CONTROL,
    GRAPHICAL_ONLY_CROSSING,
    JUNCTION_MARKED_CROSSING,
    LABEL_NEAR_WIRE_ENDPOINT,
    T_JUNCTION_CONTROL,
    T_JUNCTION_FAULT,
    UNMARKED_CROSSING,
    _geometry_candidates,
    _graphical_crossing_baseline,
)
from tests.design_lint_fixtures.schematic_geometry_test_cases import SchematicGeometryHelpers

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.schematic_lint,
    pytest.mark.schematic_connectivity_lint,
]


class SchematicGeometryWireTopologyTests(SchematicGeometryHelpers):
    def test_label_near_wire_endpoint_is_localized(self) -> None:
        source = LABEL_NEAR_WIRE_ENDPOINT.read_bytes()
        result = self.scan(source, unconnected_pins=frozenset())

        assert (result.status) == ("COMPLETE")
        assert (result.source_sha256) == (hashlib.sha256(source).hexdigest())
        assert (len(result.labels_near_wire_endpoints)) == (1)
        finding = result.labels_near_wire_endpoints[0]
        assert (finding.label_kind) == ("label")
        assert (finding.text) == ("CONTROL_NET")
        assert (finding.label_uuid) == ("b0000000-0000-4000-8000-000000000006")
        assert (finding.anchor_mm) == ((102.1, 71.12))
        assert (len(finding.candidates)) == (1)
        assert (finding.candidates[0].wire_uuid) == ("b0000000-0000-4000-8000-000000000005")
        assert (finding.candidates[0].wire_endpoint_mm) == ((101.6, 71.12))
        assert (finding.candidates[0].distance_mm) == (0.5)

    def test_label_near_endpoint_is_translation_invariant_and_attachment_clears_candidate(
        self,
    ) -> None:
        source = LABEL_NEAR_WIRE_ENDPOINT.read_bytes()
        baseline = self.scan(source, unconnected_pins=frozenset())
        assert (len(baseline.labels_near_wire_endpoints)) == (1)

        wire_points = b"(xy 76.2 71.12) (xy 101.6 71.12)"
        translated_wire_points = b"(xy 126.2 121.12) (xy 151.6 121.12)"
        label_anchor = b'(label "CONTROL_NET" (at 102.1 71.12 0)'
        translated_anchor = b'(label "CONTROL_NET" (at 152.1 121.12 0)'
        assert (source.count(wire_points)) == (1)
        assert (source.count(label_anchor)) == (1)
        translated_source = source.replace(wire_points, translated_wire_points, 1).replace(
            label_anchor,
            translated_anchor,
            1,
        )
        translated = self.scan(translated_source, unconnected_pins=frozenset())
        assert (translated.status) == ("COMPLETE")
        assert (len(translated.labels_near_wire_endpoints)) == (1)
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
        assert (translated_semantics) == (baseline_semantics)
        assert (translated_finding.anchor_mm) == ((152.1, 121.12))
        assert (translated_finding.candidates[0].wire_endpoint_mm) == ((151.6, 121.12))
        assert (translated.source_sha256) == (hashlib.sha256(translated_source).hexdigest())
        assert (translated.source_sha256) != (baseline.source_sha256)

        attached_source = translated_source.replace(
            translated_anchor,
            b'(label "CONTROL_NET" (at 151.6 121.12 0)',
            1,
        )
        attached = self.scan(attached_source, unconnected_pins=frozenset())
        assert (attached.status) == ("COMPLETE")
        assert (attached.labels_near_wire_endpoints) == (())

    def test_unmarked_orthogonal_wire_interiors_are_review_candidates(self) -> None:
        source = UNMARKED_CROSSING.read_bytes()
        result = self.scan(source, unconnected_pins=frozenset())

        assert (result.status) == ("COMPLETE")
        assert (result.source_sha256) == (hashlib.sha256(source).hexdigest())
        assert (len(result.unmarked_wire_crossings)) == (1)
        finding = result.unmarked_wire_crossings[0]
        assert (finding.crossing_mm) == ((127.0, 127.0))
        assert (finding.wire_uuids) == (
            (
                "c0000000-0000-4000-8000-000000000008",
                "c0000000-0000-4000-8000-000000000009",
            )
        )

    def test_unmarked_crossing_is_stable_under_wire_order_and_marker_repairs_it(self) -> None:
        source = UNMARKED_CROSSING.read_bytes()
        wire_blocks = {
            match.group(1).decode("ascii"): match
            for match in re.finditer(rb'(?ms)^  \(wire\b.*?^    \(uuid "([^"]+)"\)\)', source)
        }
        horizontal = wire_blocks["c0000000-0000-4000-8000-000000000008"]
        vertical = wire_blocks["c0000000-0000-4000-8000-000000000009"]
        assert (horizontal.start()) < (vertical.start())
        reordered_source = (
            source[: horizontal.start()]
            + vertical.group(0)
            + source[horizontal.end() : vertical.start()]
            + horizontal.group(0)
            + source[vertical.end() :]
        )

        original = self.scan(source, unconnected_pins=frozenset())
        reordered = self.scan(reordered_source, unconnected_pins=frozenset())
        assert (original.source_sha256) != (reordered.source_sha256)
        assert (original.unmarked_wire_crossings) == (reordered.unmarked_wire_crossings)
        assert (len(reordered.unmarked_wire_crossings)) == (1)

        sheet_instances = b"  (sheet_instances"
        assert (source.count(sheet_instances)) == (1)
        junction = (
            b"  (junction (at 127 127) (diameter 0) (color 0 0 0 0)\n"
            b'    (uuid "c0000000-0000-4000-8000-000000000010"))\n'
        )
        repaired_source = source.replace(sheet_instances, junction + sheet_instances, 1)
        repaired = self.scan(repaired_source, unconnected_pins=frozenset())
        assert (repaired.status) == ("COMPLETE")
        assert (repaired.unmarked_wire_crossings) == (())

    def test_explicit_junction_and_endpoint_touch_are_excluded(self) -> None:
        marked = self.scan(JUNCTION_MARKED_CROSSING.read_bytes(), unconnected_pins=frozenset())
        assert (marked.status) == ("COMPLETE")
        assert (marked.unmarked_wire_crossings) == (())

        endpoint_touch = UNMARKED_CROSSING.read_bytes().replace(
            b"(xy 114.3 127)", b"(xy 127 127)", 1
        )
        touched = self.scan(endpoint_touch, unconnected_pins=frozenset())
        assert (touched.unmarked_wire_crossings) == (())

    def test_graphical_polyline_crossing_a_wire_is_not_an_electrical_candidate(self) -> None:
        source = GRAPHICAL_ONLY_CROSSING.read_bytes()
        baseline_source = _graphical_crossing_baseline()
        result = self.scan(source, unconnected_pins=frozenset())
        baseline = self.scan(baseline_source, unconnected_pins=frozenset())

        assert (source.count(b"(polyline ")) == (1)
        assert (source.count(b"(rectangle (start 85.09 69.85)")) == (1)
        assert (source.count(b"(circle (center 95.25 71.12)")) == (1)
        assert (result.status) == ("COMPLETE")
        assert (result.unsupported_by_rule) == ({})
        assert (_geometry_candidates(result)) == (_geometry_candidates(baseline))

    def test_unmarked_t_junction_is_review_candidate(self) -> None:
        result = self.scan(T_JUNCTION_FAULT.read_bytes(), unconnected_pins=frozenset({"R1.2"}))

        assert (result.status) == ("COMPLETE")
        assert (len(result.unmarked_t_junctions)) == (1)
        finding = result.unmarked_t_junctions[0]
        assert (finding.endpoint_wire_uuid) == ("c0000000-0000-4000-8000-000000000012")
        assert (finding.interior_wire_uuid) == ("b0000000-0000-4000-8000-000000000005")
        assert (finding.junction_mm) == ((88.9, 71.12))

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
        assert (fault.status) == ("COMPLETE")
        assert (len(fault.unmarked_t_junctions)) == (1)
        assert (fault.source_sha256) == (hashlib.sha256(source).hexdigest())
        expected = semantic_findings(fault)

        wire_records = re.findall(rb"(?m)^  \(wire .*\n", source)
        assert (len(wire_records)) == (3)
        t_wire_records = wire_records[-2:]
        reordered_source = source
        for record in t_wire_records:
            assert (reordered_source.count(record)) == (1)
            reordered_source = reordered_source.replace(record, b"", 1)
        reordered_source = reordered_source.replace(
            b"  (sheet_instances",
            b"".join(reversed(t_wire_records)) + b"  (sheet_instances",
            1,
        )
        reordered = self.scan(reordered_source, unconnected_pins=frozenset({"R1.2"}))
        assert (reordered.status) == ("COMPLETE")
        assert (semantic_findings(reordered)) == (expected)
        assert (reordered.source_sha256) != (fault.source_sha256)

        marker = (
            b"  (junction (at 88.9 71.12) (diameter 0) (color 0 0 0 0)\n"
            b'    (uuid "c0000000-0000-4000-8000-000000000099"))\n'
        )
        marked_source = source.replace(b"  (sheet_instances", marker + b"  (sheet_instances", 1)
        marked = self.scan(marked_source, unconnected_pins=frozenset({"R1.2"}))
        assert (marked.status) == ("COMPLETE")
        assert (marked.unmarked_t_junctions) == (())

    def test_explicit_t_junction_marker_is_excluded(self) -> None:
        result = self.scan(T_JUNCTION_CONTROL.read_bytes(), unconnected_pins=frozenset())

        assert (result.status) == ("COMPLETE")
        assert (result.unmarked_t_junctions) == (())

    def test_t_junction_tolerance_and_segment_endpoint_boundary(self) -> None:
        source = T_JUNCTION_FAULT.read_bytes()
        within_tolerance = source.replace(
            b"(xy 88.9 71.12) (xy 88.9 81.28)",
            b"(xy 88.9 71.121) (xy 88.9 81.28)",
            1,
        )
        near = self.scan(within_tolerance, unconnected_pins=frozenset({"R1.2"}))
        assert (len(near.unmarked_t_junctions)) == (1)
        assert (near.unmarked_t_junctions[0].junction_mm) == ((88.9, 71.121))

        outside_tolerance = source.replace(
            b"(xy 88.9 71.12) (xy 88.9 81.28)",
            b"(xy 88.9 71.122) (xy 88.9 81.28)",
            1,
        )
        far = self.scan(outside_tolerance, unconnected_pins=frozenset({"R1.2"}))
        assert (far.unmarked_t_junctions) == (())

        endpoint_contact = source.replace(
            b"(xy 88.9 71.12) (xy 88.9 81.28)",
            b"(xy 76.2 71.12) (xy 76.2 81.28)",
            1,
        )
        endpoint = self.scan(endpoint_contact, unconnected_pins=frozenset({"R1.2"}))
        assert (endpoint.unmarked_t_junctions) == (())

    def test_attached_interior_and_far_labels_are_excluded(self) -> None:
        attached = self.scan(CONTROL.read_bytes(), unconnected_pins=frozenset())
        assert (attached.labels_near_wire_endpoints) == (())

        fixture = LABEL_NEAR_WIRE_ENDPOINT.read_bytes()
        on_wire_interior = fixture.replace(b"(at 102.1 71.12 0)", b"(at 90 71.12 0)", 1)
        assert (
            self.scan(on_wire_interior, unconnected_pins=frozenset()).labels_near_wire_endpoints
        ) == (())

        on_pin_tip = fixture.replace(b"(at 102.1 71.12 0)", b"(at 76.2 71.12 0)", 1)
        assert (self.scan(on_pin_tip, unconnected_pins=frozenset()).labels_near_wire_endpoints) == (
            ()
        )

        far_from_wire = fixture.replace(b"(at 102.1 71.12 0)", b"(at 103.21 71.12 0)", 1)
        assert (
            self.scan(far_from_wire, unconnected_pins=frozenset()).labels_near_wire_endpoints
        ) == (())

    def test_label_endpoint_search_radius_includes_boundary_only(self) -> None:
        control = CONTROL.read_bytes()
        at_boundary = control.replace(b"(at 101.6 71.12 0)", b"(at 102.87 71.12 0)", 1)
        boundary_result = self.scan(at_boundary, unconnected_pins=frozenset())
        assert (len(boundary_result.labels_near_wire_endpoints)) == (1)
        candidate = boundary_result.labels_near_wire_endpoints[0].candidates[0]
        assert (candidate.distance_mm) == (1.27)

        outside_boundary = control.replace(b"(at 101.6 71.12 0)", b"(at 102.871 71.12 0)", 1)
        assert (
            self.scan(outside_boundary, unconnected_pins=frozenset()).labels_near_wire_endpoints
        ) == (())
