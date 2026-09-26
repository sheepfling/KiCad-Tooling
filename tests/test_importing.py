"""Import portability, isolation and failure recovery without external demo fixtures."""
from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.diagnostics import repository_guidance
from kicad_tooling.hwrepo.discovery import load_config, load_registry
from kicad_tooling.hwrepo.importing import import_project
from kicad_tooling.hwrepo.model_inventory import inspect_models
from kicad_tooling.hwrepo.models import (
    ComponentIdentity,
    PcbOnlyValidationContract,
    ProjectKind,
    ProjectManifest,
    ProjectTestContract,
)
from kicad_tooling.hwrepo.repository import cad_dependencies
from kicad_tooling.lint_registry import lint
from tests.support import initialize_git, reference_root


class ImportTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="import-workflow-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.root = self.base / "repository"
        shutil.copytree(reference_root(), self.root, ignore=shutil.ignore_patterns(".git", "build"))
        initialize_git(self.root)
        self.source = self.base / "Old board"
        self.source.mkdir()
        self.project = self.source / "Old board.kicad_pro"
        self.project.write_text("{}")
        self.project.with_suffix(".kicad_sch").write_text('(kicad_sch (property "Sheetfile" "sheets/channel.kicad_sch"))')
        self.project.with_suffix(".kicad_pcb").write_text("(kicad_pcb)")
        (self.source / "sheets").mkdir()
        (self.source / "sheets/channel.kicad_sch").write_text('(kicad_sch (property "Sheetfile" "../shared.kicad_sch"))')
        (self.source / "shared.kicad_sch").write_text("(kicad_sch)")
        (self.source / "symbols.kicad_sym").write_text("(kicad_symbol_lib)")
        (self.source / "LICENSE").write_text("Test fixture source")

    def run_import(self, dry_run: bool = False):
        return import_project(self.root, self.project, "battery-board", "kicad-10.0.5", dry_run)

    def test_preserves_native_bytes_spaces_hierarchy_and_dependencies_without_catalog_edit(self) -> None:
        before = {p.relative_to(self.source).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in self.source.rglob('*') if p.is_file()}
        catalog = (self.root / "catalog/projects.json").read_bytes()
        result = self.run_import()
        self.assertEqual(result.status, "PASS", result.issues)
        self.assertEqual(result.copied_sha256, before)
        island = self.root / result.directory
        manifest = read_model(island / "project.json", ProjectManifest)
        self.assertEqual(manifest.project, "kicad/Old board.kicad_pro")
        self.assertFalse(manifest.component_identity.required)
        self.assertEqual(set(manifest.required_inputs), {f"kicad/{name}" for name in before})
        for name, digest in before.items():
            self.assertEqual(hashlib.sha256((island / 'kicad' / name).read_bytes()).hexdigest(), digest)
            self.assertEqual(hashlib.sha256((self.source / name).read_bytes()).hexdigest(), digest)
        self.assertEqual((self.root / "catalog/projects.json").read_bytes(), catalog)
        self.assertIn("battery-board", {p.id for p in load_registry(self.root).projects})
        self.assertEqual(self.run_import().status, "FAIL")

    def test_dry_run_reports_working_exports_and_separate_projects_without_writes(self) -> None:
        for name in ("other.kicad_pro", "other.kicad_sch", "other.kicad_pcb", "old.gbr", ".DS_Store", "photo.png"):
            (self.source / name).write_text("excluded")
        nested = self.source / "child"; nested.mkdir()
        (nested / "child.kicad_pro").write_text("{}")
        result = self.run_import(True)
        self.assertEqual(result.status, "PASS", result.issues)
        self.assertFalse((self.root / result.directory).exists())
        self.assertIn("old.gbr", result.excluded)
        self.assertIn("other.kicad_pro", result.excluded)
        self.assertIn("child/child.kicad_pro", result.excluded)
        self.assertIn("photo.png", result.excluded)
        self.assertNotIn("other.kicad_sch", result.copied_sha256)

    def test_cli_never_silently_ignores_dry_run_on_another_command(self) -> None:
        result = subprocess.run((sys.executable, "-I", "-B", "-m", "kicad_tooling.template", "new-project",
            "--root", str(self.root), "--project-id", "dry-board", "--toolchain", "kicad-10.0.5", "--dry-run"),
            capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 2)
        self.assertIn("require import-project", result.stderr)
        self.assertFalse((self.root / "projects/dry-board").exists())

    def test_missing_or_escaping_sheets_fail_without_publishing(self) -> None:
        for name in ("missing.kicad_sch", "../outside.kicad_sch"):
            self.project.with_suffix(".kicad_sch").write_text(f'(property "Sheetfile" "{name}")')
            report = self.run_import()
            self.assertEqual(report.status, "FAIL")
            if name.startswith("../"):
                self.assertIn("outside the selected project directory", report.issues[0])
                self.assertIn("../outside.kicad_sch", report.issues[0])
            self.assertFalse((self.root / report.directory).exists())

    def test_pcb_only_import_is_inventoried_and_limited_to_board_validation(self) -> None:
        self.project.with_suffix(".kicad_sch").unlink()
        shutil.rmtree(self.source / "sheets")
        (self.source / "shared.kicad_sch").unlink()
        before = {
            path.relative_to(self.source).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in self.source.rglob("*") if path.is_file()
        }
        dry_run = self.run_import(True)
        self.assertEqual(dry_run.status, "PASS", dry_run.issues)
        self.assertFalse((self.root / dry_run.directory).exists())
        self.assertIn("authoritative schematic", dry_run.next_step)
        self.assertIn("kicad_tooling.verify --project", dry_run.next_step)
        result = self.run_import()
        self.assertEqual(result.status, "PASS", result.issues)
        island = self.root / result.directory
        manifest = read_model(island / "project.json", ProjectManifest)
        contract = read_model(island / "tests/contract.json", ProjectTestContract)
        self.assertEqual(manifest.kind, ProjectKind.PCB_ONLY)
        self.assertEqual(set(manifest.required_inputs), {f"kicad/{name}" for name in before})
        self.assertFalse(manifest.component_identity.required)
        self.assertIsInstance(contract.validation, PcbOnlyValidationContract)
        self.assertIn("PCB-only import", (island / "README.md").read_text(encoding="utf-8"))
        self.assertEqual(lint(self.root, [manifest.id]).status, "PASS")
        self.assertEqual(
            {path.relative_to(self.source).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
             for path in self.source.rglob("*") if path.is_file()},
            before,
        )
        write_model(
            island / "project.json",
            manifest.model_copy(update={"assurance_profile": "production"}),
        )
        self.assertTrue(any("pcb_only must remain" in issue for issue in lint(self.root, [manifest.id]).issues))
        write_model(
            island / "project.json",
            manifest.model_copy(
                update={"component_identity": ComponentIdentity(required=True, part_ids=())}
            ),
        )
        self.assertTrue(
            any("pcb_only cannot require component identity" in issue for issue in lint(self.root, [manifest.id]).issues)
        )

    def test_project_without_a_schematic_or_board_fails_without_publishing(self) -> None:
        self.project.with_suffix(".kicad_sch").unlink()
        self.project.with_suffix(".kicad_pcb").unlink()
        result = self.run_import()
        self.assertEqual(result.status, "FAIL")
        self.assertIn("matching .kicad_sch or .kicad_pcb", result.issues[0])
        self.assertFalse((self.root / result.directory).exists())

    def test_symlink_rejected_and_interrupted_copy_cleans_staging(self) -> None:
        link = self.source / "linked.kicad_sym"
        try:
            link.symlink_to(self.source / "symbols.kicad_sym")
        except OSError:
            self.skipTest("Symlink creation unavailable")
        self.assertEqual(self.run_import().status, "FAIL")
        link.unlink()
        with patch("kicad_tooling.hwrepo.importing.shutil.copy2", side_effect=OSError("disk full")):
            self.assertEqual(self.run_import().status, "FAIL")
        self.assertFalse(list((self.root / "projects").glob(".import-project-*")))
        self.assertFalse((self.root / "projects/battery-board").exists())

    def test_embedded_models_are_local_dependencies_but_missing_records_fail(self) -> None:
        board = self.source / "embedded.kicad_pcb"
        board.write_text('(kicad_pcb (model "kicad-embed://part.step") '
                         '(embedded_files (file (name "part.step") (type model) '
                         '(data |YWJj|) (checksum "AABB"))))')
        self.assertEqual(cad_dependencies(self.base, board, self.source, "10", frozenset(), frozenset()), [])
        board.write_text('(kicad_pcb (model "kicad-embed://part.step"))')
        self.assertIn("missing embedded model", cad_dependencies(self.base, board, self.source, "10", frozenset(), frozenset())[0])

    def test_import_preserves_all_local_3d_source_formats_and_references(self) -> None:
        models = self.source / "models"
        models.mkdir()
        names = ("Part.step", "Part.stp", "Part.wrl", "Part.igs", "Part.iges")
        for name in names:
            (models / name).write_text(f"authored {name}", encoding="utf-8")
        paths = "\n".join(f'(model "${{KIPRJMOD}}/models/{name}")' for name in names)
        self.project.with_suffix(".kicad_pcb").write_text(
            f'(kicad_pcb (footprint "Lib:Part" (property "Reference" "U1") {paths}))',
            encoding="utf-8",
        )
        preview = self.run_import(True)
        self.assertEqual(preview.status, "PASS", preview.issues)
        for name in names:
            self.assertIn(f"models/{name}", preview.copied_sha256)
        imported = self.run_import()
        self.assertEqual(imported.status, "PASS", imported.issues)
        config = load_config(self.root, "projects/battery-board/project.json")
        board = self.root / "projects/battery-board/kicad/Old board.kicad_pcb"
        self.assertEqual(cad_dependencies(
            self.root, board, board.parent, "10",
            frozenset(config.required_inputs), frozenset(config.source_roots),
        ), [])
        inventory = inspect_models(self.root, config)
        self.assertEqual(inventory.status, "READY", inventory.findings)
        self.assertEqual(len(inventory.footprints[0].models), len(names))
        self.assertEqual(len(inventory.footprints[0].candidate_assets), len(names))

    def test_missing_3d_asset_remains_a_named_repair_after_import(self) -> None:
        self.project.with_suffix(".kicad_pcb").write_text(
            '(kicad_pcb (footprint "Lib:Part" (property "Reference" "U1") '
            '(model "${KIPRJMOD}/models/Missing.step")))', encoding="utf-8",
        )
        imported = self.run_import()
        self.assertEqual(imported.status, "PASS", imported.issues)
        config = load_config(self.root, "projects/battery-board/project.json")
        board = self.root / "projects/battery-board/kicad/Old board.kicad_pcb"
        issues = cad_dependencies(
            self.root, board, board.parent, "10",
            frozenset(config.required_inputs), frozenset(config.source_roots),
        )
        self.assertEqual(len(issues), 1)
        self.assertIn("Missing.step", issues[0])
        guidance = repository_guidance(issues[0], "10")
        self.assertEqual(guidance.code, "CAD_PATH")
        self.assertIn("intended asset", guidance.action)
        self.assertEqual(inspect_models(self.root, config).status, "FAIL")


if __name__ == "__main__":
    unittest.main()
