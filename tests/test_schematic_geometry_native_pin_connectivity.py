"""Focused native pin connectivity schematic geometry regressions."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.schematic_geometry import (
    MAX_PIN_ENDPOINT_GAP_MM,
    scan_wire_ends_on_pin_lines,
)
from tests.design_lint_fixtures.schematic_geometry_fixtures import (
    CONTROL,
    FAULT,
    LABEL_NEAR_WIRE_ENDPOINT,
    PIN_ON_WIRE_MIDDLE_CONTROL,
    PIN_ON_WIRE_MIDDLE_FAULT,
    TRANSFORM_NEAR_PIN_ENDPOINTS,
    TRANSFORM_PIN_TIPS,
    WIRE_END_NEAR_PIN_TIP_FAULT,
    transformed_near_pin_tip_wire,
)
from tests.design_lint_fixtures.schematic_geometry_test_cases import NativeSchematicGeometryHelpers

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.schematic_lint,
    pytest.mark.schematic_connectivity_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
]


class NativeSchematicGeometryPinConnectivityTests(NativeSchematicGeometryHelpers):
    def test_near_pin_endpoint_transforms_match_native_netlist_and_erc(self) -> None:
        for transform, expected_endpoint in TRANSFORM_NEAR_PIN_ENDPOINTS.items():
            source = transformed_near_pin_tip_wire(*transform)
            scan, netlist, erc = self.native_scan(
                source,
                source_name="transformed-near-pin-tip.kicad_sch",
            )
            assert (scan.status) == ("COMPLETE")
            assert (len(scan.wire_endpoints_near_pin_tips)) == (1)
            finding = scan.wire_endpoints_near_pin_tips[0]
            assert (finding.pin_tip_mm) == (TRANSFORM_PIN_TIPS[transform])
            assert (finding.wire_endpoint_mm) == (expected_endpoint)
            assert (finding.distance_to_pin_tip_mm) == (MAX_PIN_ENDPOINT_GAP_MM)
            open_pins = {
                f"{node.attrib['ref']}.{node.attrib['pin']}"
                for net in netlist.findall("./nets/net")
                if net.attrib.get("name", "").startswith("unconnected-")
                for node in net.findall("node")
            }
            assert ("R1.1") in (open_pins)
            violations = [
                violation
                for sheet in erc.get("sheets", [])
                for violation in sheet.get("violations", [])
            ]
            assert any(
                item.get("type") == "pin_not_connected"
                and any(detail.get("uuid") == finding.pin_uuid for detail in item.get("items", []))
                for item in violations
            )
            assert any(
                item.get("type") == "unconnected_wire_endpoint"
                and any(detail.get("uuid") == finding.wire_uuid for detail in item.get("items", []))
                for item in violations
            )

    def test_near_miss_matches_native_netlist_and_erc_fault_and_control(self) -> None:
        fault, fault_netlist, fault_erc = self.native_scan(FAULT)
        assert (len(fault.findings)) == (1)
        assert ("R1.1") in (
            {
                f"{node.attrib['ref']}.{node.attrib['pin']}"
                for net in fault_netlist.findall("./nets/net")
                if net.attrib.get("name", "").startswith("unconnected-")
                for node in net.findall("node")
            }
        )
        fault_violations = [
            violation
            for sheet in fault_erc.get("sheets", [])
            for violation in sheet.get("violations", [])
        ]
        finding = fault.findings[0]
        assert any(
            item.get("type") == "pin_not_connected"
            and any(detail.get("uuid") == finding.pin_uuid for detail in item.get("items", []))
            for item in fault_violations
        )
        assert any(
            item.get("type") == "unconnected_wire_endpoint"
            and any(detail.get("uuid") == finding.wire_uuid for detail in item.get("items", []))
            for item in fault_violations
        )

        control, control_netlist, control_erc = self.native_scan(CONTROL)
        assert not (control.findings)
        control_open_pins = {
            f"{node.attrib['ref']}.{node.attrib['pin']}"
            for net in control_netlist.findall("./nets/net")
            if net.attrib.get("name", "").startswith("unconnected-")
            for node in net.findall("node")
        }
        assert ("R1.1") not in (control_open_pins)
        control_violations = [
            violation
            for sheet in control_erc.get("sheets", [])
            for violation in sheet.get("violations", [])
        ]
        assert not (
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
        assert (scan.status) == ("COMPLETE")
        assert (scan.findings) == (())
        assert (len(scan.pin_tip_on_wire_interiors)) == (1)
        assert (scan.pin_tip_on_wire_interiors[0].wire_uuid) == (
            "b0000000-0000-4000-8000-000000000005"
        )
        open_pins = {
            f"{node.attrib['ref']}.{node.attrib['pin']}"
            for net in netlist.findall("./nets/net")
            if net.attrib.get("name", "").startswith("unconnected-")
            for node in net.findall("node")
        }
        assert ("R1.1") in (open_pins)
        violations = [
            violation
            for sheet in erc.get("sheets", [])
            for violation in sheet.get("violations", [])
        ]
        assert any(
            item.get("type") == "pin_not_connected"
            and any(
                detail.get("uuid") == "b0000000-0000-4000-8000-000000000003"
                for detail in item.get("items", [])
            )
            for item in violations
        )
        assert any(
            item.get("type") == "unconnected_wire_endpoint"
            and any(
                detail.get("uuid") == "b0000000-0000-4000-8000-000000000005"
                for detail in item.get("items", [])
            )
            for item in violations
        )

    def test_no_connect_marker_on_wire_crossing_preserves_native_pin_isolation(self) -> None:
        source = PIN_ON_WIRE_MIDDLE_FAULT.read_bytes()
        marked_source = source.replace(
            b"  (sheet_instances",
            b'  (no_connect (at 76.2 71.12) (uuid "b0000000-0000-4000-8000-000000000007"))\n'
            b"  (sheet_instances",
            1,
        )
        assert (marked_source) != (source)

        scan, netlist, erc = self.native_scan(
            marked_source,
            source_name="pin-on-wire-middle-no-connect.kicad_sch",
        )
        assert (scan.status) == ("COMPLETE")
        assert not (scan.findings)
        assert (scan.pin_tip_on_wire_interiors) == (())
        forced_unconnected_scan = scan_wire_ends_on_pin_lines(
            marked_source,
            source_path="synthetic/pin-on-wire-middle-no-connect.kicad_sch",
            kicad_version=self.kicad_version,
            unconnected_pins=frozenset({"R1.1"}),
        )
        assert (forced_unconnected_scan.pin_tip_on_wire_interiors) == (())

        assignments = {
            net.attrib.get("name", ""): {
                f"{node.attrib['ref']}.{node.attrib['pin']}" for node in net.findall("node")
            }
            for net in netlist.findall("./nets/net")
        }
        assert ("R1.1") not in (assignments.get("/CONTROL_NET", set()))
        violations = [
            item for sheet in erc.get("sheets", []) for item in sheet.get("violations", [])
        ]
        assert not (
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
        assert (scan.status) == ("COMPLETE")
        assert (scan.findings) == (())
        assert (scan.pin_tip_on_wire_interiors) == (())
        open_pins = {
            f"{node.attrib['ref']}.{node.attrib['pin']}"
            for net in netlist.findall("./nets/net")
            if net.attrib.get("name", "").startswith("unconnected-")
            for node in net.findall("node")
        }
        assert ("R1.1") not in (open_pins)
        nets = {
            net.attrib.get("name"): {
                f"{node.attrib['ref']}.{node.attrib['pin']}" for node in net.findall("node")
            }
            for net in netlist.findall("./nets/net")
        }
        assert ("R1.1") in (nets["/CONTROL_NET"])
        violations = [
            violation
            for sheet in erc.get("sheets", [])
            for violation in sheet.get("violations", [])
        ]
        assert not (
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
        assert (fault.status) == ("COMPLETE")
        assert (len(fault.wire_endpoints_near_pin_tips)) == (1)
        finding = fault.wire_endpoints_near_pin_tips[0]
        assert ((finding.reference, finding.pin_number)) == (("R1", "1"))
        assert (finding.distance_to_pin_tip_mm) == (MAX_PIN_ENDPOINT_GAP_MM)
        open_pins = {
            f"{node.attrib['ref']}.{node.attrib['pin']}"
            for net in fault_netlist.findall("./nets/net")
            if net.attrib.get("name", "").startswith("unconnected-")
            for node in net.findall("node")
        }
        assert ("R1.1") in (open_pins)
        fault_violations = [
            violation
            for sheet in fault_erc.get("sheets", [])
            for violation in sheet.get("violations", [])
        ]
        assert any(
            item.get("type") == "pin_not_connected"
            and any(detail.get("uuid") == finding.pin_uuid for detail in item.get("items", []))
            for item in fault_violations
        )
        assert any(
            item.get("type") == "unconnected_wire_endpoint"
            and any(detail.get("uuid") == finding.wire_uuid for detail in item.get("items", []))
            for item in fault_violations
        )

        control, control_netlist, control_erc = self.native_scan(CONTROL)
        assert (control.wire_endpoints_near_pin_tips) == (())
        connected_nets = {
            net.attrib.get("name", ""): {
                f"{node.attrib['ref']}.{node.attrib['pin']}" for node in net.findall("node")
            }
            for net in control_netlist.findall("./nets/net")
        }
        assert ("R1.1") not in (
            {
                f"{node.attrib['ref']}.{node.attrib['pin']}"
                for net in control_netlist.findall("./nets/net")
                if net.attrib.get("name", "").startswith("unconnected-")
                for node in net.findall("node")
            }
        )
        assert ("R1.1") in (connected_nets["/CONTROL_NET"])
        control_violations = [
            violation
            for sheet in control_erc.get("sheets", [])
            for violation in sheet.get("violations", [])
        ]
        assert not (
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
        assert (fault.status) == ("COMPLETE")
        assert (len(fault.labels_near_wire_endpoints)) == (1)
        finding = fault.labels_near_wire_endpoints[0]
        assert (finding.label_uuid) == ("b0000000-0000-4000-8000-000000000006")
        fault_violations = [
            violation
            for sheet in fault_erc.get("sheets", [])
            for violation in sheet.get("violations", [])
        ]
        assert any(
            item.get("type") == "label_dangling"
            and any(detail.get("uuid") == finding.label_uuid for detail in item.get("items", []))
            for item in fault_violations
        )

        control, _control_netlist, control_erc = self.native_scan(CONTROL)
        assert (control.labels_near_wire_endpoints) == (())
        control_violations = [
            violation
            for sheet in control_erc.get("sheets", [])
            for violation in sheet.get("violations", [])
        ]
        assert not (
            any(
                item.get("type") == "label_dangling"
                and any(
                    detail.get("uuid") == "b0000000-0000-4000-8000-000000000006"
                    for detail in item.get("items", [])
                )
                for item in control_violations
            )
        )
