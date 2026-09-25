"""Automatic CAD plans preserve geometry and cannot apply stale or altered sources."""
from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError

from kicad_tooling.hwrepo import auto_cad
from kicad_tooling.hwrepo.cad_assets import resolve_footprint
from kicad_tooling.hwrepo.contracts import read_model
from kicad_tooling.hwrepo.models import AutoCadPlan, AutoCadReport, ProjectManifest
from kicad_tooling.hwrepo.parts_workflow import new_receipt
from tests.support import reference_root
from tests.test_cad_assets import FOOTPRINT, MODEL, TRANSFORM, board


class AutoCadTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="auto-cad-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.root = self.base / "repository"
        shutil.copytree(reference_root(), self.root, ignore=shutil.ignore_patterns(".git"))
        self.library = self.base / "library"
        member = self.library / "footprints/Paired.pretty/TwoPin.kicad_mod"
        member.parent.mkdir(parents=True)
        member.write_text(FOOTPRINT)
        model = self.library / "3dmodels/Paired.3dshapes/TwoPin.step"
        model.parent.mkdir(parents=True)
        model.write_bytes(b"ISO-10303-21;\nTEST ONLY\nEND-ISO-10303-21;\n")
        self.board = self.root / "examples/projects/controller/kicad/controller.kicad_pcb"
        self.board.write_text(board(90, True))
        self.pair = resolve_footprint(self.root, "controller", "Paired:TwoPin", self.library)
        resolver = patch("kicad_tooling.hwrepo.auto_cad._resolve", return_value=self.pair)
        resolver.start()
        self.addCleanup(resolver.stop)

    def receipt(self) -> Path:
        return new_receipt(self.root, "controller", None)

    def plan(self) -> AutoCadReport:
        return auto_cad.plan(self.root, "controller", self.receipt())

    def apply(self, report: AutoCadReport) -> AutoCadReport:
        assert report.plan_path is not None
        return auto_cad.apply(self.root, "controller", Path(report.plan_path), self.receipt())

    def test_imports_paired_model_and_inventory_without_moving_geometry(self) -> None:
        before = self.board.read_text()
        report = self.plan()
        self.assertEqual(report.status, "PLAN", report.issues)
        self.assertEqual(self.board.read_text(), before)
        self.assertEqual(report.items[0].status, "READY")
        applied = self.apply(report)
        self.assertEqual(applied.status, "APPLIED", applied.issues)
        self.assertIn(TRANSFORM, self.board.read_text())
        after_without_model = self.board.read_text().split('\n    (model ')[0] + self.board.read_text().split(TRANSFORM + ')\n  ')[1]
        self.assertEqual(after_without_model, before)
        manifest = read_model(self.root / "examples/projects/controller/project.json", ProjectManifest)
        self.assertTrue(any(path.endswith(".step") for path in manifest.required_inputs))
        self.assertTrue(any(path.endswith("provenance.json") for path in manifest.required_inputs))
        rerun = self.plan()
        self.assertEqual(rerun.files, ())
        self.assertEqual(rerun.items[0].status, "ALREADY_PRESENT")

    def test_identical_assets_from_another_machine_preserve_historical_provenance(self) -> None:
        applied = self.apply(self.plan())
        self.assertEqual(applied.status, "APPLIED")
        provenance = next((self.board.parent / "cad").rglob("provenance.json"))
        before = provenance.read_bytes()
        relocated = replace(self.pair, source_path=Path("/another-machine/footprint.kicad_mod"),
            provenance="Identical library on a different machine",
            models=(replace(self.pair.models[0], source_path=Path("/another-machine/TwoPin.step")),))
        with patch("kicad_tooling.hwrepo.auto_cad._resolve", return_value=relocated):
            report = self.plan()
        self.assertEqual(report.files, (), report.issues)
        self.assertEqual(report.items[0].status, "ALREADY_PRESENT")
        self.assertEqual(provenance.read_bytes(), before)

    def test_geometry_mismatch_remains_actionable_and_unchanged(self) -> None:
        self.board.write_text(board().replace("0 2.54", "0 10"))
        before = self.board.read_bytes()
        report = self.plan()
        self.assertEqual(report.status, "NEEDS_REVIEW")
        self.assertIn("geometry", report.issues[0])
        self.assertIsNone(report.plan_path)
        self.assertEqual(before, self.board.read_bytes())

    def test_stale_board_rejects_whole_plan(self) -> None:
        report = self.plan()
        self.board.write_text(self.board.read_text().replace("21.7", "22.7"))
        result = self.apply(report)
        self.assertEqual(result.status, "BLOCKED")
        self.assertIn("changed", " ".join(result.issues))
        self.assertFalse((self.board.parent / "cad").exists())

    def test_tampered_plan_hash_or_source_asset_is_recalculated(self) -> None:
        report = self.plan()
        assert report.plan_path is not None
        plan_path = Path(report.plan_path)
        spec = read_model(plan_path, AutoCadPlan)
        altered = spec.model_copy(update={"after_hashes": {"README.md": "a" * 64}})
        plan_path.write_text(altered.model_dump_json())
        self.assertEqual(self.apply(report).status, "BLOCKED")
        plan_path.write_text(spec.model_dump_json())
        changed = replace(self.pair, models=(replace(self.pair.models[0], source_bytes=b"changed"),))
        with patch("kicad_tooling.hwrepo.auto_cad._resolve", return_value=changed):
            self.assertEqual(self.apply(report).status, "BLOCKED")
        self.assertNotIn("(model", self.board.read_text())

    def test_mid_transaction_write_failure_rolls_back_every_source(self) -> None:
        report = self.plan()
        before = {path: path.read_bytes() for path in self.root.rglob("*") if path.is_file() and "build" not in path.parts}
        replace_file = os.replace
        calls = 0

        def fail_once(source: str | Path, target: str | Path) -> None:
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("test interruption")
            replace_file(source, target)

        with patch("kicad_tooling.hwrepo.auto_cad.os.replace", side_effect=fail_once):
            result = self.apply(report)
        self.assertEqual(result.status, "BLOCKED")
        after = {path: path.read_bytes() for path in self.root.rglob("*") if path.is_file() and "build" not in path.parts}
        self.assertEqual(after, before)

    def test_existing_wrong_model_is_not_labeled_aligned(self) -> None:
        self.board.write_text(board(model=f'(model "{MODEL}" (rotate (xyz 0 0 37)))'))
        report = self.plan()
        self.assertEqual(report.status, "NEEDS_REVIEW")
        self.assertIn("existing 3D assignment", report.issues[0])

    def test_legacy_modules_are_not_silently_reported_as_an_empty_board(self) -> None:
        self.board.write_text(board().replace('(footprint "Paired:TwoPin"', '(module "Paired:TwoPin"'))
        report = self.plan()
        self.assertEqual(report.status, "BLOCKED")
        self.assertIn("legacy", report.issues[0])

    def test_report_and_plan_are_strict_versioned_contracts(self) -> None:
        report = self.plan()
        self.assertEqual(AutoCadReport.model_validate_json(report.model_dump_json()), report)
        assert report.plan_path is not None
        spec = read_model(Path(report.plan_path), AutoCadPlan)
        self.assertEqual(AutoCadPlan.model_validate_json(spec.model_dump_json()), spec)
        for raw in (spec.model_dump_json().replace('"1"', '"2"', 1),
                    spec.model_dump_json()[:-1] + ',"unexpected":1}',
                    spec.model_dump_json().replace('"controller"', '123')):
            with self.assertRaises(ValidationError):
                AutoCadPlan.model_validate_json(raw)


if __name__ == "__main__":
    unittest.main()
