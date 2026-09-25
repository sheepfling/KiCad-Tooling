"""Project-local discovery, scaffold and independent test execution regressions."""
from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from kicad_tooling.ci import project_static_pipeline
from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.discovery import load_config, load_registry
from kicad_tooling.hwrepo.documentation import check as documentation_check
from kicad_tooling.hwrepo.models import (
    IgnoredChecks,
    PcbOnlyValidationContract,
    ProjectKind,
    ProjectManifest,
    ProjectTestContract,
)
from kicad_tooling.hwrepo.product import check as product_check
from kicad_tooling.hwrepo.project_tests import run_tests
from kicad_tooling.hwrepo.scaffold import new_project
from kicad_tooling.lint_registry import lint
from tests.support import initialize_git, reference_root


class IslandTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="project-islands-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve() / "repository"
        shutil.copytree(reference_root(), self.root, ignore=shutil.ignore_patterns(".git", "build"))
        initialize_git(self.root)

    def test_scaffold_discovers_a_board_without_editing_catalogs_or_creating_a_circuit(self) -> None:
        before = (self.root / "catalog/projects.json").read_bytes()
        report = new_project(self.root, "battery-board", ProjectKind.PCB, "kicad-10.0.5")
        self.assertEqual(report.status, "PASS", report.issues)
        island = self.root / "projects/battery-board"
        manifest = read_model(island / "project.json", ProjectManifest)
        contract = read_model(island / "tests/contract.json", ProjectTestContract)
        self.assertEqual(manifest.assurance_profile, "development")
        self.assertFalse((island / manifest.project).exists())
        self.assertTrue((island / manifest.checks).is_file())
        self.assertEqual((self.root / "catalog/projects.json").read_bytes(), before)
        self.assertIn("battery-board", {project.id for project in load_registry(self.root).projects})
        self.assertEqual(lint(self.root, ["battery-board"]).status, "FAIL")
        self.assertEqual(documentation_check(self.root).status, "PASS")
        self.assertEqual(contract.validation.expected_ignored_checks, IgnoredChecks(erc=(), drc=()))
        # Repeating a scaffold must not overwrite a contributor's work.
        (island / "docs/README.md").write_text("keep these notes", encoding="utf-8")
        self.assertEqual(new_project(self.root, "battery-board", ProjectKind.PCB, "kicad-10.0.5").status, "FAIL")
        self.assertEqual((island / "docs/README.md").read_text(), "keep these notes")

    def test_scaffold_rejects_unsafe_ids_unknown_pins_and_existing_ids(self) -> None:
        for identifier, pin in (("../escape", "kicad-10.0.5"), ("controller", "kicad-10.0.5"), ("new-board", "missing")):
            with self.subTest(identifier=identifier):
                self.assertEqual(new_project(self.root, identifier, ProjectKind.PCB, pin).status, "FAIL")
        self.assertFalse((self.root / "projects/new-board").exists())

    def test_pcb_only_scaffold_declares_a_not_for_manufacture_board_capture_lane(self) -> None:
        report = new_project(self.root, "legacy-layout", ProjectKind.PCB_ONLY, "kicad-10.0.5")
        self.assertEqual(report.status, "PASS", report.issues)
        island = self.root / "projects/legacy-layout"
        manifest = read_model(island / "project.json", ProjectManifest)
        contract = read_model(island / "tests/contract.json", ProjectTestContract)
        self.assertEqual(manifest.kind, ProjectKind.PCB_ONLY)
        self.assertEqual(manifest.assurance_profile, "development")
        self.assertIsInstance(contract.validation, PcbOnlyValidationContract)
        self.assertIn(".kicad_pcb", " ".join(manifest.required_inputs))
        self.assertEqual(contract.validation.expected_ignored_checks, IgnoredChecks(erc=(), drc=()))
        self.assertIn("PCB-only capture lane", (island / "README.md").read_text(encoding="utf-8"))

    def test_local_manifest_paths_cannot_escape_the_island(self) -> None:
        path = self.root / "examples/projects/controller/project.json"
        manifest = read_model(path, ProjectManifest)
        write_model(path, manifest.model_copy(update={"project": "../other/board.kicad_pro"}))
        with self.assertRaisesRegex(ValueError, "Unsafe repository path"):
            load_registry(self.root)
        self.assertEqual(project_static_pipeline(self.root, ("controller",)).status, "FAIL")

    def test_duplicate_ids_and_mismatched_directory_names_are_rejected(self) -> None:
        destination = self.root / "projects/Controller"
        shutil.copytree(self.root / "examples/projects/controller", destination)
        manifest = read_model(destination / "project.json", ProjectManifest)
        write_model(destination / "project.json", manifest.model_copy(update={"id": "Controller"}))
        with self.assertRaisesRegex(ValueError, "Duplicate project id"):
            load_registry(self.root)
        write_model(destination / "project.json", manifest.model_copy(update={"id": "wrong-folder"}))
        with self.assertRaisesRegex(ValueError, "directory must match"):
            load_registry(self.root)

    def test_development_board_does_not_require_production_records(self) -> None:
        path = self.root / "examples/projects/passive-signal-reference/project.json"
        manifest = read_model(path, ProjectManifest)
        write_model(path, manifest.model_copy(update={"status": "engineering", "assurance_profile": "development"}))
        contract_path = path.parent / manifest.checks
        contract = read_model(contract_path, ProjectTestContract)
        write_model(contract_path, contract.model_copy(update={"validation": contract.validation.model_copy(
            update={"expected_ignored_checks": IgnoredChecks(erc=(), drc=())})}))
        report = lint(self.root, [manifest.id])
        self.assertEqual(report.status, "PASS", report.issues)
        self.assertTrue(load_config(self.root, path).not_for_manufacture)

    def write_test(self, relative: str, passed: bool) -> None:
        path = self.root / relative / "tests/test_same_name.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("import unittest\n\nclass IslandBehavior(unittest.TestCase):\n"
                        f"    def test_requirement(self):\n        self.assertTrue({passed})\n", encoding="utf-8")

    def test_local_suites_have_separate_import_scopes_and_fail_the_selected_gate(self) -> None:
        self.write_test("examples/projects/controller", True)
        self.write_test("examples/projects/arduino-uno-status-led", False)
        self.assertEqual(run_tests(self.root, ("controller",)).status, "PASS")
        result = run_tests(self.root)
        self.assertEqual(result.commands["project-controller"].returncode, 0)
        self.assertNotEqual(result.commands["project-arduino-uno-status-led"].returncode, 0)
        self.assertEqual(project_static_pipeline(self.root, ("arduino-uno-status-led",)).status, "FAIL")

    def test_parallel_island_suites_keep_stable_results_and_order(self) -> None:
        self.write_test("examples/projects/controller", True)
        self.write_test("examples/projects/arduino-uno-status-led", False)
        serial = run_tests(self.root)
        parallel = run_tests(self.root, max_workers=2)
        self.assertEqual(parallel.status, "FAIL")
        self.assertEqual(list(parallel.commands), list(serial.commands))
        self.assertEqual(
            {name: command.returncode for name, command in parallel.commands.items()},
            {name: command.returncode for name, command in serial.commands.items()},
        )
        with self.assertRaisesRegex(ValueError, "at least one"):
            run_tests(self.root, max_workers=0)

    def test_product_tests_run_only_for_participating_projects(self) -> None:
        self.write_test("examples/products/status-indicator-system", False)
        self.assertEqual(run_tests(self.root, ("controller",)).status, "PASS")
        self.assertEqual(run_tests(self.root, ("arduino-uno-status-led",)).status, "FAIL")

    def test_focused_lane_ignores_an_unrelated_project_contract(self) -> None:
        path = self.root / "examples/projects/arduino-uno-status-led/tests/contract.json"
        path.write_text("{}", encoding="utf-8")

        focused = project_static_pipeline(self.root, ("controller",))
        self.assertEqual(focused.status, "PASS", focused.model_dump_json())
        self.assertEqual(focused.product.status, "PASS")

        # The full gate still validates every project, including the damaged one.
        self.assertEqual(lint(self.root).status, "FAIL")
        full_product = product_check(self.root)
        self.assertEqual(full_product.status, "FAIL")
        self.assertIn("PRODUCT_LOAD", {issue.code for issue in full_product.issues})

    def test_focused_lane_checks_contracts_of_its_dependent_product(self) -> None:
        path = self.root / "examples/projects/status-indicator-wiring/tests/contract.json"
        path.write_text("{}", encoding="utf-8")

        focused = project_static_pipeline(self.root, ("arduino-uno-status-led",))
        self.assertEqual(focused.registry.status, "PASS", focused.registry.issues)
        self.assertEqual(focused.product.status, "FAIL")
        self.assertTrue(any(
            issue.code == "PRODUCT_LOAD" and "status-indicator-wiring" in issue.message
            for issue in focused.product.issues
        ))

    def test_product_check_fails_closed_on_unknown_selected_project(self) -> None:
        report = product_check(self.root, selected_project_ids=("does-not-exist",))
        self.assertEqual(report.status, "FAIL")
        self.assertIn("PROJECT_SELECTION", {issue.code for issue in report.issues})

    def test_nested_test_files_cannot_silently_run_zero_tests(self) -> None:
        path = self.root / "examples/projects/controller/tests/nested"
        path.mkdir()
        (path / "test_missing_package.py").write_text("import unittest\n", encoding="utf-8")
        result = run_tests(self.root, ("controller",))
        self.assertEqual(result.status, "FAIL")
        self.assertIn("none were discovered", result.commands["project-controller"].error or "")

    def test_authored_and_frozen_boms_are_tracked_but_working_outputs_are_ignored(self) -> None:
        for name, expected in (("projects/battery-board/bom/assembly.csv", 1),
                               ("projects/battery-board/releases/v1/bom.csv", 1),
                               ("projects/battery-board/build/bom.csv", 0)):
            result = subprocess.run(("git", "check-ignore", "--no-index", "-q", "--", name),
                                    cwd=self.root, check=False)
            self.assertEqual(result.returncode, expected, name)


if __name__ == "__main__":
    unittest.main()
