"""Reviewed part selection preserves CAD bytes and refuses ambiguous instances."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.model_inventory import _atoms, _children
from kicad_tooling.hwrepo.models import PartCadBinding, PartRecord, PartStatus, ProjectManifest
from kicad_tooling.hwrepo.part_cad import (
    preview_cad,
    read_cad_components,
    validate_footprint_binding,
)
from tests.support import reference_root

MODEL = "${KIPRJMOD}/models/resistor.step"


def reviewed_part(
    footprint: str = "Pilot:R_Test", value: str = "1k", symbol_id: str = "Pilot:R"
) -> PartRecord:
    return PartRecord(
        id="resistor-reviewed",
        revision="A",
        description="Test-only identity",
        part_class="resistor",
        unit="each",
        manufacturer="Vishay",
        mpn="MRS25000C1001FCT00",
        datasheet_url="https://example.invalid/test-only",
        lifecycle="active",
        status=PartStatus.APPROVED,
        cad=PartCadBinding(
            symbol_id=symbol_id,
            value=value,
            footprint=footprint,
            model="examples/projects/controller/kicad/models/resistor.step",
        ),
    )


class PartCadTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="part-cad-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve() / "repository"
        shutil.copytree(reference_root(), self.root, ignore=shutil.ignore_patterns(".git"))
        self.schematic = self.root / "examples/projects/controller/kicad/controller.kicad_sch"
        self.board = self.schematic.with_suffix(".kicad_pcb")
        self.original_schematic = self.schematic.read_bytes().decode("utf-8")
        self.original_board = self.board.read_bytes().decode("utf-8")
        model = self.schematic.parent / "models/resistor.step"
        model.parent.mkdir()
        model.write_text("TEST-ONLY authored model fixture; not a manufacturer asset\n")
        member = self.schematic.parent / "Pilot.pretty/R_Test.kicad_mod"
        source = member.read_text()
        member.write_text(
            source.rstrip()[:-1] + f' (model "{MODEL}" '
            "(offset (xyz 1.25 0 0.5)) (scale (xyz 1 1 1)) "
            "(rotate (xyz 0 0 90)))\n)\n"
        )
        manifest_path = self.schematic.parent.parent / "project.json"
        manifest = read_model(manifest_path, ProjectManifest)
        write_model(
            manifest_path,
            manifest.model_copy(
                update={
                    "required_inputs": (*manifest.required_inputs, "kicad/models/resistor.step"),
                }
            ),
        )

    def node(self, source: str, kind: str, reference: str) -> tuple[int, int]:
        root = _children(source, 0, len(source))[0]
        for child in _children(source, root.start + 1, root.end - 1):
            if _atoms(source, child)[:1] != (kind,):
                continue
            for prop in _children(source, child.start + 1, child.end - 1):
                if _atoms(source, prop)[:3] == ("property", "Reference", reference):
                    return child.start, child.end
        self.fail(f"Missing fixture {kind} {reference}")

    def change_symbol(self, old: str, new: str, reference: str = "R1") -> None:
        source = self.schematic.read_bytes().decode("utf-8")
        start, end = self.node(source, "symbol", reference)
        self.assertIn(old, source[start:end])
        updated = source[:start] + source[start:end].replace(old, new) + source[end:]
        self.schematic.write_bytes(updated.encode("utf-8"))

    def change_board(self, old: str, new: str) -> None:
        source = self.board.read_bytes().decode("utf-8")
        start, end = self.node(source, "footprint", "R1")
        self.assertIn(old, source[start:end])
        self.board.write_bytes(
            (source[:start] + source[start:end].replace(old, new) + source[end:]).encode("utf-8")
        )

    def add_model(self, expression: str) -> None:
        source = self.board.read_bytes().decode("utf-8")
        _, end = self.node(source, "footprint", "R1")
        self.board.write_bytes(
            (source[: end - 1] + "\n    " + expression + source[end - 1 :]).encode("utf-8")
        )

    def declare_footprint(self, name: str) -> None:
        path = self.schematic.parent / f"Pilot.pretty/{name}.kicad_mod"
        path.write_text(f'(footprint "{name}" (layer "F.Cu"))\n', encoding="utf-8")
        manifest_path = self.schematic.parent.parent / "project.json"
        manifest = read_model(manifest_path, ProjectManifest)
        write_model(
            manifest_path,
            manifest.model_copy(
                update={
                    "required_inputs": (
                        *manifest.required_inputs,
                        f"kicad/Pilot.pretty/{name}.kicad_mod",
                    ),
                }
            ),
        )

    def preview(self, part: PartRecord | None = None):
        return preview_cad(self.root, "controller", {"R1": part or reviewed_part()}, {"R1": MODEL})

    def test_inventory_reads_instances_without_editing_source(self) -> None:
        components = read_cad_components(self.root, "controller")
        self.assertEqual([item.reference for item in components], ["R1", "R2"])
        self.assertEqual(
            (
                components[0].symbol_id,
                components[0].value,
                components[0].footprint,
                components[0].part_id,
            ),
            ("Pilot:R", "1k", "Pilot:R_Test", None),
        )
        self.assertEqual(components[0].uuid, "b8f01b2f-9bdb-5c6a-9689-cf06e05b0b52")
        self.assertEqual(self.schematic.read_bytes().decode(), self.original_schematic)

    def test_matching_board_adds_part_and_model_without_writing_or_changing_geometry(self) -> None:
        report = self.preview()
        self.assertEqual(report.pending_references, ())
        self.assertEqual(len(report.edits), 2)
        by_suffix = {Path(edit.path).suffix: edit for edit in report.edits}
        schematic = by_suffix[".kicad_sch"]
        board = by_suffix[".kicad_pcb"]
        self.assertEqual(schematic.before, self.original_schematic)
        self.assertEqual(board.before, self.original_board)
        for before, after, kind in (
            (self.original_schematic, schematic.after, "symbol"),
            (self.original_board, board.after, "footprint"),
        ):
            start, end = self.node(before, kind, "R1")
            new_start, new_end = self.node(after, kind, "R1")
            self.assertEqual(before[:start], after[:new_start])
            self.assertEqual(before[end:], after[new_end:])
            expected_existing = before[start : end - 1].replace(
                '(property "Datasheet" ""',
                '(property "Datasheet" "https://example.invalid/test-only"',
            )
            self.assertTrue(after[new_start:new_end].startswith(expected_existing))
        self.assertIn('(property "PART_ID" "resistor-reviewed"', schematic.after)
        self.assertIn(f'(model "{MODEL}"', board.after)
        self.assertIn("(offset (xyz 1.25 0 0.5))", board.after)
        self.assertIn("(rotate (xyz 0 0 90))", board.after)
        for edit in (schematic, board):
            for name, value in (
                ("Manufacturer", "Vishay"),
                ("MPN", "MRS25000C1001FCT00"),
                ("Datasheet", "https://example.invalid/test-only"),
            ):
                self.assertIn(f'(property "{name}" "{value}"', edit.after)
        self.assertEqual(self.schematic.read_bytes().decode(), self.original_schematic)
        self.assertEqual(self.board.read_bytes().decode(), self.original_board)

    def test_new_model_without_authored_pair_is_refused(self) -> None:
        member = self.schematic.parent / "Pilot.pretty/R_Test.kicad_mod"
        source = member.read_text()
        start = source.index(' (model "')
        member.write_text(source[:start] + "\n)\n")
        with self.assertRaisesRegex(ValueError, "no paired 3D model"):
            self.preview()
        self.assertEqual(self.board.read_bytes().decode(), self.original_board)

    def test_new_model_refuses_different_pad_spacing_and_catalog_model(self) -> None:
        self.change_board("(at 10 0)", "(at 9 0)")
        with self.assertRaisesRegex(ValueError, "numbered pad geometry"):
            self.preview()
        self.board.write_text(self.original_board)
        part = reviewed_part()
        assert part.cad is not None
        different = part.model_copy(
            update={
                "cad": part.cad.model_copy(
                    update={
                        "model": "examples/projects/controller/kicad/models/other.step",
                    }
                )
            }
        )
        with self.assertRaisesRegex(ValueError, "catalog model must match"):
            self.preview(different)

    def test_changed_footprint_is_schematic_only_and_pending_f8(self) -> None:
        self.declare_footprint("Other_Package")
        report = self.preview(reviewed_part(footprint="Pilot:Other_Package"))
        self.assertEqual(report.pending_references, ("R1",))
        self.assertEqual(len(report.edits), 1)
        after = report.edits[0].after
        start, end = self.node(after, "symbol", "R1")
        self.assertIn('(property "Footprint" "Pilot:Other_Package"', after[start:end])
        self.assertIn('(property "Value" "1k"', after[start:end])
        self.assertIn('(property "Footprint" "Pilot:R_Test"', after[:start])
        self.assertEqual(self.board.read_bytes().decode(), self.original_board)

    def test_missing_board_or_footprint_is_pending_without_geometry_creation(self) -> None:
        source = self.original_board
        start, end = self.node(source, "footprint", "R1")
        self.board.write_text(source[:start] + source[end:], encoding="utf-8")
        self.assertEqual(self.preview().pending_references, ("R1",))
        self.board.unlink()
        self.assertEqual(self.preview().pending_references, ("R1",))
        self.assertFalse(self.board.exists())

    def test_mismatched_pcb_instance_path_is_pending(self) -> None:
        self.change_board(
            "b8f01b2f-9bdb-5c6a-9689-cf06e05b0b52", "11c55fda-a71c-5108-9dc8-c91bba18d665"
        )
        report = self.preview()
        self.assertEqual(report.pending_references, ("R1",))
        self.assertTrue(all(not edit.path.endswith(".kicad_pcb") for edit in report.edits))

    def test_stale_pcb_value_requires_f8_without_mutating_value(self) -> None:
        self.change_board('(property "Value" "1k"', '(property "Value" "2k"')
        before = self.board.read_bytes()
        report = self.preview()
        self.assertEqual(report.pending_references, ("R1",))
        self.assertTrue(all(not edit.path.endswith(".kicad_pcb") for edit in report.edits))
        self.assertEqual(self.board.read_bytes(), before)

    def test_stale_pcb_population_flags_require_f8(self) -> None:
        for flag in ("dnp", "exclude_from_bom"):
            with self.subTest(flag=flag):
                self.board.write_text(self.original_board, encoding="utf-8")
                self.change_board("(attr through_hole)", f"(attr through_hole {flag})")
                report = self.preview()
                self.assertEqual(report.pending_references, ("R1",))
                self.assertTrue(all(not edit.path.endswith(".kicad_pcb") for edit in report.edits))
        self.board.write_text(self.original_board, encoding="utf-8")
        self.change_board("(attr through_hole)", "(attr through_hole exclude_from_pos_files)")
        self.assertEqual(self.preview().pending_references, ())

    def test_same_model_keeps_existing_transforms_byte_for_byte(self) -> None:
        model = f'(model "{MODEL}" (offset (xyz 1.2 3.4 5.6)) '
        model += "(scale (xyz 0.5 2 3)) (rotate (xyz 90 180 270)))"
        self.add_model(model)
        report = self.preview()
        board = next(edit for edit in report.edits if edit.path.endswith(".kicad_pcb"))
        self.assertIn(model, board.after)
        self.assertEqual(board.after.count('(model "'), 1)

    def test_other_or_duplicate_existing_models_block(self) -> None:
        self.add_model('(model "${KIPRJMOD}/models/other.step" (offset (xyz 1 2 3)))')
        with self.assertRaisesRegex(ValueError, "existing 3D model"):
            self.preview()
        self.board.write_text(self.original_board, encoding="utf-8")
        self.add_model(f'(model "{MODEL}")\n    (model "{MODEL}")')
        with self.assertRaisesRegex(ValueError, "existing 3D model"):
            self.preview()

    def test_existing_property_tokens_change_without_losing_position_or_visibility(self) -> None:
        for edit in self.preview().edits:
            (self.root / edit.path).write_bytes(edit.after.encode("utf-8"))
        substitutions = (
            ("resistor-reviewed", "previous-reviewed"),
            ("Vishay", "Old manufacturer"),
            ("MRS25000C1001FCT00", "OLD-MPN"),
            ("https://example.invalid/test-only", "https://example.invalid/old"),
        )
        originals: dict[str, str] = {}
        for path in (self.schematic, self.board):
            source = path.read_bytes().decode("utf-8")
            originals[path.relative_to(self.root).as_posix()] = source
            for correct, previous in substitutions:
                source = source.replace('"' + correct + '"', '"' + previous + '"')
            path.write_bytes(source.encode("utf-8"))
        report = self.preview()
        self.assertEqual(len(report.edits), 2)
        for edit in report.edits:
            self.assertEqual(edit.after, originals[edit.path])

    def test_reviewed_catalog_text_is_quoted_safely_in_schematic_and_pcb(self) -> None:
        part = reviewed_part().model_copy(
            update={
                "manufacturer": 'Vishay "Components"',
                "mpn": "CODE\\SUFFIX",
                "datasheet_url": "https://example.invalid/data?a=1&b=2",
            }
        )
        report = self.preview(part)
        for edit in report.edits:
            self.assertIn('Vishay \\"Components\\"', edit.after)
            self.assertIn("CODE\\\\SUFFIX", edit.after)
            self.assertIn("https://example.invalid/data?a=1&b=2", edit.after)
        for edit in report.edits:
            (self.root / edit.path).write_bytes(edit.after.encode("utf-8"))
        self.assertEqual(self.preview(part).edits, ())

    def test_missing_footprint_property_is_inserted_with_safe_native_syntax(self) -> None:
        self.change_symbol('(property "Footprint"', '(property "FormerFootprint"')
        report = self.preview()
        after = next(edit.after for edit in report.edits if edit.path.endswith(".kicad_sch"))
        self.schematic.write_bytes(after.encode())
        self.assertEqual(read_cad_components(self.root, "controller")[0].footprint, "Pilot:R_Test")

    def test_crlf_source_remains_crlf_in_plan(self) -> None:
        self.schematic.write_bytes(self.original_schematic.replace("\n", "\r\n").encode())
        self.board.write_bytes(self.original_board.replace("\n", "\r\n").encode())
        for edit in self.preview().edits:
            assert edit.before is not None
            self.assertIn("\r\n", edit.before)
            self.assertNotIn("\n", edit.after.replace("\r\n", ""))

    def test_unsafe_footprint_filename_cannot_insert_sexpressions(self) -> None:
        with self.assertRaises(ValueError):
            self.preview(reviewed_part(footprint='Pilot:Quoted"Name'))
        self.assertEqual(self.schematic.read_bytes().decode(), self.original_schematic)

    def test_missing_or_undeclared_footprint_is_not_offered_as_pending(self) -> None:
        with self.assertRaisesRegex(ValueError, "must be declared"):
            self.preview(reviewed_part(footprint="Pilot:Missing"))
        self.declare_footprint("Missing")
        (self.schematic.parent / "Pilot.pretty/Missing.kicad_mod").unlink()
        with self.assertRaisesRegex(ValueError, "file is missing"):
            self.preview(reviewed_part(footprint="Pilot:Missing"))

    def test_stock_or_global_footprint_resolution_requires_an_explicit_prerequisite(self) -> None:
        with self.assertRaisesRegex(ValueError, "not in the declared"):
            self.preview(reviewed_part(footprint="Resistor_SMD:R_0603"))
        table = self.schematic.parent / "fp-lib-table"
        table.write_text(
            table.read_text().replace(
                "${KIPRJMOD}/Pilot.pretty", "${KICAD10_FOOTPRINT_DIR}/Pilot.pretty"
            )
        )
        with self.assertRaisesRegex(ValueError, "global, machine-specific or unresolved"):
            self.preview()

    def test_declared_shared_library_footprint_resolves(self) -> None:
        validate_footprint_binding(
            self.root, "raspberry-pi-status-led", "StatusLedTraining:R_Axial_10mm"
        )

    def test_duplicate_library_nickname_and_wrong_member_identity_fail(self) -> None:
        table = self.schematic.parent / "fp-lib-table"
        original = table.read_text()
        table.write_text(
            original[:-2] + '(lib (name "Pilot")(type "KiCad")'
            '(uri "${KIPRJMOD}/Pilot.pretty"))\n)\n'
        )
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            self.preview()
        table.write_text(original)
        member = self.schematic.parent / "Pilot.pretty/R_Test.kicad_mod"
        member.write_text(member.read_text().replace('(footprint "R_Test"', '(footprint "Other"'))
        with self.assertRaisesRegex(ValueError, "file identity differs"):
            self.preview()

    def test_symbol_and_value_compatibility_are_exact(self) -> None:
        for part in (reviewed_part(value="2k"), reviewed_part(symbol_id="Device:R")):
            with self.subTest(part=part), self.assertRaisesRegex(ValueError, "symbol/value"):
                self.preview(part)
        self.assertEqual(self.schematic.read_bytes().decode(), self.original_schematic)

    def test_project_instance_and_reference_mismatches_fail(self) -> None:
        for old, new in (
            ('(project "controller"', '(project "unrelated"'),
            ('(reference "R1")', '(reference "R9")'),
            ('(path "/161c9728-dba4-5866-866e-d6b916f9d485"', '(path "/other-sheet"'),
        ):
            with self.subTest(new=new):
                self.schematic.write_text(self.original_schematic, encoding="utf-8")
                self.change_symbol(old, new)
                with self.assertRaisesRegex(ValueError, "instance|reference"):
                    read_cad_components(self.root, "controller")

    def test_native_project_stem_need_not_equal_registry_id(self) -> None:
        directory = self.schematic.parent.parent
        renamed = directory.with_name("controller-renamed")
        directory.rename(renamed)
        manifest_path = renamed / "project.json"
        manifest = read_model(manifest_path, ProjectManifest)
        write_model(manifest_path, manifest.model_copy(update={"id": "controller-renamed"}))
        self.assertEqual(len(read_cad_components(self.root, "controller-renamed")), 2)

    def test_hierarchy_and_legacy_annotations_fail_with_actionable_scope(self) -> None:
        for expression, expected in (
            ('(sheet (uuid "x"))', "Hierarchical"),
            ('(symbol_instances (path "/x"))', "Legacy"),
        ):
            with self.subTest(expression=expression):
                self.schematic.write_text(
                    self.original_schematic[:-2] + expression + "\n)\n", encoding="utf-8"
                )
                with self.assertRaisesRegex(ValueError, expected):
                    read_cad_components(self.root, "controller")

    def test_duplicate_references_properties_and_uuids_fail(self) -> None:
        mutations = (
            ('(property "Datasheet" ""', '(property "Footprint" ""'),
            (
                '(uuid "b8f01b2f-9bdb-5c6a-9689-cf06e05b0b52")',
                '(uuid "11c55fda-a71c-5108-9dc8-c91bba18d665")',
            ),
        )
        for old, new in mutations:
            with self.subTest(new=new):
                self.schematic.write_text(self.original_schematic, encoding="utf-8")
                self.change_symbol(old, new)
                with self.assertRaisesRegex(ValueError, "duplicate|Duplicate"):
                    read_cad_components(self.root, "controller")
        self.schematic.write_text(self.original_schematic, encoding="utf-8")
        self.change_board('"Reference" "R1"', '"Reference" "R2"')
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.preview()

    def test_multiunit_inventory_collapses_only_consistent_fields_but_apply_refuses(self) -> None:
        start, end = self.node(self.original_schematic, "symbol", "R1")
        second = (
            self.original_schematic[start:end]
            .replace("(unit 1)", "(unit 2)")
            .replace("b8f01b2f-9bdb-5c6a-9689-cf06e05b0b52", "733d029a-2d84-416a-9319-8a86af6c1296")
        )
        source = self.original_schematic[:end] + "\n  " + second + self.original_schematic[end:]
        self.schematic.write_text(source, encoding="utf-8")
        self.assertEqual(len(read_cad_components(self.root, "controller")), 2)
        with self.assertRaisesRegex(ValueError, "multi-unit"):
            self.preview()
        self.schematic.write_text(source.replace("(unit 2)", "(unit 1)"), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "duplicate"):
            read_cad_components(self.root, "controller")

    def test_multiunit_library_is_refused_even_when_only_unit_one_is_placed(self) -> None:
        source = self.original_schematic.replace('(symbol "R_0_1"', '(symbol "R_2_1"')
        self.schematic.write_text(source, encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "multi-unit"):
            self.preview()

    def test_dnp_bom_exclusions_and_offboard_symbols_are_not_populated(self) -> None:
        for old, new, reason in (
            ("(dnp no)", "(dnp yes)", "excluded"),
            ("(in_bom yes)", "(in_bom no)", "excluded"),
            ("(on_board yes)", "(on_board no)", "off-board"),
        ):
            with self.subTest(new=new):
                self.schematic.write_text(self.original_schematic, encoding="utf-8")
                self.change_symbol(old, new)
                with self.assertRaisesRegex(ValueError, reason):
                    self.preview()

    def test_malformed_source_and_unquoted_property_fail(self) -> None:
        self.schematic.write_text(self.original_schematic + ")", encoding="utf-8")
        with self.assertRaises(ValueError):
            read_cad_components(self.root, "controller")
        self.schematic.write_text(self.original_schematic, encoding="utf-8")
        self.change_symbol('(property "Value" "1k"', '(property "Value" 1k')
        with self.assertRaisesRegex(ValueError, "quoted"):
            read_cad_components(self.root, "controller")

    def test_model_mapping_set_must_match_selected_references(self) -> None:
        with self.assertRaisesRegex(ValueError, "Every selected"):
            preview_cad(self.root, "controller", {"R1": reviewed_part()}, {})
        with self.assertRaisesRegex(ValueError, "Unknown schematic"):
            preview_cad(self.root, "controller", {"R9": reviewed_part()}, {"R9": MODEL})
