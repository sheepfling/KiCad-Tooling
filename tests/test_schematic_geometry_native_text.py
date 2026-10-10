"""Focused native text schematic geometry regressions."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from tests.design_lint_fixtures.schematic_geometry_fixtures import (
    free_text_anchor_fixture,
    free_text_objects_fixture,
    justify_first_free_text,
)
from tests.design_lint_fixtures.schematic_geometry_native_support import (
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


class NativeSchematicGeometryTextTests(NativeSchematicGeometryHelpers):
    def test_coincident_text_anchor_fixture_adds_no_native_erc_diagnostic(self) -> None:
        separated, _separated_netlist, separated_erc = self.native_scan(
            free_text_anchor_fixture((25.4, 25.4), (50.8, 25.4))
        )
        coincident, _coincident_netlist, coincident_erc = self.native_scan(
            free_text_anchor_fixture((25.4, 25.4), (25.4, 25.4))
        )
        assert (separated.coincident_text_anchors) == (())
        assert (len(coincident.coincident_text_anchors)) == (1)

        def violations(report: dict[str, object]) -> list[dict[str, object]]:
            return [
                item for sheet in report.get("sheets", []) for item in sheet.get("violations", [])
            ]

        assert (violations(coincident_erc)) == (violations(separated_erc))

    def test_free_text_overlap_matches_native_svg_and_erc_control(self) -> None:
        fault_text = "10µF ±5V"
        second_text = "4.7Ω"
        fault_source = free_text_objects_fixture(
            fault_text, (25.4, 25.4), second_text, (29.0, 25.4)
        )
        control_source = free_text_objects_fixture(
            fault_text, (25.4, 25.4), second_text, (50.8, 25.4)
        )
        fault, fault_netlist, fault_erc = self.native_scan(
            fault_source, source_name="text-overlap.kicad_sch", scan_hierarchy=False
        )
        control, control_netlist, control_erc = self.native_scan(
            control_source, source_name="text-overlap.kicad_sch", scan_hierarchy=False
        )
        assert (fault.status) == ("COMPLETE")
        assert (len(fault.free_text_overlaps)) == (1)
        assert (control.free_text_overlaps) == (())
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
        fault_svg = self.native_svg(fault_source, source_name="fault-text-overlap.kicad_sch")
        control_svg = self.native_svg(control_source, source_name="control-text-overlap.kicad_sch")
        fault_alpha = _native_svg_text_strokes(fault_svg, fault_text)
        fault_beta = _native_svg_text_strokes(fault_svg, second_text)
        control_alpha = _native_svg_text_strokes(control_svg, fault_text)
        control_beta = _native_svg_text_strokes(control_svg, second_text)
        fault_gap = min(
            _segment_distance(*first, *second) for first in fault_alpha for second in fault_beta
        )
        control_gap = min(
            _segment_distance(*first, *second) for first in control_alpha for second in control_beta
        )
        assert (fault_gap) <= (0.1524)
        assert (control_gap) > (0.1524)

        metrics_path = (
            Path(__file__).parents[1] / "kicad_tooling/hwrepo/schematic-text-metrics.json"
        )
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        for svg_root, expected_text in (
            (fault_svg, fault_text),
            (fault_svg, second_text),
        ):
            text_nodes = [
                node
                for node in svg_root.iter()
                if node.tag.endswith("}text") and node.text == expected_text
            ]
            assert (len(text_nodes)) == (1)
            expected_width = sum(metrics["advances_mm"][char] for char in expected_text)
            expected_width += metrics["line_end_spacing_mm"]
            assert abs((float(text_nodes[0].attrib["textLength"])) - (expected_width)) <= (0.01)

    def test_horizontal_justification_matches_native_svg_and_erc_control(self) -> None:
        for justification, second_x in (("left", 54.0), ("right", 46.0)):
            fault_source = justify_first_free_text(
                free_text_objects_fixture("FIRST", (50.0, 50.0), "SECOND", (second_x, 50.0)),
                justification,
            )
            control_source = justify_first_free_text(
                free_text_objects_fixture("FIRST", (50.0, 50.0), "SECOND", (90.0, 50.0)),
                justification,
            )
            fault, fault_netlist, fault_erc = self.native_scan(
                fault_source,
                source_name="justified-text-fault.kicad_sch",
                scan_hierarchy=False,
            )
            control, control_netlist, control_erc = self.native_scan(
                control_source,
                source_name="justified-text-control.kicad_sch",
                scan_hierarchy=False,
            )

            assert (fault.status) == ("COMPLETE")
            assert (len(fault.free_text_overlaps)) == (1)
            assert (control.status) == ("COMPLETE")
            assert (control.free_text_overlaps) == (())
            assert (_netlist_components_without_sheetfile(fault_netlist)) == (
                _netlist_components_without_sheetfile(control_netlist)
            )
            assert (ET.tostring(fault_netlist.find("./nets"))) == (
                ET.tostring(control_netlist.find("./nets"))
            )

            def erc_signatures(report: dict[str, object]) -> tuple[tuple[object, ...], ...]:
                violations = [
                    item
                    for sheet in report.get("sheets", [])
                    for item in sheet.get("violations", [])
                ]
                return tuple(
                    sorted(
                        (
                            item["type"],
                            item["severity"],
                            tuple(entry.get("uuid") for entry in item["items"]),
                        )
                        for item in violations
                    )
                )

            assert (erc_signatures(fault_erc)) == (erc_signatures(control_erc))
            first_box = fault.free_text_overlaps[0].first_box_mm
            svg_root = self.native_svg(fault_source, source_name="justified-text-fault.kicad_sch")
            strokes = _native_svg_text_strokes(svg_root, "FIRST")
            stroke_x = tuple(point[0] for segment in strokes for point in segment)
            assert (min(stroke_x)) >= (first_box[0] - 0.01)
            assert (max(stroke_x)) <= (first_box[2] + 0.01)

    def test_empty_justification_matches_native_default_centering(self) -> None:
        default_source = free_text_objects_fixture("FIRST", (50.0, 50.0), "SECOND", (54.0, 50.0))
        empty_source = justify_first_free_text(default_source, "")
        default, default_netlist, default_erc = self.native_scan(
            default_source,
            source_name="empty-justify.kicad_sch",
            scan_hierarchy=False,
        )
        empty, empty_netlist, empty_erc = self.native_scan(
            empty_source,
            source_name="empty-justify.kicad_sch",
            scan_hierarchy=False,
        )

        assert (default.status) == ("COMPLETE")
        assert (empty.status) == ("COMPLETE")
        assert (default.unsupported_by_rule) == ({})
        assert (empty.unsupported_by_rule) == ({})
        assert (default.free_text_overlaps) == (empty.free_text_overlaps)
        assert (ET.tostring(default_netlist.find("./nets"))) == (
            ET.tostring(empty_netlist.find("./nets"))
        )

        def erc_signatures(report: dict[str, object]) -> tuple[tuple[object, ...], ...]:
            return tuple(
                sorted(
                    (
                        item["type"],
                        item["severity"],
                        tuple(entry.get("uuid") for entry in item["items"]),
                    )
                    for sheet in report.get("sheets", [])
                    for item in sheet.get("violations", [])
                )
            )

        assert (erc_signatures(default_erc)) == (erc_signatures(empty_erc))
        default_svg = self.native_svg(default_source, source_name="empty-justify.kicad_sch")
        empty_svg = self.native_svg(empty_source, source_name="empty-justify.kicad_sch")

        def first_text_svg_geometry(
            svg_root: ET.Element,
        ) -> tuple[dict[str, str], tuple[tuple[tuple[float, float], tuple[float, float]], ...]]:
            text_nodes = [
                node
                for node in svg_root.iter()
                if node.tag.endswith("}text") and node.text == "FIRST"
            ]
            assert (len(text_nodes)) == (1)
            return text_nodes[0].attrib, _native_svg_text_strokes(svg_root, "FIRST")

        assert (first_text_svg_geometry(default_svg)) == (first_text_svg_geometry(empty_svg))

    def test_unsupported_free_text_variants_preserve_native_connectivity(self) -> None:
        text_anchor = (25.4, 25.4)
        base = free_text_objects_fixture("FIRST", text_anchor, "SECOND", (29.0, 25.4))
        baseline, baseline_netlist, baseline_erc = self.native_scan(
            base, source_name="text-variant.kicad_sch", scan_hierarchy=False
        )
        assert (baseline.status) == ("COMPLETE")
        assert (len(baseline.free_text_overlaps)) == (1)

        def replace_first_text(source: bytes, old: bytes, new: bytes) -> bytes:
            start = source.index(b'(text "FIRST"')
            end_marker = b'(uuid "d0000000-0000-4000-8000-000000000001"))'
            end = source.index(end_marker, start) + len(end_marker)
            text_node = source[start:end]
            if text_node.count(old) != 1:
                raise AssertionError("expected a unique text-node style to replace")
            return source[:start] + text_node.replace(old, new, 1) + source[end:]

        variants = (
            replace_first_text(
                base,
                b"(font (size 1.27 1.27))",
                b'(font (face "Synthetic Custom Font") (size 1.27 1.27))',
            ),
            replace_first_text(
                base,
                b"(font (size 1.27 1.27))",
                b"(font (bold yes) (size 1.27 1.27))",
            ),
            replace_first_text(
                base,
                b"(font (size 1.27 1.27))",
                b"(font (italic yes) (size 1.27 1.27))",
            ),
            replace_first_text(
                base,
                b"(font (size 1.27 1.27))",
                b"(font (size 1.27 1.27) (thickness 0.2))",
            ),
            replace_first_text(
                base,
                b"(effects (font (size 1.27 1.27)))",
                b"(effects (font (size 1.27 1.27)) (justify top))",
            ),
            replace_first_text(
                base,
                b"(at 25.4 25.4 0)",
                b"(at 25.4 25.4 45)",
            ),
            free_text_objects_fixture("F~{IR}ST", text_anchor, "SECOND", (29.0, 25.4)),
            free_text_objects_fixture("FÜRST", text_anchor, "SECOND", (29.0, 25.4)),
        )

        def netlist_connectivity(root: ET.Element) -> tuple[object, ...]:
            components = tuple(
                sorted(
                    (
                        component.get("ref", ""),
                        component.findtext("value", ""),
                        component.findtext("footprint", ""),
                        (
                            component.find("libsource").get("lib", "")
                            if component.find("libsource") is not None
                            else ""
                        ),
                        (
                            component.find("libsource").get("part", "")
                            if component.find("libsource") is not None
                            else ""
                        ),
                    )
                    for component in root.findall("./components/comp")
                )
            )
            assignments = tuple(
                sorted(
                    (
                        net.get("name", ""),
                        node.get("ref", ""),
                        node.get("pin", ""),
                    )
                    for net in root.findall("./nets/net")
                    for node in net.findall("node")
                )
            )
            return components, assignments

        def erc_signatures(report: dict[str, object]) -> tuple[tuple[object, ...], ...]:
            violations = [
                item for sheet in report.get("sheets", []) for item in sheet.get("violations", [])
            ]
            return tuple(
                sorted(
                    (
                        item["type"],
                        item["severity"],
                        tuple(entry.get("uuid") for entry in item["items"]),
                    )
                    for item in violations
                )
            )

        for index, source in enumerate(variants):
            result, netlist, erc = self.native_scan(
                source, source_name="text-variant.kicad_sch", scan_hierarchy=False
            )
            assert (result.status) == ("PARTIAL")
            assert (result.free_text_overlaps) == (())
            assert (netlist_connectivity(netlist)) == (netlist_connectivity(baseline_netlist))
            assert (erc_signatures(erc)) == (erc_signatures(baseline_erc))
