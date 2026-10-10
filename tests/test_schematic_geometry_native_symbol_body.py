"""Focused native symbol body schematic geometry regressions."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from tests.design_lint_fixtures.schematic_geometry_fixtures import (
    enclosed_connector_body_wire_fixture,
    free_text_symbol_body_fixture,
    symbol_body_wire_fixture,
)
from tests.design_lint_fixtures.schematic_geometry_native_support import (
    _native_svg_matching_line,
    _native_svg_matching_rect,
    _native_svg_text_strokes,
    _netlist_components_without_sheetfile,
)
from tests.design_lint_fixtures.schematic_geometry_test_cases import NativeSchematicGeometryHelpers
from tests.design_lint_fixtures.schematic_geometry_text_metrics import (
    calibrated_stroke_text_metrics_fixture,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.schematic_lint,
    pytest.mark.schematic_text_lint,
    pytest.mark.native_kicad,
    pytest.mark.slow,
]


class NativeSchematicGeometrySymbolBodyTests(NativeSchematicGeometryHelpers):
    def test_symbol_body_wire_matches_native_svg_and_erc_control(self) -> None:
        fault_source = symbol_body_wire_fixture()
        control_source = symbol_body_wire_fixture(((71.12, 82.55), (81.28, 82.55)))
        fault, fault_netlist, fault_erc = self.native_scan(
            fault_source,
            source_name="symbol-body-wire.kicad_sch",
            scan_hierarchy=False,
        )
        control, control_netlist, control_erc = self.native_scan(
            control_source,
            source_name="symbol-body-wire.kicad_sch",
            scan_hierarchy=False,
        )
        assert (fault.status) == ("COMPLETE")
        assert (len(fault.wires_through_symbol_bodies)) == (1)
        assert (control.wires_through_symbol_bodies) == (())
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

        fault_signatures = violation_signatures(fault_erc)
        control_signatures = violation_signatures(control_erc)
        assert (len(fault_signatures)) == (6)
        assert (fault_signatures) == (control_signatures)
        fault_svg = self.native_svg(fault_source, source_name="symbol-body-wire-fault.kicad_sch")
        control_svg = self.native_svg(
            control_source, source_name="symbol-body-wire-control.kicad_sch"
        )
        body_rect = _native_svg_matching_rect(fault_svg, 74.93, 73.66, 2.54, 5.08)
        fault_wire = _native_svg_matching_line(fault_svg, (71.12, 76.2), (81.28, 76.2))
        _native_svg_matching_line(control_svg, (71.12, 82.55), (81.28, 82.55))
        assert (body_rect[1]) < (fault_wire[0][1])
        assert (body_rect[1] + body_rect[3]) > (fault_wire[0][1])
        assert (max(point[0] for point in fault_wire)) > (body_rect[0])
        assert (min(point[0] for point in fault_wire)) < (body_rect[0] + body_rect[2])

    def test_valid_peer_connector_contacts_inside_symbol_body_remain_review_candidates(
        self,
    ) -> None:
        enclosed_source = enclosed_connector_body_wire_fixture(body_offset_x=0.0)
        clear_source = enclosed_connector_body_wire_fixture(body_offset_x=2.54)
        enclosed, enclosed_netlist, enclosed_erc = self.native_scan(
            enclosed_source,
            source_name="synthetic-enclosed-connector.kicad_sch",
        )
        clear, clear_netlist, clear_erc = self.native_scan(
            clear_source,
            source_name="synthetic-enclosed-connector.kicad_sch",
        )

        assert (enclosed.status) == ("COMPLETE")
        assert (
            {
                (finding.reference, finding.symbol_library_id)
                for finding in enclosed.wires_through_symbol_bodies
            }
        ) == (
            {
                ("J1", "Connector_Generic:Conn_01x01"),
                ("J2", "Connector_Generic:Conn_01x01"),
            }
        )
        assert (clear.status) == ("COMPLETE")
        assert (clear.wires_through_symbol_bodies) == (())
        assert (_netlist_components_without_sheetfile(enclosed_netlist)) == (
            _netlist_components_without_sheetfile(clear_netlist)
        )
        enclosed_nets = enclosed_netlist.find("./nets")
        clear_nets = clear_netlist.find("./nets")
        assert (enclosed_nets) is not None
        assert (clear_nets) is not None
        assert (ET.tostring(enclosed_nets)) == (ET.tostring(clear_nets))
        signal_nodes = {
            node.attrib["ref"]
            for net in enclosed_netlist.findall("./nets/net")
            if net.attrib.get("name") == "/SIGNAL"
            for node in net.findall("./node")
            if node.attrib.get("ref") in {"J1", "J2"} and node.attrib.get("pin") == "1"
        }
        assert (signal_nodes) == ({"J1", "J2"})

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

        enclosed_erc_signatures = violation_signatures(enclosed_erc)
        clear_erc_signatures = violation_signatures(clear_erc)
        assert (enclosed_erc_signatures) == (clear_erc_signatures)
        assert ({signature[0] for signature in enclosed_erc_signatures}) == (
            {"lib_symbol_issues"}
        ), (
            "standalone native scans lack a project sym-lib-table; no electrical ERC warning is expected"
        )

        enclosed_svg = self.native_svg(
            enclosed_source, source_name="synthetic-enclosed-connector.kicad_sch"
        )
        clear_svg = self.native_svg(
            clear_source, source_name="synthetic-enclosed-connector.kicad_sch"
        )
        enclosed_body = _native_svg_matching_rect(enclosed_svg, 71.12, 71.12, 10.16, 10.16)
        enclosed_second_body = _native_svg_matching_rect(enclosed_svg, 115.57, 71.12, 10.16, 10.16)
        clear_body = _native_svg_matching_rect(clear_svg, 73.66, 71.12, 10.16, 10.16)
        clear_second_body = _native_svg_matching_rect(clear_svg, 118.11, 71.12, 10.16, 10.16)
        enclosed_wire = _native_svg_matching_line(enclosed_svg, (63.5, 76.2), (73.66, 76.2))
        enclosed_second_wire = _native_svg_matching_line(
            enclosed_svg, (109.22, 76.2), (118.11, 76.2)
        )
        clear_wire = _native_svg_matching_line(clear_svg, (63.5, 76.2), (73.66, 76.2))
        clear_second_wire = _native_svg_matching_line(clear_svg, (109.22, 76.2), (118.11, 76.2))
        assert (enclosed_body[0]) < (max(point[0] for point in enclosed_wire))
        assert (enclosed_body[0] + enclosed_body[2]) > (min(point[0] for point in enclosed_wire))
        assert (enclosed_second_body[0]) < (max(point[0] for point in enclosed_second_wire))
        assert (enclosed_second_body[0] + enclosed_second_body[2]) > (
            min(point[0] for point in enclosed_second_wire)
        )
        assert ((enclosed_body[2], enclosed_body[3])) == ((clear_body[2], clear_body[3]))
        assert ((enclosed_second_body[2], enclosed_second_body[3])) == (
            (clear_second_body[2], clear_second_body[3])
        )
        assert round((clear_body[0]) - (max(point[0] for point in clear_wire)), 7) == 0
        assert (
            round((clear_second_body[0]) - (max(point[0] for point in clear_second_wire)), 7) == 0
        )

    def test_unsupported_formatted_text_does_not_reduce_native_wire_body_coverage(self) -> None:
        fault_source = symbol_body_wire_fixture()
        source_with_text = fault_source.replace(
            b"  (sheet_instances",
            b'  (text "UNSUPPORTED~{LINE}" (at 25.4 25.4 0) '
            b"(effects (font (size 1.27 1.27))) "
            b'(uuid "f1000000-0000-4000-8000-000000000009"))\n'
            b"  (sheet_instances",
            1,
        )
        with_text, with_text_netlist, with_text_erc = self.native_scan(
            source_with_text,
            source_name="symbol-body-wire-multiline.kicad_sch",
            scan_hierarchy=False,
        )
        _, baseline_netlist, baseline_erc = self.native_scan(
            fault_source,
            source_name="symbol-body-wire-multiline.kicad_sch",
            scan_hierarchy=False,
        )

        assert (with_text.status) == ("PARTIAL")
        assert (len(with_text.wires_through_symbol_bodies)) == (1)
        assert ("schematic.wire_through_symbol_body") not in (with_text.unsupported_by_rule)
        assert ("schematic.free_text_overlap") in (with_text.unsupported_by_rule)
        assert (ET.tostring(with_text_netlist.find("./nets"))) == (
            ET.tostring(baseline_netlist.find("./nets"))
        )

        def erc_signatures(report: dict[str, object]) -> tuple[tuple[object, ...], ...]:
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

        assert (erc_signatures(with_text_erc)) == (erc_signatures(baseline_erc))

    def test_free_text_symbol_body_overlap_matches_native_svg_and_erc_control(self) -> None:
        fault_source = free_text_symbol_body_fixture()
        control_source = free_text_symbol_body_fixture(point=(88.9, 76.2))
        fault, fault_netlist, fault_erc = self.native_scan(
            fault_source,
            source_name="text-symbol-body.kicad_sch",
            scan_hierarchy=False,
        )
        control, control_netlist, control_erc = self.native_scan(
            control_source,
            source_name="text-symbol-body.kicad_sch",
            scan_hierarchy=False,
        )
        assert (fault.status) == ("COMPLETE")
        assert (len(fault.free_text_symbol_body_overlaps)) == (1)
        assert (control.free_text_symbol_body_overlaps) == (())
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

        fault_signatures = violation_signatures(fault_erc)
        control_signatures = violation_signatures(control_erc)
        assert (len(fault_signatures)) == (3)
        assert (fault_signatures) == (control_signatures)

        fault_svg = self.native_svg(fault_source, source_name="text-symbol-body-fault.kicad_sch")
        control_svg = self.native_svg(
            control_source, source_name="text-symbol-body-control.kicad_sch"
        )
        body = _native_svg_matching_rect(fault_svg, 74.93, 73.66, 2.54, 5.08)
        body_box = (body[0], body[1], body[0] + body[2], body[1] + body[3])
        fault_strokes = _native_svg_text_strokes(fault_svg, "BODY NOTE")
        control_strokes = _native_svg_text_strokes(control_svg, "BODY NOTE")
        fault_points = [point for segment in fault_strokes for point in segment]
        control_points = [point for segment in control_strokes for point in segment]

        def stroke_bounds(
            points: list[tuple[float, float]],
        ) -> tuple[float, float, float, float]:
            return (
                min(point[0] for point in points),
                min(point[1] for point in points),
                max(point[0] for point in points),
                max(point[1] for point in points),
            )

        fault_bounds = stroke_bounds(fault_points)
        control_bounds = stroke_bounds(control_points)
        assert (fault_bounds[0]) < (body_box[2])
        assert (fault_bounds[2]) > (body_box[0])
        assert (fault_bounds[1]) < (body_box[3])
        assert (fault_bounds[3]) > (body_box[1])
        assert (control_bounds[0]) > (body_box[2])
        guarded_body = (
            body_box[0] + 0.15,
            body_box[1] + 0.15,
            body_box[2] - 0.15,
            body_box[3] - 0.15,
        )

        def any_stroke_midpoint_inside(
            strokes: tuple[tuple[tuple[float, float], tuple[float, float]], ...],
        ) -> bool:
            return any(
                guarded_body[0] < (start[0] + end[0]) / 2.0 < guarded_body[2]
                and guarded_body[1] < (start[1] + end[1]) / 2.0 < guarded_body[3]
                for start, end in strokes
            )

        assert any_stroke_midpoint_inside(fault_strokes)
        assert not (any_stroke_midpoint_inside(control_strokes))

    def test_schematic_text_metrics_match_native_svg_for_calibrated_glyphs(self) -> None:
        svg_root = self.native_svg(
            calibrated_stroke_text_metrics_fixture(), source_name="text-metrics.kicad_sch"
        )
        metrics_path = (
            Path(__file__).parents[1] / "kicad_tooling/hwrepo/schematic-text-metrics.json"
        )
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        rendered: dict[str, float] = {}
        for node in svg_root.iter():
            if (
                node.tag.endswith("}text")
                and node.attrib.get("x") == "30.0000"
                and node.attrib.get("y") == "30.3850"
            ):
                character = node.text or ""
                if character in metrics["advances_mm"]:
                    rendered[character] = float(node.attrib["textLength"])
        assert (set(rendered)) == (set(metrics["advances_mm"]))
        for character, advance in metrics["advances_mm"].items():
            measured_width = advance + metrics["single_glyph_svg_end_spacing_mm"]
            assert abs((rendered[character]) - (measured_width)) <= (0.0001)

        top_ratio, bottom_ratio = metrics["vertical_ink_envelope_ratio"]
        expected_ink_envelope = (
            30.0 + top_ratio * metrics["reference_size_mm"] - metrics["stroke_width_mm"] / 2.0,
            30.0 + bottom_ratio * metrics["reference_size_mm"] + metrics["stroke_width_mm"] / 2.0,
        )
        for character in "—µΩ°±×":
            strokes = _native_svg_text_strokes(svg_root, character)
            points = tuple(point for segment in strokes for point in segment)
            assert points
            assert (min(point[1] for point in points)) >= (expected_ink_envelope[0])
            assert (max(point[1] for point in points)) <= (expected_ink_envelope[1])
