"""Focused native wire topology schematic geometry regressions."""

from __future__ import annotations

import json
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.schematic_geometry import (
    scan_wire_ends_on_pin_lines,
)
from tests.design_lint_fixtures.schematic_geometry_fixtures import (
    DANGLING_WIRE,
    GRAPHICAL_ONLY_CROSSING,
    JUNCTION_MARKED_CROSSING,
    REPEATED_CHANNEL,
    REPEATED_CHANNEL_CONTROL,
    REPEATED_SHEET,
    REPEATED_SHEET_CONTROL,
    T_JUNCTION_CONTROL,
    T_JUNCTION_FAULT,
    TRANSFORM_MIDPOINTS,
    UNMARKED_CROSSING,
    _geometry_candidates,
    _graphical_crossing_baseline,
    transformed_fault,
)
from tests.design_lint_fixtures.schematic_geometry_native_support import (
    _native_svg_matching_line,
    _native_svg_matching_rect,
    _netlist_components_without_sheetfile,
)
from tests.design_lint_fixtures.schematic_geometry_test_cases import NativeSchematicGeometryHelpers

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.schematic_lint,
    pytest.mark.schematic_connectivity_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
]


class NativeSchematicGeometryWireTopologyTests(NativeSchematicGeometryHelpers):
    def test_unmarked_crossing_has_native_wire_diagnostics_and_marked_control_does_not_lint(
        self,
    ) -> None:
        fault, _fault_netlist, fault_erc = self.native_scan(UNMARKED_CROSSING)
        control, _control_netlist, control_erc = self.native_scan(JUNCTION_MARKED_CROSSING)

        assert (fault.status) == ("COMPLETE")
        assert (len(fault.unmarked_wire_crossings)) == (1)
        crossing = fault.unmarked_wire_crossings[0]
        assert (crossing.crossing_mm) == ((127.0, 127.0))
        assert (crossing.wire_uuids) == (
            (
                "c0000000-0000-4000-8000-000000000008",
                "c0000000-0000-4000-8000-000000000009",
            )
        )
        assert (control.status) == ("COMPLETE")
        assert (control.unmarked_wire_crossings) == (())

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
            assert set(crossing.wire_uuids).issubset(native_wire_uuids)

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

        assert (graphical.status) == ("COMPLETE")
        assert (_geometry_candidates(graphical)) == (_geometry_candidates(baseline))
        assert all(not group for group in _geometry_candidates(graphical))
        assert (_netlist_components_without_sheetfile(graphical_netlist)) == (
            _netlist_components_without_sheetfile(baseline_netlist)
        )
        graphical_nets = graphical_netlist.find("./nets")
        baseline_nets = baseline_netlist.find("./nets")
        assert (graphical_nets) is not None
        assert (baseline_nets) is not None
        assert (ET.tostring(graphical_nets)) == (ET.tostring(baseline_nets))

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

        assert (violation_signatures(graphical_erc)) == (violation_signatures(baseline_erc))
        graphical_svg = self.native_svg(graphical_source, source_name=source_name)
        baseline_svg = self.native_svg(baseline_source, source_name=source_name)
        _native_svg_matching_line(graphical_svg, (82.55, 68.58), (82.55, 73.66))
        _native_svg_matching_rect(graphical_svg, 85.09, 69.85, 5.08, 2.54)
        circle_source = (
            b"  (circle (center 95.25 71.12) (radius 1.27)\n"
            b"    (stroke (width 0) (type default)) (fill (type none))\n"
            b'    (uuid "d0000000-0000-4000-8000-000000000003"))\n'
        )
        assert (graphical_source.count(circle_source)) == (1)
        without_circle_svg = self.native_svg(
            graphical_source.replace(circle_source, b"", 1), source_name=source_name
        )
        svg_geometry_tags = {"path", "rect", "circle", "ellipse", "polygon", "line"}

        def svg_geometry_count(root: ET.Element) -> int:
            return sum(
                1 for element in root.iter() if element.tag.rsplit("}", 1)[-1] in svg_geometry_tags
            )

        assert (svg_geometry_count(graphical_svg)) == (svg_geometry_count(baseline_svg) + 3)
        assert (svg_geometry_count(graphical_svg)) > (svg_geometry_count(without_circle_svg))

    def test_unmarked_t_junction_matches_native_netlist_and_erc_control(self) -> None:
        fault, fault_netlist, fault_erc = self.native_scan(T_JUNCTION_FAULT)
        control, control_netlist, control_erc = self.native_scan(T_JUNCTION_CONTROL)

        assert (fault.status) == ("COMPLETE")
        assert (len(fault.unmarked_t_junctions)) == (1)
        finding = fault.unmarked_t_junctions[0]
        assert (finding.junction_mm) == ((88.9, 71.12))
        assert (control.status) == ("COMPLETE")
        assert (control.unmarked_t_junctions) == (())

        def pin_nets(netlist: ET.Element) -> dict[str, str]:
            return {
                f"{node.attrib['ref']}.{node.attrib['pin']}": net.attrib["name"]
                for net in netlist.findall("./nets/net")
                for node in net.findall("node")
            }

        fault_nets = pin_nets(fault_netlist)
        control_nets = pin_nets(control_netlist)
        assert (fault_nets["R1.1"]) == ("/CONTROL_NET")
        assert fault_nets["R1.2"].startswith("unconnected-(")
        assert (control_nets["R1.1"]) == ("/CONTROL_NET")
        assert (control_nets["R1.2"]) == ("/CONTROL_NET")

        def violations(report: dict[str, object]) -> list[dict[str, object]]:
            return [
                item for sheet in report.get("sheets", []) for item in sheet.get("violations", [])
            ]

        fault_violations = violations(fault_erc)
        assert any(
            item.get("type") == "unconnected_wire_endpoint"
            and any(
                detail.get("uuid") == finding.endpoint_wire_uuid for detail in item.get("items", [])
            )
            for item in fault_violations
        )
        assert any(
            item.get("type") == "pin_not_connected"
            and any(
                detail.get("uuid") == "b0000000-0000-4000-8000-000000000004"
                for detail in item.get("items", [])
            )
            for item in fault_violations
        )
        control_violations = violations(control_erc)
        assert not (
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

        assert (scan.status) == ("COMPLETE")
        assert (len(scan.unmarked_t_junctions)) == (2)
        assert (len(scan.source_bindings)) == (3)
        assert (
            [component.attrib["ref"] for component in netlist.findall("./components/comp")]
        ) == (["R1", "R2"])
        net_assignments = {
            (node.attrib["ref"], node.attrib["pin"]): net.attrib["name"]
            for net in netlist.findall("./nets/net")
            for node in net.findall("node")
        }
        assert (net_assignments[("R1", "1")]) == ("/InstanceA/CONTROL_NET")
        assert (net_assignments[("R2", "1")]) == ("/InstanceB/CONTROL_NET")
        assert (
            {pin for pin, net in net_assignments.items() if net.startswith("unconnected-")}
        ) == ({("R1", "2"), ("R2", "2")})

        pin_uuids = {
            detail["uuid"]
            for sheet in erc.get("sheets", [])
            for violation in sheet.get("violations", [])
            if violation.get("type") == "pin_not_connected"
            for detail in violation.get("items", [])
        }
        assert (pin_uuids) == ({"b0000000-0000-4000-8000-000000000004"})

        control_scan, control_netlist, control_erc = self.native_scan(
            REPEATED_SHEET_CONTROL,
            related_sources=(REPEATED_CHANNEL_CONTROL,),
            scan_hierarchy=True,
        )
        assert (control_scan.status) == ("COMPLETE")
        assert (control_scan.unmarked_t_junctions) == (())
        control_assignments = {
            (node.attrib["ref"], node.attrib["pin"]): net.attrib["name"]
            for net in control_netlist.findall("./nets/net")
            for node in net.findall("node")
        }
        assert (control_assignments[("R1", "2")]) == ("/InstanceA/CONTROL_NET")
        assert (control_assignments[("R2", "2")]) == ("/InstanceB/CONTROL_NET")
        control_pin_violations = [
            violation
            for sheet in control_erc.get("sheets", [])
            for violation in sheet.get("violations", [])
            if violation.get("type") == "pin_not_connected"
        ]
        assert (control_pin_violations) == ([])

    def test_free_dangling_wire_is_already_localized_by_native_erc(self) -> None:
        scan, _netlist, erc = self.native_scan(DANGLING_WIRE)

        assert (scan.status) == ("COMPLETE")
        assert (scan.findings) == (())
        assert (scan.pin_tip_on_wire_interiors) == (())
        assert (scan.wire_endpoints_near_pin_tips) == (())
        assert (scan.labels_near_wire_endpoints) == (())
        assert (scan.unmarked_wire_crossings) == (())
        assert (scan.unmarked_t_junctions) == (())

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
        assert any(item.get("type") == "wire_dangling" for item in native_wire_findings)
        assert any(item.get("type") == "unconnected_wire_endpoint" for item in native_wire_findings)

    def test_all_supported_symbol_transforms_match_native_open_pin_netlists(self) -> None:
        for (angle, mirror), endpoint in TRANSFORM_MIDPOINTS.items():
            source = transformed_fault(angle, mirror, endpoint)
            with tempfile.TemporaryDirectory(prefix="schematic-geometry-transform-") as directory:
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
                assert (result.returncode) == (0), result.stderr or result.stdout
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
                assert (erc_result.returncode) == (0), erc_result.stderr or erc_result.stdout
                root_xml = ET.parse(netlist).getroot()
                open_pins = {
                    f"{node.attrib['ref']}.{node.attrib['pin']}"
                    for net in root_xml.findall("./nets/net")
                    if net.attrib.get("name", "").startswith("unconnected-")
                    for node in net.findall("node")
                }
                assert ("R1.1") in (open_pins)
                scan = scan_wire_ends_on_pin_lines(
                    source,
                    source_path=schematic.name,
                    kicad_version=self.kicad_version,
                    unconnected_pins=frozenset(open_pins),
                )
                assert (len(scan.findings)) == (1)
                assert (scan.findings[0].wire_endpoint_mm) == (endpoint)
                pin_uuid = scan.findings[0].pin_uuid
                assert (pin_uuid) is not None
                erc = json.loads(erc_path.read_text(encoding="utf-8"))
                native_pin_positions = [
                    detail["pos"]
                    for sheet in erc.get("sheets", [])
                    for violation in sheet.get("violations", [])
                    if violation.get("type") == "pin_not_connected"
                    for detail in violation.get("items", [])
                    if detail.get("uuid") == pin_uuid
                ]
                assert (len(native_pin_positions)) == (1)
                assert (
                    round(
                        (native_pin_positions[0]["x"] * 100) - (scan.findings[0].pin_tip_mm[0]), 6
                    )
                    == 0
                )
                assert (
                    round(
                        (native_pin_positions[0]["y"] * 100) - (scan.findings[0].pin_tip_mm[1]), 6
                    )
                    == 0
                )
