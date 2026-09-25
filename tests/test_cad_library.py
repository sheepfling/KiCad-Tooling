"""Sourced libraries remain source-bound and never rewrite an existing design."""
from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError

from kicad_tooling.hwrepo import cad_library
from kicad_tooling.hwrepo.cad_assets import resolve_footprint
from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.models import (
    CadImportPlan,
    CadImportReport,
    CadSourceBundle,
    CadSourceFile,
    ProjectManifest,
)
from kicad_tooling.hwrepo.parts_workflow import new_receipt
from tests.support import reference_root
from tests.test_cad_assets import PADS, TRANSFORM

SYMBOL = '''(kicad_symbol_lib (version 20231120) (generator "TEST_ONLY")
  (symbol "TwoPin"
    (property "Reference" "J") (property "Value" "TEST_ONLY")
    (property "Footprint" "part:TwoPin")
    (property "Manufacturer" "Test Fixture") (property "MPN" "TEST-ONLY-1")
    (property "LCSC Part" "C1234")
    (symbol "TwoPin_0_1")
    (symbol "TwoPin_1_1"
      (pin passive line (at 0 0 0) (length 2.54) (name "ONE") (number "1"))
      (pin passive line (at 0 2.54 0) (length 2.54) (name "TWO") (number "2")))))
'''
MODEL_PATH = 'library/part.3dshapes/TwoPin.wrl'
FOOTPRINT = (f'(footprint "TwoPin" (layer "F.Cu") {PADS} '
             f'(model "${{KIPRJMOD}}/{MODEL_PATH}" {TRANSFORM}))\n')
WRL = b'#VRML V2.0 utf8\n# TEST ONLY\nShape { geometry Box { size 1 1 1 } }\n'


def sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


class CadLibraryTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="cad-library-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.root = self.base / "repository"
        shutil.copytree(reference_root(), self.root, ignore=shutil.ignore_patterns(".git"))
        self.island = self.root / "examples/projects/controller"
        self.bundle_dir = self.base / "bundle"
        self.bundle_dir.mkdir()
        self.symbol_path = self.bundle_dir / "library/part.kicad_sym"
        self.footprint_path = self.bundle_dir / "library/part.pretty/TwoPin.kicad_mod"
        self.model_path = self.bundle_dir / MODEL_PATH
        for path, content in ((self.symbol_path, SYMBOL.encode()),
                              (self.footprint_path, FOOTPRINT.encode()), (self.model_path, WRL)):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        self.bundle = CadSourceBundle(
            supplier_id="C1234", manufacturer="Test Fixture", mpn="TEST-ONLY-1", package="TwoPin",
            symbol_file="library/part.kicad_sym", symbol_name="TwoPin",
            footprint_file="library/part.pretty/TwoPin.kicad_mod", footprint_name="TwoPin",
            model_file=MODEL_PATH, files=(),
            source_url="https://easyeda.com/api/products/C1234/components",
            source_sha256="a" * 64, retrieved_at="2026-09-25T00:00:00Z",
        )
        self.save_bundle()

    def save_bundle(self) -> None:
        self.bundle = self.bundle.model_copy(update={"files": tuple(
            CadSourceFile(path=path.relative_to(self.bundle_dir).as_posix(), sha256=sha(path.read_bytes()))
            for path in sorted(self.bundle_dir.rglob("*"))
            if path.is_file() and path.name != "bundle.json"
        )})
        write_model(self.bundle_dir / "bundle.json", self.bundle)

    def receipt(self) -> Path:
        return new_receipt(self.root, "controller", None)

    def plan(self) -> CadImportReport:
        return cad_library.plan(self.root, "controller", self.bundle_dir, self.receipt())

    def apply(self, report: CadImportReport) -> CadImportReport:
        assert report.plan_path is not None
        return cad_library.apply(self.root, "controller", Path(report.plan_path), self.receipt())

    def test_imports_complete_native_library_without_touching_design_or_catalog(self) -> None:
        protected = {path: path.read_bytes() for path in (
            self.island / "kicad/controller.kicad_sch", self.island / "kicad/controller.kicad_pcb",
            self.island / "tests/contract.json", self.root / "catalog/parts.json")}
        report = self.plan()
        self.assertEqual(report.status, "PLAN", report.issues)
        self.assertIsNotNone(report.check)
        assert report.check is not None and report.footprint_id is not None
        self.assertEqual(report.check.symbol_pins, ("1", "2"))
        self.assertFalse(report.check.physical_fit_verified)
        self.assertIn("part.kicad_sym", report.diff)
        self.assertFalse((self.island / "kicad/cad").exists())
        applied = self.apply(report)
        self.assertEqual(applied.status, "APPLIED", applied.issues)
        pair = resolve_footprint(self.root, "controller", report.footprint_id)
        self.assertEqual(pair.models[0].source_bytes, WRL)
        self.assertIn(TRANSFORM, pair.models[0].model_expression)
        self.assertTrue(pair.models[0].source_model_reference.startswith("${KIPRJMOD}/cad/sourced/"))
        symbol = next((self.island / "kicad/cad").rglob("part.kicad_sym")).read_text()
        self.assertIn(f'(property "Footprint" "{report.footprint_id}")', symbol)
        self.assertIn('(lib (name "Pilot")', (self.island / "kicad/fp-lib-table").read_text())
        manifest = read_model(self.island / "project.json", ProjectManifest)
        for name in report.files:
            if name != "examples/projects/controller/project.json":
                self.assertIn(Path(name).relative_to("examples/projects/controller").as_posix(), manifest.required_inputs)
        self.assertEqual({path: path.read_bytes() for path in protected}, protected)
        repeated = self.plan()
        self.assertEqual(repeated.status, "PLAN", repeated.issues)
        self.assertEqual(repeated.files, ())

    def test_legacy_provider_header_is_normalized_without_rewriting_geometry(self) -> None:
        source = FOOTPRINT.replace('(footprint "TwoPin"', '(module easyeda2kicad:TwoPin')
        self.footprint_path.write_text(source)
        self.save_bundle()
        report = self.plan()
        applied = self.apply(report)
        self.assertEqual(applied.status, "APPLIED", applied.issues)
        assert report.footprint_id is not None
        pair = resolve_footprint(self.root, "controller", report.footprint_id)
        self.assertTrue(pair.source_text.startswith('(footprint "TwoPin"'))
        self.assertIn(PADS, pair.source_text)
        self.assertIn(TRANSFORM, pair.source_text)
        self.assertEqual(pair.pads[0].number, "1")
        self.assertEqual(pair.pads[1].number, "2")
        self.assertEqual(pair.pads[1].y, 2.54)

    def test_raw_step_is_hashed_but_never_installed_or_substituted(self) -> None:
        raw = self.bundle_dir / "source/raw.step"
        raw.parent.mkdir()
        raw.write_bytes(b"ISO-10303-21;\nTEST ONLY\nEND-ISO-10303-21;\n")
        self.save_bundle()
        applied = self.apply(self.plan())
        self.assertEqual(applied.status, "APPLIED", applied.issues)
        self.assertEqual(tuple((self.island / "kicad/cad").rglob("*.step")), ())
        self.assertFalse((self.island / "kicad/cad/source").exists())
        source = next((self.island / "kicad/cad").rglob("SOURCE.json"))
        self.assertEqual(read_model(source, CadSourceBundle), self.bundle)

    def test_mismatched_identity_blocks_without_source_writes(self) -> None:
        for old, new in (("Test Fixture", "Different Manufacturer"), ("TEST-ONLY-1", "OTHER-MPN"),
                         ("C1234", "C9999"), ("part:TwoPin", "part:OtherFootprint")):
            with self.subTest(field=old):
                self.symbol_path.write_text(SYMBOL.replace(old, new))
                self.save_bundle()
                report = self.plan()
                self.assertEqual(report.status, "BLOCKED")
                self.assertIn("differ", " ".join(report.issues))
                self.assertFalse((self.island / "kicad/cad").exists())

    def test_pin_number_mismatch_is_not_alignment_evidence(self) -> None:
        self.symbol_path.write_text(SYMBOL.replace('(number "2")', '(number "3")'))
        self.save_bundle()
        checked = cad_library.inspect_bundle(self.bundle_dir, self.bundle)
        self.assertEqual(checked.status, "BLOCKED")
        self.assertIn("pin numbers differ", checked.issues[0])
        self.assertFalse(checked.physical_fit_verified)

    def test_stacked_pins_repeated_pads_and_unplated_mechanical_holes_are_supported(self) -> None:
        self.symbol_path.write_text(SYMBOL.replace(
            '(pin passive line (at 0 0 0)',
            '(pin passive line (at 0 0 0) (length 2.54) (name "ONE") (number "1"))\n'
            '      (pin passive line (at 0 0 0)'))
        extra = ('(pad "1" smd rect (at 0 4) (size 1 1) (layers "F.Cu" "F.Paste" "F.Mask"))'
                 '(pad "" np_thru_hole circle (at 9 9) (size 2 2) (drill 2) (layers "*.Cu" "*.Mask"))')
        self.footprint_path.write_text(FOOTPRINT[:-2] + extra + ")\n")
        self.save_bundle()
        checked = cad_library.inspect_bundle(self.bundle_dir, self.bundle)
        self.assertEqual(checked.status, "READY", checked.issues)
        self.assertEqual(checked.footprint_pads, ("1", "2"))

    def test_missing_hidden_or_escaping_model_is_blocked(self) -> None:
        variants = (FOOTPRINT.replace(f'(model "${{KIPRJMOD}}/{MODEL_PATH}" {TRANSFORM})', ""),
                    FOOTPRINT.replace(TRANSFORM, TRANSFORM + " (hide yes)"),
                    FOOTPRINT.replace(MODEL_PATH, "../outside.wrl"),
                    FOOTPRINT.replace(MODEL_PATH, "library/part.3dshapes/TwoPin.step"))
        for source in variants:
            with self.subTest(source=source):
                self.footprint_path.write_text(source)
                self.save_bundle()
                self.assertEqual(cad_library.inspect_bundle(self.bundle_dir, self.bundle).status, "BLOCKED")

    def test_model_must_be_native_and_self_contained(self) -> None:
        for content in (b"<html>Access denied</html>", b"#VRML V2.0 utf8\n",
                        WRL + b'Inline { url "https://example.invalid/other.wrl" }'):
            with self.subTest(content=content):
                self.model_path.write_bytes(content)
                self.save_bundle()
                self.assertEqual(cad_library.inspect_bundle(self.bundle_dir, self.bundle).status, "BLOCKED")

    def test_changed_and_extra_source_files_fail_complete_inventory_check(self) -> None:
        self.model_path.write_bytes(WRL + b"# changed")
        checked = cad_library.inspect_bundle(self.bundle_dir, self.bundle)
        self.assertIn("changed", checked.issues[0])
        self.model_path.write_bytes(WRL)
        extra = self.bundle_dir / "unrecorded.txt"
        extra.write_text("unrecorded")
        checked = cad_library.inspect_bundle(self.bundle_dir, self.bundle)
        self.assertIn("complete inventory", checked.issues[0])

    def test_duplicate_manifest_paths_cannot_silently_overwrite_hashes(self) -> None:
        self.bundle = self.bundle.model_copy(update={"files": (*self.bundle.files, self.bundle.files[0])})
        write_model(self.bundle_dir / "bundle.json", self.bundle)
        checked = cad_library.inspect_bundle(self.bundle_dir, self.bundle)
        self.assertIn("repeats", checked.issues[0])

    def test_unsafe_manifest_paths_and_symlinked_assets_are_rejected(self) -> None:
        for unsafe in ("../outside.wrl", "/tmp/model.wrl", "C:/model.wrl", "library\\model.wrl"):
            with self.subTest(path=unsafe):
                altered = self.bundle.model_copy(update={"model_file": unsafe})
                write_model(self.bundle_dir / "bundle.json", altered)
                self.assertEqual(cad_library.inspect_bundle(self.bundle_dir, altered).status, "BLOCKED")
        write_model(self.bundle_dir / "bundle.json", self.bundle)
        outside = self.base / "model.wrl"
        self.model_path.rename(outside)
        try:
            self.model_path.symlink_to(outside)
        except OSError:
            self.skipTest("Host cannot create symlinks")
        checked = cad_library.inspect_bundle(self.bundle_dir, self.bundle)
        self.assertEqual(checked.status, "BLOCKED")
        self.assertIn("Linked", checked.issues[0])

    def test_case_conflicting_manifest_paths_are_rejected_on_all_hosts(self) -> None:
        alias = CadSourceFile(path=self.bundle.files[0].path.upper(), sha256=self.bundle.files[0].sha256)
        self.bundle = self.bundle.model_copy(update={"files": (*self.bundle.files, alias)})
        write_model(self.bundle_dir / "bundle.json", self.bundle)
        self.assertEqual(cad_library.inspect_bundle(self.bundle_dir, self.bundle).status, "BLOCKED")

    def test_oversized_recorded_source_is_rejected_before_read(self) -> None:
        with patch("kicad_tooling.hwrepo.cad_library._MAX_FILE", len(WRL) - 1):
            checked = cad_library.inspect_bundle(self.bundle_dir, self.bundle)
        self.assertEqual(checked.status, "BLOCKED")
        self.assertIn("size", checked.issues[0])

    def test_preview_locks_source_and_cached_bundle_bytes(self) -> None:
        report = self.plan()
        self.model_path.write_bytes(WRL + b"# changed")
        self.assertEqual(self.apply(report).status, "BLOCKED")
        self.model_path.write_bytes(WRL)
        self.bundle = self.bundle.model_copy(update={"retrieved_at": "changed"})
        write_model(self.bundle_dir / "bundle.json", self.bundle)
        self.assertEqual(self.apply(report).status, "BLOCKED")
        self.assertFalse((self.island / "kicad/cad").exists())

    def test_changed_board_or_forged_plan_rejects_apply(self) -> None:
        report = self.plan()
        assert report.plan_path is not None
        path = Path(report.plan_path)
        spec = read_model(path, CadImportPlan)
        write_model(path, spec.model_copy(update={"after_hashes": {"README.md": "a" * 64}}))
        self.assertEqual(self.apply(report).status, "BLOCKED")
        write_model(path, spec)
        board = self.island / "kicad/controller.kicad_pcb"
        board.write_bytes(board.read_bytes() + b"\n# user edit\n")
        self.assertEqual(self.apply(report).status, "BLOCKED")
        self.assertFalse((self.island / "kicad/cad").exists())

    def test_nickname_collision_is_not_overwritten(self) -> None:
        report = self.plan()
        assert report.symbol_id is not None
        nickname = report.symbol_id.split(":")[0]
        table = self.island / "kicad/sym-lib-table"
        before = table.read_text()
        table.write_text(before[:before.rfind(")")] + f'(lib (name "{nickname}")(type "KiCad")'
                         '(uri "${KIPRJMOD}/Pilot.kicad_sym")(options ""))\n)\n')
        blocked = self.plan()
        self.assertEqual(blocked.status, "BLOCKED")
        self.assertIn("nickname conflicts", " ".join(blocked.issues))
        self.assertFalse((self.island / "kicad/cad").exists())

    def test_mid_transaction_failure_restores_every_original_file(self) -> None:
        report = self.plan()
        before = {path: path.read_bytes() for path in self.island.rglob("*") if path.is_file()}
        original_replace = os.replace
        calls = 0

        def fail_once(source: str | Path, target: str | Path) -> None:
            nonlocal calls
            calls += 1
            if calls == 4:
                raise OSError("test interrupted import")
            original_replace(source, target)

        with patch("kicad_tooling.hwrepo.auto_cad.os.replace", side_effect=fail_once):
            applied = self.apply(report)
        self.assertEqual(applied.status, "BLOCKED")
        self.assertEqual({path: path.read_bytes() for path in self.island.rglob("*") if path.is_file()}, before)

    def test_strict_contracts_round_trip_and_reject_unknown_or_wrong_fields(self) -> None:
        report = self.plan()
        self.assertEqual(CadImportReport.model_validate_json(report.model_dump_json()), report)
        self.assertEqual(CadSourceBundle.model_validate_json(self.bundle.model_dump_json()), self.bundle)
        assert report.plan_path is not None
        spec = read_model(Path(report.plan_path), CadImportPlan)
        self.assertEqual(CadImportPlan.model_validate_json(spec.model_dump_json()), spec)
        for raw in (spec.model_dump_json().replace('"1"', '"2"', 1),
                    spec.model_dump_json()[:-1] + ',"unknown":true}',
                    spec.model_dump_json().replace('"controller"', '123')):
            with self.assertRaises(ValidationError):
                CadImportPlan.model_validate_json(raw)


if __name__ == "__main__":
    unittest.main()
