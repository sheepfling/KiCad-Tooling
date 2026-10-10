"""Focused hierarchy schematic geometry regressions."""

from __future__ import annotations

import hashlib

import pytest

from kicad_tooling.hwrepo.schematic_geometry import (
    SUPPORTED_KICAD_VERSION,
    resolve_schematic_sheet_path,
    scan_schematic_geometry_tree,
    schematic_sheet_references,
)
from tests.design_lint_fixtures.schematic_geometry_fixtures import (
    FAULT,
    REPEATED_CHANNEL,
    REPEATED_CHANNEL_CONTROL,
    REPEATED_SHEET,
    REPEATED_SHEET_CONTROL,
    TRANSFORM_MIDPOINTS,
    transformed_fault,
)
from tests.design_lint_fixtures.schematic_geometry_test_cases import SchematicGeometryHelpers

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.schematic_lint,
    pytest.mark.schematic_hierarchy_lint,
]


class SchematicGeometryHierarchyTests(SchematicGeometryHelpers):
    def test_no_connect_marker_and_off_line_endpoint_are_excluded(self) -> None:
        source = FAULT.read_bytes()
        source = source.replace(
            b"  (wire (pts",
            b'  (no_connect (at 76.2 71.12) (uuid "a0000000-0000-4000-8000-000000000007"))\n'
            b"  (wire (pts",
            1,
        )
        assert (self.scan(source).findings) == (())

        offset = FAULT.read_bytes().replace(b"76.2 72.39", b"76.21 72.39", 1)
        assert (self.scan(offset).findings) == (())

    def test_exact_kicad_version_format_and_sheet_scope_are_enforced(self) -> None:
        supported_patch_version = self.scan(FAULT.read_bytes(), version="10.0.5")
        assert (supported_patch_version.status) == ("COMPLETE")
        assert (len(supported_patch_version.findings)) == (1)

        wrong_version = self.scan(FAULT.read_bytes(), version="10.0.0")
        assert (wrong_version.status) == ("UNSUPPORTED")
        assert not (wrong_version.findings)
        assert ("10.0.5") in (wrong_version.unsupported[0])
        assert ("10.0.6") in (wrong_version.unsupported[0])

        wrong_format = self.scan(FAULT.read_bytes().replace(b"20231120", b"20250101", 1))
        assert (wrong_format.status) == ("UNSUPPORTED")
        assert (wrong_format.schematic_version) == ("20250101")

        hierarchical = self.scan(
            FAULT.read_bytes().replace(
                b"  (sheet_instances",
                b"  (sheet (at 0 0) (size 10 10))\n  (sheet_instances",
                1,
            )
        )
        assert (hierarchical.status) == ("UNSUPPORTED")
        assert ("Hierarchical") in (hierarchical.unsupported[0])

    def test_single_file_scanner_rejects_hierarchy_without_tree_context(self) -> None:
        result = self.scan(
            REPEATED_SHEET.read_bytes(),
            unconnected_pins=frozenset({"R1.2", "R2.2"}),
        )

        assert (result.status) == ("UNSUPPORTED")
        assert ("Hierarchical") in (result.unsupported[0])
        assert (result.findings) == (())
        control = self.scan(
            REPEATED_SHEET_CONTROL.read_bytes(),
            unconnected_pins=frozenset(),
        )
        assert (control.status) == ("UNSUPPORTED")

    def test_kicad8_sheet_property_names_bind_reused_child_instances(self) -> None:
        legacy_root = (
            REPEATED_SHEET.read_bytes()
            .replace(b'"Sheet name"', b'"Sheetname"')
            .replace(b'"Sheet file"', b'"Sheetfile"')
        )
        result = scan_schematic_geometry_tree(
            {
                REPEATED_SHEET.name: legacy_root,
                REPEATED_CHANNEL.name: REPEATED_CHANNEL.read_bytes(),
            },
            root_path=REPEATED_SHEET.name,
            project_directory=".",
            project_name=REPEATED_SHEET.stem,
            kicad_version=SUPPORTED_KICAD_VERSION,
            unconnected_pins=frozenset({"R1.2", "R2.2"}),
        )

        assert (result.status) == ("COMPLETE")
        assert (len(result.source_bindings)) == (3)
        assert ({binding.sheet_path for binding in result.source_bindings}) == (
            {(), ("InstanceA",), ("InstanceB",)}
        )

    def test_duplicate_legacy_and_current_sheet_property_aliases_fail_closed(self) -> None:
        source = REPEATED_SHEET.read_bytes().replace(b'"Sheet name"', b'"Sheetname"', 1)
        duplicate = (
            b'(property "Sheet name" "InstanceA" (id 2) (at 50 49.3 0) '
            b"(effects (font (size 1.27 1.27))))\n    "
        )
        source = source.replace(
            b'(property "Sheetname" "InstanceA"',
            duplicate + b'(property "Sheetname" "InstanceA"',
            1,
        )

        with pytest.raises(ValueError, match="Duplicate KiCad property aliases"):
            schematic_sheet_references(source)

    def test_reused_sheet_tree_maps_geometry_to_each_instance_reference(self) -> None:
        repeated_channel = REPEATED_CHANNEL.read_text(encoding="utf-8").replace(
            "  (sheet_instances",
            '  (text "CHANNEL_A" (at 25.4 25.4 0) '
            "(effects (font (size 1.27 1.27))) "
            '(uuid "e0000000-0000-4000-8000-000000000001"))\n'
            '  (text "CHANNEL_B" (at 25.4 25.4 0) '
            "(effects (font (size 1.27 1.27))) "
            '(uuid "e0000000-0000-4000-8000-000000000002"))\n'
            '  (text "LONG_LABEL_ALPHA" (at 120 25.4 0) '
            "(effects (font (size 1.27 1.27))) "
            '(uuid "e0000000-0000-4000-8000-000000000003"))\n'
            '  (text "LONG_LABEL_BETA" (at 123.6 25.4 0) '
            "(effects (font (size 1.27 1.27))) "
            '(uuid "e0000000-0000-4000-8000-000000000004"))\n'
            "  (sheet_instances",
            1,
        )
        fault = scan_schematic_geometry_tree(
            {
                REPEATED_SHEET.name: REPEATED_SHEET.read_bytes(),
                REPEATED_CHANNEL.name: repeated_channel.encode("utf-8"),
            },
            root_path=REPEATED_SHEET.name,
            project_directory=".",
            project_name=REPEATED_SHEET.stem,
            kicad_version=SUPPORTED_KICAD_VERSION,
            unconnected_pins=frozenset({"R1.2", "R2.2"}),
        )

        assert (fault.status) == ("COMPLETE")
        assert (len(fault.unmarked_t_junctions)) == (2)
        assert ({item.sheet_instance_path for item in fault.unmarked_t_junctions}) == (
            {
                "/d0000000-0000-4000-8000-000000000001/d0000000-0000-4000-8000-000000000002",
                "/d0000000-0000-4000-8000-000000000001/d0000000-0000-4000-8000-000000000003",
            }
        )
        assert (len(fault.source_bindings)) == (3)
        assert (len(fault.source_tree_sha256 or "")) == (64)
        assert (len(fault.coincident_text_anchors)) == (2)
        assert ({item.sheet_instance_path for item in fault.coincident_text_anchors}) == (
            {
                "/d0000000-0000-4000-8000-000000000001/d0000000-0000-4000-8000-000000000002",
                "/d0000000-0000-4000-8000-000000000001/d0000000-0000-4000-8000-000000000003",
            }
        )
        assert (len(fault.free_text_overlaps)) == (2)
        assert ({item.sheet_instance_path for item in fault.free_text_overlaps}) == (
            {
                "/d0000000-0000-4000-8000-000000000001/d0000000-0000-4000-8000-000000000002",
                "/d0000000-0000-4000-8000-000000000001/d0000000-0000-4000-8000-000000000003",
            }
        )

        control = scan_schematic_geometry_tree(
            {
                REPEATED_SHEET_CONTROL.name: REPEATED_SHEET_CONTROL.read_bytes(),
                REPEATED_CHANNEL_CONTROL.name: REPEATED_CHANNEL_CONTROL.read_bytes(),
            },
            root_path=REPEATED_SHEET_CONTROL.name,
            project_directory=".",
            project_name=REPEATED_SHEET_CONTROL.stem,
            kicad_version=SUPPORTED_KICAD_VERSION,
            unconnected_pins=frozenset(),
        )
        assert (control.status) == ("COMPLETE")
        assert (control.unmarked_t_junctions) == (())
        assert (control.free_text_overlaps) == (())
        assert (fault.source_tree_sha256) != (control.source_tree_sha256)

    def test_reused_sheet_without_exact_instance_references_is_partial(self) -> None:
        child = REPEATED_CHANNEL.read_text(encoding="utf-8").replace(
            'project "repeated-sheet-root"', 'project "different-project"'
        )
        result = scan_schematic_geometry_tree(
            {
                REPEATED_SHEET.name: REPEATED_SHEET.read_bytes(),
                REPEATED_CHANNEL.name: child.encode("utf-8"),
            },
            root_path=REPEATED_SHEET.name,
            project_directory=".",
            project_name=REPEATED_SHEET.stem,
            kicad_version=SUPPORTED_KICAD_VERSION,
            unconnected_pins=frozenset({"R1.2", "R2.2"}),
        )

        assert (result.status) == ("PARTIAL")
        assert (len(result.unmarked_t_junctions)) == (2)
        assert (len(result.source_bindings)) == (3)
        assert (len(result.unsupported)) == (4)
        assert all(
            "no unique" in item.casefold() and "reference" in item.casefold()
            for item in result.unsupported
        )
        assert (len(result.unsupported_by_rule["schematic.pin_tip_on_wire_interior"])) == (4)
        assert ("schematic.free_text_overlap") not in (result.unsupported_by_rule)

    def test_hierarchical_sheet_resolution_rejects_project_escape(self) -> None:
        with pytest.raises(ValueError, match="escapes its project directory"):
            resolve_schematic_sheet_path(
                "projects/controller/main.kicad_sch",
                "projects/controller",
                "../sibling/child.kicad_sch",
            )

    def test_rotated_and_mirrored_pin_line_transforms(self) -> None:
        # Pin-1 midpoint coordinates were checked against KiCad 10.0.6 native
        # netlist coordinates for each orthogonal orientation and mirror mode.
        semantic_finding: tuple[str, str, str, str, str, float, float, str] | None = None
        source_hashes: set[str] = set()
        for (angle, mirror), endpoint in TRANSFORM_MIDPOINTS.items():
            source = transformed_fault(angle, mirror, endpoint)
            result = self.scan(source)
            assert (result.status) == ("COMPLETE")
            assert (len(result.findings)) == (1)
            finding = result.findings[0]
            assert (finding.wire_endpoint_mm) == (endpoint)
            observed_semantics = (
                finding.reference,
                finding.symbol_library_id,
                finding.pin_number,
                finding.pin_name,
                finding.wire_uuid,
                finding.distance_to_pin_tip_mm,
                finding.distance_along_pin_mm,
                finding.sheet_instance_path,
            )
            if semantic_finding is None:
                semantic_finding = observed_semantics
            assert (observed_semantics) == (semantic_finding)
            assert (result.source_sha256) == (hashlib.sha256(source).hexdigest())
            source_hashes.add(result.source_sha256)

            # Match the fixture helper's source spelling exactly; some
            # binary floats are emitted with their full Python repr.
            wire_end = (endpoint[0] + 25.4, endpoint[1])
            wire_points = (
                f"(xy {endpoint[0]} {endpoint[1]}) (xy {wire_end[0]} {wire_end[1]})"
            ).encode()
            reverse_points = (
                f"(xy {wire_end[0]} {wire_end[1]}) (xy {endpoint[0]} {endpoint[1]})"
            ).encode()
            assert (source.count(wire_points)) == (1)
            reversed_source = source.replace(wire_points, reverse_points, 1)
            reversed_result = self.scan(reversed_source)
            assert (reversed_result.status) == ("COMPLETE")
            assert (len(reversed_result.findings)) == (1)
            reversed_finding = reversed_result.findings[0]
            assert (
                (
                    reversed_finding.reference,
                    reversed_finding.symbol_library_id,
                    reversed_finding.pin_number,
                    reversed_finding.pin_name,
                    reversed_finding.wire_uuid,
                    reversed_finding.distance_to_pin_tip_mm,
                    reversed_finding.distance_along_pin_mm,
                    reversed_finding.sheet_instance_path,
                )
            ) == (observed_semantics)
            assert (reversed_finding.wire_endpoint_mm) == (endpoint)

            # Translating the whole wire slightly off the pin axis removes
            # the candidate without changing the unconnected-pin input.
            if finding.pin_tip_mm[0] == finding.pin_body_end_mm[0]:
                delta_x, delta_y = 0.01, 0.0
            else:
                delta_x, delta_y = 0.0, 0.01
            shifted_start = (round(endpoint[0] + delta_x, 6), round(endpoint[1] + delta_y, 6))
            shifted_end = (round(wire_end[0] + delta_x, 6), round(wire_end[1] + delta_y, 6))
            shifted_points = (
                f"(xy {shifted_start[0]} {shifted_start[1]}) (xy {shifted_end[0]} {shifted_end[1]})"
            ).encode()
            shifted_source = source.replace(wire_points, shifted_points, 1)
            shifted_result = self.scan(shifted_source)
            assert (shifted_result.status) == ("COMPLETE")
            assert (shifted_result.findings) == (())

        assert (semantic_finding) is not None
        assert (len(source_hashes)) > (1)
