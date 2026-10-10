"""Focused native wire body schematic geometry regressions."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from tests.design_lint_fixtures.schematic_geometry_fixtures import (
    free_text_wire_fixture,
)
from tests.design_lint_fixtures.schematic_geometry_native_support import (
    _native_svg_matching_line,
    _native_svg_text_strokes,
    _netlist_components_without_sheetfile,
    _segment_distance,
)
from tests.design_lint_fixtures.schematic_geometry_test_cases import NativeSchematicGeometryHelpers

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.schematic_lint,
    pytest.mark.schematic_text_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
]


class NativeSchematicGeometryWireBodyTests(NativeSchematicGeometryHelpers):
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
        assert (fault.status) == ("COMPLETE")
        assert (len(fault.free_text_wire_overlaps)) == (1)
        assert (control.free_text_wire_overlaps) == (())
        assert (_netlist_components_without_sheetfile(fault_netlist)) == (
            _netlist_components_without_sheetfile(control_netlist)
        )
        fault_nets = fault_netlist.find("./nets")
        control_nets = control_netlist.find("./nets")
        assert (fault_nets) is not None
        assert (control_nets) is not None
        assert (ET.tostring(fault_nets)) == (ET.tostring(control_nets))

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

        assert (violation_signatures(fault_erc)) == (violation_signatures(control_erc))
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
        assert abs((fault_gap) - (0.0)) <= (1e-6)
        assert (control_gap) > (7.9)

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

        assert (fault.status) == ("COMPLETE")
        assert (len(fault.free_text_wire_overlaps)) == (1)
        assert (control.status) == ("COMPLETE")
        assert (control.free_text_wire_overlaps) == (())
        assert (_netlist_components_without_sheetfile(fault_netlist)) == (
            _netlist_components_without_sheetfile(control_netlist)
        )
        fault_nets = fault_netlist.find("./nets")
        control_nets = control_netlist.find("./nets")
        assert (fault_nets) is not None
        assert (control_nets) is not None
        assert (ET.tostring(fault_nets)) == (ET.tostring(control_nets))

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

        assert (violation_signatures(fault_erc)) == (violation_signatures(control_erc))
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
        assert abs((fault_gap) - (0.0)) <= (1e-6)
        assert (control_gap) > (5.0)

        text_nodes = [
            node
            for node in fault_svg.iter()
            if node.tag.endswith("}text") and node.text in {"TOP", "WIRE CROSSING FAULT", "BOTTOM"}
        ]
        assert (len(text_nodes)) == (3)
        baselines = sorted(float(node.attrib["y"]) for node in text_nodes)
        metrics_path = (
            Path(__file__).parents[1] / "kicad_tooling/hwrepo/schematic-text-metrics.json"
        )
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        measured_spacing = metrics["multiline_line_spacing_mm"]
        assert abs((baselines[1] - baselines[0]) - (measured_spacing)) <= (0.0001)
        assert abs((baselines[2] - baselines[1]) - (measured_spacing)) <= (0.0001)

        finding = next(
            item
            for item in fault.free_text_wire_overlaps
            if item.text_uuid == "f0000000-0000-4000-8000-000000000001"
        )
        x_values = [coordinate[0] for segment in fault_strokes for coordinate in segment]
        y_values = [coordinate[1] for segment in fault_strokes for coordinate in segment]
        stroke_margin = metrics["stroke_width_mm"] / 2.0
        assert (finding.text_box_mm[0]) <= (min(x_values) - stroke_margin)
        assert (finding.text_box_mm[2]) >= (max(x_values) + stroke_margin)
        assert (finding.text_box_mm[1]) <= (min(y_values) - stroke_margin)
        assert (finding.text_box_mm[3]) >= (max(y_values) + stroke_margin)
