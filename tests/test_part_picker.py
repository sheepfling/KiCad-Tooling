"""Reviewed source selection is explicit, source-bound and transactionally reversible."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError

from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.models import (
    CommandEvidence,
    ComponentIdentity,
    PartCadBinding,
    PartPickerReport,
    PartRecord,
    PartsCatalog,
    PartSelectionAssignment,
    PartSelectionMap,
    PartSelectionReport,
    PartStatus,
    ProjectConfig,
    ProjectManifest,
    PurchasingPreferences,
)
from kicad_tooling.hwrepo.part_cad import read_cad_components
from kicad_tooling.hwrepo.part_picker import create_picker, resume_selection, selection
from kicad_tooling.hwrepo.parts_workflow import new_receipt
from tests.support import reference_root

NETLIST = """<export><components>
<comp ref="R1"><value>1k</value><footprint>Pilot:R_Test</footprint></comp>
<comp ref="R2"><value>2k</value><footprint>Pilot:R_Test</footprint></comp>
</components><nets/></export>"""


class PickerRunner:
    selected_runner = "local"

    def version(self, root: Path, config: ProjectConfig) -> CommandEvidence:
        return CommandEvidence(
            argv=("test-kicad-cli",),
            started_utc="2026-09-24T00:00:00+00:00",
            returncode=0,
            stdout=config.kicad_version + "\n",
        )

    def export(self, root: Path, config: ProjectConfig, output: Path) -> CommandEvidence:
        output.write_text(NETLIST, encoding="utf-8")
        return CommandEvidence(
            argv=("test-kicad-cli",), started_utc="2026-09-24T00:00:00+00:00", returncode=0
        )


class PartPickerTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="part-picker-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve() / "source"
        shutil.copytree(reference_root(), self.root, ignore=shutil.ignore_patterns(".git"))
        self.project_id = "controller"
        self.island = self.root / "examples/projects/controller"
        self.manifest_path = self.island / "project.json"
        self.schematic = self.island / "kicad/controller.kicad_sch"
        self.board = self.island / "kicad/controller.kicad_pcb"
        self.preferences = self.island / "docs/purchasing.json"
        self.model = self.island / "kicad/test-only.step"
        self.model.write_text(
            "TEST-ONLY GEOMETRY PLACEHOLDER; never a reviewed real model\n", encoding="utf-8"
        )
        member = self.island / "kicad/Pilot.pretty/R_Test.kicad_mod"
        member.write_text(
            member.read_text().rstrip()[:-1]
            + ' (model "${KIPRJMOD}/test-only.step" (offset (xyz 1.25 0 0.5)) '
            "(scale (xyz 1 1 1)) (rotate (xyz 0 0 90)))\n)\n"
        )
        manifest = read_model(self.manifest_path, ProjectManifest)
        write_model(
            self.manifest_path,
            manifest.model_copy(
                update={
                    "required_inputs": (*manifest.required_inputs, "kicad/test-only.step"),
                }
            ),
        )
        self.catalog_path = self.root / "catalog/parts.json"
        self.part = PartRecord(
            id="test-r1",
            revision="A",
            description="TEST-ONLY purchasing fixture",
            part_class="resistor",
            unit="each",
            manufacturer="Vishay",
            mpn="MRS25000C1001FCT00",
            datasheet_url="https://example.invalid/test-only",
            lifecycle="active",
            status=PartStatus.APPROVED,
            cad=PartCadBinding(
                symbol_id="Pilot:R",
                value="1k",
                footprint="Pilot:R_Test",
                model=self.model.relative_to(self.root).as_posix(),
                digikey_sku="541-TEST-ND",
            ),
        )
        self.set_parts(self.part)

    def set_parts(self, *parts: PartRecord) -> None:
        write_model(self.catalog_path, PartsCatalog(schema_version="1", parts=parts))

    def receipt(self) -> Path:
        return new_receipt(self.root, self.project_id, None)

    def picker(self) -> PartPickerReport:
        return create_picker(self.root, self.project_id, self.receipt(), PickerRunner())

    def draft(self, report: PartPickerReport | None = None) -> Path:
        report = self.picker() if report is None else report
        self.assertEqual(report.status, "READY", report.issues)
        assert report.selection_template is not None
        spec = report.selection_template.model_copy(
            update={
                "assignments": (PartSelectionAssignment(reference="R1", part_id=self.part.id),),
            }
        )
        path = self.root / "build/selected.json"
        path.write_text(spec.model_dump_json(indent=2) + "\n", encoding="utf-8")
        return path

    def test_picker_shows_only_exact_reviewed_candidates_and_binds_absence(self) -> None:
        before = self.schematic.read_bytes()
        report = self.picker()
        self.assertEqual(report.status, "READY", report.issues)
        self.assertEqual(report.items[0].choice_ids, ("test-r1",))
        self.assertEqual(report.items[1].choice_ids, ())
        self.assertIn("exact value '2k'", " ".join(report.items[1].issues))
        self.assertEqual(report.choices, (self.part,))
        assert report.selection_template is not None
        preconditions = report.selection_template.preconditions
        self.assertIn(self.preferences.relative_to(self.root).as_posix(), preconditions)
        self.assertIsNone(preconditions[self.preferences.relative_to(self.root).as_posix()])
        self.assertIn(self.model.relative_to(self.root).as_posix(), preconditions)
        self.assertEqual(self.schematic.read_bytes(), before)
        self.assertEqual(PartPickerReport.model_validate_json(report.model_dump_json()), report)

    def test_empty_training_missing_and_wrong_cad_catalogs_are_actionable(self) -> None:
        assert self.part.cad is not None
        for record in (
            None,
            self.part.model_copy(update={"status": PartStatus.TRAINING}),
            self.part.model_copy(update={"cad": None}),
            self.part.model_copy(
                update={"cad": self.part.cad.model_copy(update={"symbol_id": "Device:R"})}
            ),
            self.part.model_copy(update={"cad": self.part.cad.model_copy(update={"value": "10k"})}),
            self.part.model_copy(
                update={"cad": self.part.cad.model_copy(update={"model": "outside/missing.step"})}
            ),
            self.part.model_copy(update={"mpn": "TBD"}),
        ):
            with self.subTest(record=record):
                self.set_parts(*(() if record is None else (record,)))
                report = self.picker()
                self.assertEqual(report.status, "NEEDS_CATALOG", report.issues)
                self.assertEqual(report.choices, ())
                self.assertTrue(report.items[0].issues)

    def test_cad_contract_strict_and_old_catalog_still_valid(self) -> None:
        assert self.part.cad is not None
        binding = self.part.cad
        self.assertEqual(PartCadBinding.model_validate_json(binding.model_dump_json()), binding)
        for raw in (
            binding.model_dump_json().replace('"Pilot:R_Test"', '"R_Test"'),
            binding.model_dump_json().replace('"541-TEST-ND"', '" padded "'),
            binding.model_dump_json().replace('"541-TEST-ND"', "4"),
            binding.model_dump_json()[:-1] + ',"unknown":true}',
        ):
            with self.subTest(raw=raw), self.assertRaises(ValidationError):
                PartCadBinding.model_validate_json(raw)
        legacy = self.part.model_dump_json(exclude={"cad"})
        self.assertIsNone(PartRecord.model_validate_json(legacy).cad)

    def test_preview_has_all_diffs_and_does_not_write_authoritative_source(self) -> None:
        selected = self.draft()
        originals = {
            path: path.read_bytes() for path in (self.schematic, self.board, self.manifest_path)
        }
        report = selection(self.root, self.project_id, selected, self.receipt())
        self.assertEqual(report.status, "PLAN", report.issues)
        self.assertEqual(len(report.edits), 4)
        self.assertFalse(self.preferences.exists())
        self.assertEqual({path: path.read_bytes() for path in originals}, originals)
        self.assertIn("PART_ID", (Path(report.receipt_dir) / "selection.diff").read_text())
        assert report.locked_map is not None
        locked = read_model(Path(report.locked_map), PartSelectionMap)
        self.assertTrue(locked.locked)
        self.assertEqual(set(locked.after_hashes), {edit.path for edit in report.edits})
        self.assertEqual(PartSelectionReport.model_validate_json(report.model_dump_json()), report)

    def test_apply_updates_only_selected_sources_manifest_and_saved_supplier(self) -> None:
        write_model(
            self.preferences, PurchasingPreferences(boards=7, spare_percent=10, spare_minimum=3)
        )
        report = selection(self.root, self.project_id, self.draft(), self.receipt())
        assert report.locked_map is not None
        applied = selection(
            self.root, self.project_id, Path(report.locked_map), self.receipt(), apply=True
        )
        self.assertEqual(applied.status, "APPLIED", applied.issues)
        components = read_cad_components(self.root, self.project_id)
        self.assertEqual(components[0].part_id, "test-r1")
        self.assertIsNone(components[1].part_id)
        self.assertIn("${KIPRJMOD}/test-only.step", self.board.read_text())
        manifest = read_model(self.manifest_path, ProjectManifest)
        self.assertIn("test-r1", manifest.component_identity.part_ids)
        self.assertFalse(manifest.component_identity.required)
        prefs = read_model(self.preferences, PurchasingPreferences)
        self.assertEqual((prefs.boards, prefs.spare_percent, prefs.spare_minimum), (7, 10, 3))
        self.assertEqual(prefs.digikey_skus, {"test-r1": "541-TEST-ND"})
        self.assertFalse(applied.purchase_authorized)
        self.assertFalse(applied.build_authorized)

    def test_unlocked_wrong_project_removed_binding_and_duplicate_selection_block(self) -> None:
        selected = self.draft()
        original = selected.read_text()
        spec = read_model(selected, PartSelectionMap)
        for bad in (
            spec.model_copy(update={"project_id": "different"}),
            spec.model_copy(update={"preconditions": {}}),
            spec.model_copy(
                update={
                    "assignments": (PartSelectionAssignment(reference="R2", part_id="test-r1"),)
                }
            ),
            spec.model_copy(
                update={
                    "assignments": (PartSelectionAssignment(reference="R1", part_id="missing"),)
                }
            ),
            spec.model_copy(update={"assignments": (*spec.assignments, *spec.assignments)}),
        ):
            with self.subTest(bad=bad):
                selected.write_text(bad.model_dump_json(), encoding="utf-8")
                report = selection(self.root, self.project_id, selected, self.receipt())
                self.assertEqual(report.status, "BLOCKED")
        selected.write_text(original, encoding="utf-8")
        self.assertEqual(
            selection(self.root, self.project_id, selected, self.receipt(), apply=True).status,
            "BLOCKED",
        )

    def test_all_source_policy_model_and_absent_preferences_drift_block(self) -> None:
        selected = self.draft()
        for path in (
            self.schematic,
            self.board,
            self.model,
            self.catalog_path,
            self.root / "catalog/libraries.json",
            self.manifest_path,
            self.root / "examples/projects/passive-signal-reference/project.json",
        ):
            with self.subTest(path=path):
                before = path.read_bytes()
                path.write_bytes(before + b"\n")
                result = selection(self.root, self.project_id, selected, self.receipt())
                self.assertEqual(result.status, "BLOCKED")
                path.write_bytes(before)
        write_model(self.preferences, PurchasingPreferences(boards=99))
        result = selection(self.root, self.project_id, selected, self.receipt())
        self.assertEqual(result.status, "BLOCKED")
        self.assertIn("preconditions", " ".join(result.issues))

    def test_locked_after_hashes_and_assignments_cannot_be_changed(self) -> None:
        report = selection(self.root, self.project_id, self.draft(), self.receipt())
        assert report.locked_map is not None
        path = Path(report.locked_map)
        locked = read_model(path, PartSelectionMap)
        write_model(
            path,
            locked.model_copy(
                update={"after_hashes": {name: "0" * 64 for name in locked.after_hashes}}
            ),
        )
        result = selection(self.root, self.project_id, path, self.receipt(), apply=True)
        self.assertEqual(result.status, "BLOCKED")
        self.assertIn("recalculated", " ".join(result.issues))
        self.assertFalse(self.preferences.exists())

    def test_transaction_rolls_back_every_applied_file_when_replace_fails(self) -> None:
        report = selection(self.root, self.project_id, self.draft(), self.receipt())
        assert report.locked_map is not None
        originals = {
            path: path.read_bytes() for path in (self.schematic, self.board, self.manifest_path)
        }
        actual_replace = os.replace
        calls = 0

        def fail_second(source: Path, destination: Path) -> None:
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("simulated replacement failure")
            actual_replace(source, destination)

        with patch("kicad_tooling.hwrepo.part_picker.os.replace", side_effect=fail_second):
            result = selection(
                self.root, self.project_id, Path(report.locked_map), self.receipt(), apply=True
            )
        self.assertEqual(result.status, "BLOCKED")
        self.assertFalse(self.preferences.exists())
        self.assertEqual({path: path.read_bytes() for path in originals}, originals)

    def test_inputs_rechecked_between_mutations_and_external_drift_is_not_reverted(self) -> None:
        report = selection(self.root, self.project_id, self.draft(), self.receipt())
        assert report.locked_map is not None
        schematic = self.schematic.read_bytes()
        actual_replace = os.replace
        changed = False

        def mutate_catalog(source: Path, destination: Path) -> None:
            nonlocal changed
            actual_replace(source, destination)
            if not changed:
                changed = True
                self.catalog_path.write_bytes(self.catalog_path.read_bytes() + b"\n")

        with patch("kicad_tooling.hwrepo.part_picker.os.replace", side_effect=mutate_catalog):
            result = selection(
                self.root, self.project_id, Path(report.locked_map), self.receipt(), apply=True
            )
        self.assertEqual(result.status, "BLOCKED")
        self.assertFalse(self.preferences.exists())
        self.assertEqual(self.schematic.read_bytes(), schematic)
        self.assertTrue(self.catalog_path.read_bytes().endswith(b"\n\n"))

    def test_pending_footprint_can_resume_after_f8_without_guessing_a_model(self) -> None:
        assert self.part.cad is not None
        self.part = self.part.model_copy(
            update={"cad": self.part.cad.model_copy(update={"footprint": "Pilot:R_New"})}
        )
        self.set_parts(self.part)
        new_footprint = self.island / "kicad/Pilot.pretty/R_New.kicad_mod"
        new_footprint.write_text(
            (self.island / "kicad/Pilot.pretty/R_Test.kicad_mod")
            .read_text()
            .replace('(footprint "R_Test"', '(footprint "R_New"'),
            encoding="utf-8",
        )
        manifest = read_model(self.manifest_path, ProjectManifest)
        write_model(
            self.manifest_path,
            manifest.model_copy(
                update={
                    "required_inputs": (
                        *manifest.required_inputs,
                        "kicad/Pilot.pretty/R_New.kicad_mod",
                    ),
                }
            ),
        )
        preview = selection(self.root, self.project_id, self.draft(), self.receipt())
        self.assertEqual(preview.pending_references, ("R1",), preview.issues)
        assert preview.locked_map is not None
        applied = selection(
            self.root, self.project_id, Path(preview.locked_map), self.receipt(), apply=True
        )
        self.assertEqual(applied.status, "APPLIED_NEEDS_PCB_UPDATE", applied.issues)
        self.assertNotIn("test-only.step", self.board.read_text())
        # Simulate only the explicit footprint replacement performed by KiCad F8.
        self.board.write_text(
            self.board.read_text().replace(
                '(footprint "Pilot:R_Test"', '(footprint "Pilot:R_New"', 1
            ),
            encoding="utf-8",
        )
        resumed = resume_selection(self.root, self.project_id, self.receipt())
        self.assertEqual(resumed.status, "PLAN", resumed.issues)
        self.assertEqual(resumed.pending_references, ())
        self.assertEqual(len(resumed.edits), 1)
        assert resumed.locked_map is not None
        finished = selection(
            self.root, self.project_id, Path(resumed.locked_map), self.receipt(), apply=True
        )
        self.assertEqual(finished.status, "APPLIED", finished.issues)
        self.assertIn("${KIPRJMOD}/test-only.step", self.board.read_text())

    def test_undeclared_models_and_unsafe_output_do_not_bypass_capture(self) -> None:
        manifest = read_model(self.manifest_path, ProjectManifest)
        write_model(
            self.manifest_path,
            manifest.model_copy(
                update={
                    "required_inputs": tuple(
                        name for name in manifest.required_inputs if name != "kicad/test-only.step"
                    ),
                }
            ),
        )
        report = self.picker()
        self.assertEqual(report.status, "BLOCKED")
        self.assertIn("Declare reviewed model assets", " ".join(report.issues))
        report = create_picker(self.root, self.project_id, self.island / "docs", PickerRunner())
        self.assertEqual(report.status, "BLOCKED")
        self.assertFalse((self.island / "docs/selection-draft.json").exists())

    def test_saved_supplier_conflicts_require_review_and_resume_needs_selection(self) -> None:
        write_model(
            self.preferences, PurchasingPreferences(digikey_skus={"test-r1": "DIFFERENT-ND"})
        )
        report = selection(self.root, self.project_id, self.draft(), self.receipt())
        self.assertEqual(report.status, "BLOCKED")
        self.assertIn("conflicts", " ".join(report.issues))
        resumed = resume_selection(self.root, self.project_id, self.receipt())
        self.assertEqual(resumed.status, "BLOCKED")
        self.assertIn("choose parts", " ".join(resumed.issues))

    def test_manifest_semantics_preserved_outside_declared_part_and_model_inputs(self) -> None:
        original = json.loads(self.manifest_path.read_text())
        report = selection(self.root, self.project_id, self.draft(), self.receipt())
        manifest_edit = next(
            edit
            for edit in report.edits
            if edit.path == self.manifest_path.relative_to(self.root).as_posix()
        )
        updated = json.loads(manifest_edit.after)
        self.assertEqual(set(original), set(updated))
        for key in original:
            if key not in {"component_identity", "required_inputs", "shared_inputs"}:
                self.assertEqual(original[key], updated[key])

    def test_selection_contract_rejects_schema_type_unknowns_and_missing_preconditions(
        self,
    ) -> None:
        selected = self.draft()
        original = selected.read_text()
        spec = read_model(selected, PartSelectionMap)
        prefs_name = self.preferences.relative_to(self.root).as_posix()
        removed = {name: value for name, value in spec.preconditions.items() if name != prefs_name}
        selected.write_text(
            spec.model_copy(update={"preconditions": removed}).model_dump_json(), encoding="utf-8"
        )
        result = selection(self.root, self.project_id, selected, self.receipt())
        self.assertEqual(result.status, "BLOCKED")
        for raw in (
            original.replace('"schema_version": "1"', '"schema_version": "2"'),
            original.replace('"locked": false', '"locked": "true"'),
            original.rstrip()[:-1] + ', "unexpected": 1}',
            original.replace(
                '"project_id": "controller"',
                '"project_id": "controller", "project_id": "controller"',
            ),
        ):
            with self.subTest(raw=raw):
                selected.write_text(raw, encoding="utf-8")
                self.assertEqual(
                    selection(self.root, self.project_id, selected, self.receipt()).status,
                    "BLOCKED",
                )

    def test_handcrafted_selection_cannot_skip_inventory_or_pick_unsupported_symbol(self) -> None:
        selected = self.draft()
        before = self.schematic.read_bytes()
        # A forger can fill current hashes but cannot bypass source inventory policy.
        from kicad_tooling.hwrepo.part_picker import _snapshot

        manifest = read_model(self.manifest_path, ProjectManifest)
        write_model(
            self.manifest_path,
            manifest.model_copy(
                update={
                    "required_inputs": tuple(
                        name for name in manifest.required_inputs if name != "kicad/test-only.step"
                    ),
                }
            ),
        )
        spec = read_model(selected, PartSelectionMap)
        spec = spec.model_copy(update={"preconditions": _snapshot(self.root, self.project_id)})
        selected.write_text(spec.model_dump_json(), encoding="utf-8")
        result = selection(self.root, self.project_id, selected, self.receipt())
        self.assertEqual(result.status, "BLOCKED")
        self.assertIn("inventory", " ".join(result.issues))
        self.assertEqual(self.schematic.read_bytes(), before)

    def test_picker_disables_offboard_symbols_before_selection(self) -> None:
        self.schematic.write_bytes(
            self.schematic.read_bytes().replace(
                b"(in_bom yes) (on_board yes) (dnp no)", b"(in_bom yes) (on_board no) (dnp no)", 1
            )
        )
        report = self.picker()
        self.assertEqual(report.status, "NEEDS_CATALOG", report.issues)
        self.assertEqual(report.items[0].choice_ids, ())
        self.assertIn("off-board", " ".join(report.items[0].issues).lower())

    def replacement_draft(self, shared_old_part: bool) -> Path:
        from kicad_tooling.hwrepo.part_picker import _snapshot

        source = self.schematic.read_text()
        references = ("R1", "R2") if shared_old_part else ("R1",)
        for reference in references:
            source = source.replace(
                f'(property "Reference" "{reference}"',
                '(property "PART_ID" "old-part" (at 0 0 0) (effects (font (size 1 1)) hide))\n'
                + f'    (property "Reference" "{reference}"',
            )
        self.schematic.write_text(source, encoding="utf-8")
        old = self.part.model_copy(update={"id": "old-part", "mpn": "OLD-PART-123", "cad": None})
        unrelated = self.part.model_copy(
            update={"id": "unrelated", "mpn": "UNRELATED-123", "cad": None}
        )
        self.set_parts(self.part, old, unrelated)
        manifest = read_model(self.manifest_path, ProjectManifest)
        write_model(
            self.manifest_path,
            manifest.model_copy(
                update={
                    "component_identity": ComponentIdentity(
                        required=True, part_ids=("old-part", "unrelated")
                    ),
                }
            ),
        )
        write_model(
            self.preferences,
            PurchasingPreferences(
                boards=8,
                spare_percent=15,
                spare_minimum=4,
                digikey_skus={"old-part": "OLD-ND", "unrelated": "UNRELATED-ND"},
            ),
        )
        spec = PartSelectionMap(
            project_id=self.project_id,
            preconditions=_snapshot(self.root, self.project_id),
            assignments=(PartSelectionAssignment(reference="R1", part_id="test-r1"),),
        )
        selected = self.root / "build/replacement.json"
        selected.parent.mkdir(parents=True, exist_ok=True)
        selected.write_text(spec.model_dump_json(indent=2), encoding="utf-8")
        return selected

    def test_replacing_last_use_retires_only_its_manifest_id_and_supplier_override(self) -> None:
        selected = self.replacement_draft(shared_old_part=False)
        contract = self.island / "tests/contract.json"
        contract_before = contract.read_bytes()
        preview = selection(self.root, self.project_id, selected, self.receipt())
        self.assertEqual(preview.status, "PLAN", preview.issues)
        self.assertIn("Review independent engineering requirements", " ".join(preview.issues))
        assert preview.locked_map is not None
        result = selection(
            self.root, self.project_id, Path(preview.locked_map), self.receipt(), apply=True
        )
        self.assertEqual(result.status, "APPLIED", result.issues)
        manifest = read_model(self.manifest_path, ProjectManifest)
        self.assertEqual(manifest.component_identity.part_ids, ("test-r1", "unrelated"))
        self.assertTrue(manifest.component_identity.required)
        prefs = read_model(self.preferences, PurchasingPreferences)
        self.assertEqual(
            prefs.digikey_skus, {"test-r1": "541-TEST-ND", "unrelated": "UNRELATED-ND"}
        )
        self.assertEqual((prefs.boards, prefs.spare_percent, prefs.spare_minimum), (8, 15, 4))
        self.assertEqual(contract.read_bytes(), contract_before)

    def test_replacing_one_shared_use_preserves_old_id_and_supplier_for_unchanged_reference(
        self,
    ) -> None:
        selected = self.replacement_draft(shared_old_part=True)
        preview = selection(self.root, self.project_id, selected, self.receipt())
        self.assertEqual(preview.status, "PLAN", preview.issues)
        assert preview.locked_map is not None
        result = selection(
            self.root, self.project_id, Path(preview.locked_map), self.receipt(), apply=True
        )
        self.assertEqual(result.status, "APPLIED", result.issues)
        manifest = read_model(self.manifest_path, ProjectManifest)
        self.assertEqual(manifest.component_identity.part_ids, ("old-part", "test-r1", "unrelated"))
        prefs = read_model(self.preferences, PurchasingPreferences)
        self.assertEqual(prefs.digikey_skus["old-part"], "OLD-ND")
        self.assertEqual(prefs.digikey_skus["unrelated"], "UNRELATED-ND")
        self.assertEqual(read_cad_components(self.root, self.project_id)[1].part_id, "old-part")

    def test_excluded_reference_still_preserves_its_part_declaration(self) -> None:
        selected = self.replacement_draft(shared_old_part=True)
        source = self.schematic.read_text()
        # R2 is the second top-level symbol; keep its explicit old PART_ID even when DNP.
        position = source.index('(property "Reference" "R2"')
        prefix = source[:position]
        marker = prefix.rfind("(dnp no)")
        self.schematic.write_text(
            source[:marker] + source[marker:].replace("(dnp no)", "(dnp yes)", 1), encoding="utf-8"
        )
        from kicad_tooling.hwrepo.part_picker import _snapshot

        spec = read_model(selected, PartSelectionMap)
        selected.write_text(
            spec.model_copy(
                update={"preconditions": _snapshot(self.root, self.project_id)}
            ).model_dump_json(),
            encoding="utf-8",
        )
        preview = selection(self.root, self.project_id, selected, self.receipt())
        self.assertEqual(preview.status, "PLAN", preview.issues)
        manifest_edit = next(
            edit
            for edit in preview.edits
            if edit.path == self.manifest_path.relative_to(self.root).as_posix()
        )
        self.assertIn(
            "old-part",
            ProjectManifest.model_validate_json(manifest_edit.after).component_identity.part_ids,
        )
