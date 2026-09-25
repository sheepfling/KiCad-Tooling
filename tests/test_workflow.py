"""Fork adoption, automatic expansion and source-only generation regressions."""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from kicad_tooling.ci_matrix import build_matrix
from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.generation import check_generation, drift, generate
from kicad_tooling.hwrepo.initialization import initialize
from kicad_tooling.hwrepo.models import (
    LibrariesCatalog,
    ProductIndex,
    ProjectDiscovery,
    ProjectManifest,
)
from kicad_tooling.hwrepo.product import check as product_check
from kicad_tooling.hwrepo.repository import check_repository
from kicad_tooling.lint_registry import lint
from tests.support import initialize_git, reference_root


class ForkWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="kicad-fork-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve() / "repository"
        shutil.copytree(reference_root(), self.root, ignore=shutil.ignore_patterns(".git"))
        initialize_git(self.root)

    def test_initialize_empty_fork_is_repeatable_and_retains_reference_tests(self) -> None:
        team_notes = self.root / "docs/team/architecture.md"
        team_notes.write_text("# Team architecture\n\nDurable adopter decision.\n", encoding="utf-8")
        team_readme = self.root / "docs/team/README.md"
        team_readme.write_text(
            team_readme.read_text(encoding="utf-8")
            + "\n## Team index\n\n- [Architecture](architecture.md)\n",
            encoding="utf-8",
        )
        before_team_docs = {
            path: path.read_bytes() for path in (team_notes, team_readme)
        }
        result = initialize(self.root, "team-hardware")
        self.assertEqual(result.status, "PASS", result.issues)
        self.assertTrue(
            (self.root / "README.md").read_text(encoding="utf-8").startswith(
                "# team-hardware\n\n"
            )
        )
        self.assertEqual(build_matrix(self.root).include, ())
        self.assertEqual(product_check(self.root).status, "PASS")
        self.assertEqual(check_generation(self.root), ())
        self.assertEqual(
            {path: path.read_bytes() for path in before_team_docs},
            before_team_docs,
        )
        self.add_project()
        self.assertEqual(initialize(self.root, "team-hardware").changed, ())
        self.assertEqual([row.project for row in build_matrix(self.root).include], ["team-signal"])
        self.assertEqual(initialize(self.root, "different-name").status, "FAIL")
        result = subprocess.run((sys.executable, "-B", "-m", "unittest", "tests.test_governance"),
                                cwd=self.root, text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_initialize_never_overwrites_existing_work_or_partially_edits(self) -> None:
        catalog = self.root / "catalog/parts.json"
        catalog.write_text(catalog.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        before = (self.root / "catalog/projects.json").read_bytes()
        self.assertEqual(initialize(self.root, "team-hardware").status, "FAIL")
        self.assertEqual((self.root / "catalog/projects.json").read_bytes(), before)
        self.assertFalse((self.root / "template-adoption.json").exists())
        self.assertEqual(initialize(self.root, "../escape").status, "FAIL")

    def test_disabling_live_discovery_cannot_turn_existing_designs_into_an_empty_pass(self) -> None:
        self.add_project()
        path = self.root / "catalog/projects.json"
        policy = read_model(path, ProjectDiscovery)
        write_model(path, policy.model_copy(update={"project_roots": ()}))
        with self.assertRaisesRegex(ValueError, "invalid registry"):
            build_matrix(self.root)

    def test_authored_images_are_trackable_but_generated_images_are_rejected(self) -> None:
        authored = "projects/board/docs/assets/connector.png"
        path = self.root / authored
        path.parent.mkdir(parents=True)
        path.write_bytes(b"authored fixture")
        subprocess.run(("git", "-C", str(self.root), "add", "--", authored), check=True)
        self.assertEqual(check_repository(self.root).status, "PASS")
        generated = "projects/board/build/connector.png"
        path = self.root / generated
        path.parent.mkdir(parents=True)
        path.write_bytes(b"derived fixture")
        subprocess.run(("git", "-C", str(self.root), "add", "-f", "--", generated), check=True)
        self.assertIn(f"TRACKED_LOCAL_STATE: {generated}", check_repository(self.root).issues)

    def test_shared_library_paths_are_inventoried_and_private_project_paths_fail(self) -> None:
        selected = ("arduino-uno-status-led",)
        self.assertEqual(check_repository(self.root, selected).status, "PASS")
        self.assertEqual(lint(self.root, list(selected)).status, "PASS")
        table = self.root / "examples/projects/arduino-uno-status-led/kicad/sym-lib-table"
        table.write_text(
            table.read_text(encoding="utf-8").replace(
                "${KIPRJMOD}/../../../libraries/status-led/status-led.kicad_sym",
                "${KIPRJMOD}/../../controller/kicad/Pilot.kicad_sym",
            ),
            encoding="utf-8",
        )
        report = check_repository(self.root, selected)
        self.assertEqual(report.status, "FAIL")
        self.assertTrue(any("not in this project's required_inputs" in issue for issue in report.issues))

    def test_focused_repository_check_rejects_undeclared_cad_in_selected_island(self) -> None:
        unselected = self.root / "examples/projects/arduino-uno-status-led/kicad/rogue.kicad_sch"
        unselected.write_text("(kicad_sch)", encoding="utf-8")
        self.assertEqual(check_repository(self.root, ("controller",)).status, "PASS")
        selected = self.root / "examples/projects/controller/kicad/rogue.kicad_pcb"
        selected.write_text("(kicad_pcb)", encoding="utf-8")
        report = check_repository(self.root, ("controller",))
        self.assertIn(
            "UNREGISTERED_DESIGN: examples/projects/controller/kicad/rogue.kicad_pcb",
            report.issues,
        )

    def test_shared_source_roots_must_match_registered_library_paths(self) -> None:
        path = self.root / "examples/projects/arduino-uno-status-led/project.json"
        manifest = read_model(path, ProjectManifest)
        write_model(path, manifest.model_copy(update={
            "shared_source_roots": ("examples/projects/controller/kicad",),
        }))
        report = lint(self.root, ["arduino-uno-status-led"])
        self.assertEqual(report.status, "FAIL")
        self.assertTrue(any("shared_source_roots must match library_ids" in issue for issue in report.issues))

    def test_library_table_cannot_expose_an_unscoped_parent_directory(self) -> None:
        table = self.root / "examples/projects/arduino-uno-status-led/kicad/fp-lib-table"
        table.write_text(
            table.read_text(encoding="utf-8").replace(
                "${KIPRJMOD}/../../../libraries/status-led/status-led.pretty",
                "${KIPRJMOD}/../../../libraries",
            ),
            encoding="utf-8",
        )
        report = check_repository(self.root, ("arduino-uno-status-led",))
        self.assertEqual(report.status, "FAIL")
        self.assertTrue(any("outside this project's source_roots" in issue for issue in report.issues))

    def test_library_table_directory_exposes_only_inventoried_files(self) -> None:
        loose = self.root / "examples/libraries/status-led/status-led.pretty/Loose.kicad_mod"
        loose.write_text("(footprint Loose)", encoding="utf-8")
        report = check_repository(self.root, ("arduino-uno-status-led",))
        self.assertEqual(report.status, "FAIL")
        self.assertTrue(any("exposes unlisted files" in issue for issue in report.issues))

    def test_library_catalog_cannot_register_another_project_as_a_library(self) -> None:
        path = self.root / "catalog/libraries.json"
        catalog = read_model(path, LibrariesCatalog)
        library = catalog.libraries[0].model_copy(update={
            "path": "examples/projects/controller/kicad",
        })
        write_model(path, catalog.model_copy(update={"libraries": (library,)}))
        report = lint(self.root, ["arduino-uno-status-led"])
        self.assertEqual(report.status, "FAIL")
        self.assertTrue(any("path must be a named directory under library_roots" in issue for issue in report.issues))

    def test_fresh_policy_generation_needs_no_cached_exports_and_writes_no_source(self) -> None:
        self.assertFalse((self.root / "schemas/product-v1.schema.json").exists())
        self.assertEqual(check_generation(self.root), ())
        self.assertFalse((self.root / "schemas/product-v1.schema.json").exists())
        self.assertFalse((self.root / "generated/library-sbom-v1.json").exists())

    def test_schema_missing_tampered_and_stale_outputs_are_detected(self) -> None:
        generate(self.root)
        path = self.root / "schemas/product-v1.schema.json"
        path.unlink()
        self.assertIn("GENERATION_DRIFT: schemas/product-v1.schema.json", drift(self.root))
        generate(self.root)
        path.write_text("{}", encoding="utf-8")
        self.assertIn("GENERATION_DRIFT: schemas/product-v1.schema.json", drift(self.root))
        (path.parent / "obsolete.schema.json").write_text("{}", encoding="utf-8")
        self.assertIn("STALE_OUTPUT: schemas/obsolete.schema.json", drift(self.root))

    def test_force_added_exports_are_rejected(self) -> None:
        for name in ("generated/bom.csv", "schemas/product.schema.json", "projects/board.gbr"):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("derived", encoding="utf-8")
            subprocess.run(("git", "-C", str(self.root), "add", "-f", "--", name), check=True)
        report = check_repository(self.root)
        self.assertEqual(report.status, "FAIL")
        for name in ("generated/bom.csv", "schemas/product.schema.json", "projects/board.gbr"):
            self.assertIn(f"TRACKED_GENERATED_OUTPUT: {name}", report.issues)

    def add_project(self) -> None:
        directory = self.root / "projects/team-signal"
        shutil.copytree(self.root / "examples/projects/passive-signal-reference", directory)
        path = directory / "project.json"
        manifest = read_model(path, ProjectManifest)
        write_model(path, manifest.model_copy(update={"id": "team-signal", "tags": ("team",)}))

    def test_registration_adds_a_lane_and_adoption_can_retire_live_examples(self) -> None:
        self.add_project()
        matrix = build_matrix(self.root)
        self.assertEqual(matrix.include[-1].project, "team-signal")
        self.assertFalse(matrix.include[-1].fault_probes)
        self.assertTrue(next(row for row in matrix.include if row.project == "controller").fault_probes)
        self.assertEqual(len(matrix.include), 7)
        path = self.root / "catalog/projects.json"
        discovery = read_model(path, ProjectDiscovery)
        write_model(path, discovery.model_copy(update={"project_roots": ("projects",)}))
        index = read_model(self.root / "catalog/products.json", ProductIndex)
        write_model(self.root / "catalog/products.json", index.model_copy(update={"products": ()}))
        self.assertEqual(lint(self.root).status, "PASS", lint(self.root).issues)
        self.assertEqual(product_check(self.root).status, "PASS", product_check(self.root).issues)
        self.assertEqual([row.project for row in build_matrix(self.root).include], ["team-signal"])
        # A fork's live catalog changes must not rewrite the reference unit expectations.
        result = subprocess.run((sys.executable, "-B", "-m", "unittest", "tests.test_governance"),
                                cwd=self.root, text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
