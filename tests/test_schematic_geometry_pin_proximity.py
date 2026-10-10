"""Focused pin proximity schematic geometry regressions."""

from __future__ import annotations

import hashlib

import pytest

from kicad_tooling.hwrepo.schematic_geometry import (
    MAX_PIN_ENDPOINT_GAP_MM,
)
from tests.design_lint_fixtures.schematic_geometry_fixtures import (
    CONTROL,
    FAULT,
    PIN_ON_WIRE_MIDDLE_CONTROL,
    PIN_ON_WIRE_MIDDLE_FAULT,
    TRANSFORM_NEAR_PIN_ENDPOINTS,
    TRANSFORM_PIN_TIPS,
    WIRE_END_NEAR_PIN_TIP_FAULT,
    transformed_near_pin_tip_wire,
    transformed_pin_tip_wire,
)
from tests.design_lint_fixtures.schematic_geometry_test_cases import SchematicGeometryHelpers

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.schematic_lint,
    pytest.mark.schematic_connectivity_lint,
]


class SchematicGeometryPinProximityTests(SchematicGeometryHelpers):
    def test_fault_is_localized_to_the_native_unconnected_pin(self) -> None:
        source = FAULT.read_bytes()
        result = self.scan(source)

        assert (result.status) == ("COMPLETE")
        assert (result.source_sha256) == (hashlib.sha256(source).hexdigest())
        assert (len(result.findings)) == (1)
        finding = result.findings[0]
        assert ((finding.reference, finding.pin_number)) == (("R1", "1"))
        assert (finding.pin_tip_mm) == ((76.2, 71.12))
        assert (finding.wire_endpoint_mm) == ((76.2, 72.39))
        assert (finding.distance_to_pin_tip_mm) == (1.27)
        assert (finding.distance_along_pin_mm) == (1.27)

    def test_connected_control_and_non_native_open_pin_are_excluded(self) -> None:
        control = self.scan(CONTROL.read_bytes(), unconnected_pins=frozenset({"R1.2"}))
        assert (control.findings) == (())

        not_open = self.scan(FAULT.read_bytes(), unconnected_pins=frozenset({"R1.2"}))
        assert (not_open.findings) == (())

    def test_pin_on_wire_middle_without_junction_is_localized(self) -> None:
        result = self.scan(
            PIN_ON_WIRE_MIDDLE_FAULT.read_bytes(),
        )
        assert (result.status) == ("COMPLETE")
        assert (result.findings) == (())
        assert (len(result.pin_tip_on_wire_interiors)) == (1)
        finding = result.pin_tip_on_wire_interiors[0]
        assert ((finding.reference, finding.pin_number)) == (("R1", "1"))
        assert (finding.pin_tip_mm) == ((76.2, 71.12))
        assert (finding.wire_segment_start_mm) == ((50.8, 71.12))
        assert (finding.wire_segment_end_mm) == ((101.6, 71.12))

    def test_wire_endpoint_just_short_of_pin_tip_is_localized(self) -> None:
        source = WIRE_END_NEAR_PIN_TIP_FAULT.read_bytes()
        result = self.scan(source)
        assert (result.status) == ("COMPLETE")
        assert (result.findings) == (())
        assert (result.pin_tip_on_wire_interiors) == (())
        assert (len(result.wire_endpoints_near_pin_tips)) == (1)
        finding = result.wire_endpoints_near_pin_tips[0]
        assert ((finding.reference, finding.pin_number)) == (("R1", "1"))
        assert (finding.pin_tip_mm) == ((76.2, 71.12))
        assert (finding.wire_endpoint_mm) == ((76.2, 70.62))
        assert (finding.distance_to_pin_tip_mm) == (MAX_PIN_ENDPOINT_GAP_MM)

    def test_wire_endpoint_gap_boundary_and_controls(self) -> None:
        fixture = WIRE_END_NEAR_PIN_TIP_FAULT.read_bytes()
        assert (len(self.scan(fixture).wire_endpoints_near_pin_tips)) == (1)

        outside = fixture.replace(b"76.2 70.62", b"76.2 70.619", 1)
        outside = outside.replace(b"101.6 70.62", b"101.6 70.619", 1)
        assert (self.scan(outside).wire_endpoints_near_pin_tips) == (())

        on_pin_segment = fixture.replace(b"76.2 70.62", b"76.2 71.42", 1)
        assert (self.scan(on_pin_segment).wire_endpoints_near_pin_tips) == (())
        assert (len(self.scan(on_pin_segment).findings)) == (1)

        connected = self.scan(CONTROL.read_bytes(), unconnected_pins=frozenset())
        assert (connected.wire_endpoints_near_pin_tips) == (())

        non_native_open_pin = self.scan(fixture, unconnected_pins=frozenset({"R1.2"}))
        assert (non_native_open_pin.wire_endpoints_near_pin_tips) == (())

    def test_wire_endpoint_near_pin_tip_tracks_all_supported_symbol_transforms(self) -> None:
        semantic_finding: tuple[str, str, float] | None = None
        source_hashes: set[str] = set()
        for transform, expected_endpoint in TRANSFORM_NEAR_PIN_ENDPOINTS.items():
            source = transformed_near_pin_tip_wire(*transform)
            result = self.scan(source)
            assert (result.status) == ("COMPLETE")
            assert (result.findings) == (())
            assert (result.pin_tip_on_wire_interiors) == (())
            assert (len(result.wire_endpoints_near_pin_tips)) == (1)
            finding = result.wire_endpoints_near_pin_tips[0]
            observed_semantics = (
                finding.reference,
                finding.pin_number,
                finding.distance_to_pin_tip_mm,
            )
            if semantic_finding is None:
                semantic_finding = observed_semantics
            assert (observed_semantics) == (semantic_finding)
            assert (result.source_sha256) == (hashlib.sha256(source).hexdigest())
            source_hashes.add(result.source_sha256)
            assert (finding.pin_tip_mm) == (TRANSFORM_PIN_TIPS[transform])
            assert (finding.wire_endpoint_mm) == (expected_endpoint)
            assert (finding.distance_to_pin_tip_mm) == (MAX_PIN_ENDPOINT_GAP_MM)
        assert (len(source_hashes)) > (1)

        baseline = transformed_near_pin_tip_wire(0, None)
        outside = baseline.replace(b"(xy 76.2 70.62)", b"(xy 76.2 70.619)", 1)
        outside = outside.replace(b"(xy 101.6 70.62)", b"(xy 101.6 70.619)", 1)
        outside = outside.replace(
            b'(label "FAULT_NET" (at 101.6 70.62 0)',
            b'(label "FAULT_NET" (at 101.6 70.619 0)',
            1,
        )
        repaired = self.scan(outside)
        assert (repaired.status) == ("COMPLETE")
        assert (repaired.wire_endpoints_near_pin_tips) == (())

    def test_no_connect_marker_excludes_wire_endpoint_near_pin_tip(self) -> None:
        source = WIRE_END_NEAR_PIN_TIP_FAULT.read_bytes().replace(
            b"  (wire (pts",
            b'  (no_connect (at 76.2 71.12) (uuid "c0000000-0000-4000-8000-000000000007"))\n'
            b"  (wire (pts",
            1,
        )
        assert (self.scan(source).wire_endpoints_near_pin_tips) == (())

    def test_junction_control_is_excluded_when_native_netlist_marks_pin_connected(self) -> None:
        result = self.scan(
            PIN_ON_WIRE_MIDDLE_CONTROL.read_bytes(),
            unconnected_pins=frozenset(),
        )
        assert (result.status) == ("COMPLETE")
        assert (result.findings) == (())
        assert (result.pin_tip_on_wire_interiors) == (())

    def test_no_connect_marker_excludes_pin_tip_on_wire_interior(self) -> None:
        source = PIN_ON_WIRE_MIDDLE_FAULT.read_bytes().replace(
            b"  (sheet_instances",
            b'  (no_connect (at 76.2 71.12) (uuid "e0000000-0000-4000-8000-000000000009"))\n'
            b"  (sheet_instances",
            1,
        )
        result = self.scan(source)
        assert (result.findings) == (())
        assert (result.pin_tip_on_wire_interiors) == (())

    def test_pin_tip_on_wire_interior_tracks_all_supported_symbol_transforms(self) -> None:
        semantic_finding: tuple[str, str, str, str, float, str] | None = None
        source_hashes: set[str] = set()
        for transform, pin_tip in TRANSFORM_PIN_TIPS.items():
            source = transformed_pin_tip_wire(*transform, pin_tip)
            result = self.scan(source)
            assert (result.status) == ("COMPLETE")
            assert (result.findings) == (())
            assert (len(result.pin_tip_on_wire_interiors)) == (1)
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
            assert (observed_semantics) == (semantic_finding)
            assert (result.source_sha256) == (hashlib.sha256(source).hexdigest())
            source_hashes.add(result.source_sha256)
            assert (finding.pin_tip_mm) == (pin_tip)
            assert (finding.wire_segment_start_mm) == ((round(pin_tip[0] - 25.4, 6), pin_tip[1]))
            assert (finding.wire_segment_end_mm) == ((round(pin_tip[0] + 25.4, 6), pin_tip[1]))

            # Segment direction is incidental: reversing its endpoints must
            # preserve the same pin-to-wire observation.
            start_x = round(pin_tip[0] - 25.4, 6)
            end_x = round(pin_tip[0] + 25.4, 6)
            y = round(pin_tip[1], 6)
            forward = f"(xy {start_x} {y}) (xy {end_x} {y})".encode()
            reverse = f"(xy {end_x} {y}) (xy {start_x} {y})".encode()
            assert (source.count(forward)) == (1)
            reversed_source = source.replace(forward, reverse, 1)
            reversed_result = self.scan(reversed_source)
            assert (reversed_result.status) == ("COMPLETE")
            assert (
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
                )
            ) == ((semantic_finding,))

            # A small causal offset removes the geometric contact while
            # leaving the pin's native unconnected state unchanged.
            offset_y = round(y + 0.01, 6)
            moved = source.replace(
                forward,
                f"(xy {start_x} {offset_y}) (xy {end_x} {offset_y})".encode(),
                1,
            )
            assert (moved) != (source)
            repaired = self.scan(moved)
            assert (repaired.status) == ("COMPLETE")
            assert (repaired.pin_tip_on_wire_interiors) == (())

        assert (semantic_finding) is not None
        assert (len(source_hashes)) > (1)
