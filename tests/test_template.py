"""Typed template bootstrap and migration-plan tests."""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.models import (
    TemplateAdoptionRecord,
    TemplateContract,
    TemplateUpgrade,
    TemplateUpgradesCatalog,
)
from kicad_tooling.hwrepo.template import bootstrap, plan_upgrade, preflight
from tests.support import initialize_git, reference_root

ROOT = reference_root()


class TemplateToolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="template-tools-")
        self.addCleanup(self.temporary.cleanup)
        self.parent = Path(self.temporary.name)
        self.root = self.parent / "source-template"
        shutil.copytree(
            ROOT,
            self.root,
            ignore=shutil.ignore_patterns(".git", "build", ".evidence", "__pycache__"),
        )

        initialize_git(self.root)

    def test_preflight_accepts_the_declared_template_contract(self) -> None:
        report = preflight(self.root)
        self.assertEqual(report.status, "PASS", report.issues)
        contract = read_model(self.root / "templates/template-contract.json", TemplateContract)
        self.assertEqual(report.template_version, contract.template_version)
        self.assertFalse(report.build_authorized)

    def test_preflight_rejects_a_missing_required_template_path(self) -> None:
        (self.root / "docs/workflow/START_HERE.md").unlink()
        report = preflight(self.root)
        self.assertEqual(report.status, "FAIL")
        self.assertIn("TEMPLATE_REQUIRED_PATH", {issue.code for issue in report.issues})

    def test_bootstrap_creates_a_non_git_copy_with_pending_adoption_record(self) -> None:
        destination = self.parent / "adopting-repository"
        with patch("kicad_tooling.hwrepo.template.working_tree_is_clean", return_value=True):
            report = bootstrap(self.root, destination, "example-board")
        self.assertEqual(report.status, "PASS", report.issues)
        self.assertFalse((destination / ".git").exists())
        self.assertTrue((destination / "AGENTS.md").is_file())
        self.assertTrue((destination / "CLAUDE.md").is_file())
        adoption = read_model(destination / "template-adoption.json", TemplateAdoptionRecord)
        self.assertEqual(adoption.project_id, "example-board")
        self.assertEqual(adoption.status, "needs_adoption")

    def test_bootstrap_excludes_ignored_downloads_and_generated_outputs(self) -> None:
        for name in ("private.zip", "generated/old.json", "schemas/old.schema.json", ".venv/private.txt"):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("local only", encoding="utf-8")
        destination = self.parent / "source-only"
        with patch("kicad_tooling.hwrepo.template.working_tree_is_clean", return_value=True):
            report = bootstrap(self.root, destination, "example-board")
        self.assertEqual(report.status, "PASS", report.issues)
        self.assertTrue((destination / "README.md").is_file())
        for name in ("private.zip", "generated/old.json", "schemas/old.schema.json", ".venv"):
            self.assertFalse((destination / name).exists(), name)

    def test_upgrade_plan_requires_one_forward_catalog_path(self) -> None:
        write_model(self.root / "template-adoption.json", TemplateAdoptionRecord(
            template_version="1.0.0", project_id="adopted-board", status="initialized"))
        catalog_path = self.root / "templates/template-upgrades.json"
        catalog = read_model(catalog_path, TemplateUpgradesCatalog)
        write_model(
            catalog_path,
            catalog.model_copy(
                update={
                    "upgrades": (
                        TemplateUpgrade(
                            id="template-1.0-to-1.1",
                            from_version="1.0.0",
                            to_version="1.1.0",
                            breaking=True,
                            steps=(
                                "Review the documented migration before changing source.",
                                "Run static and native checks after the reviewed update.",
                            ),
                        ),
                    )
                }
            ),
        )
        report = plan_upgrade(self.root, "1.1.0")
        self.assertEqual(report.status, "PASS", report.issues)
        self.assertEqual([upgrade.id for upgrade in report.upgrades], ["template-1.0-to-1.1"])

    def test_upgrade_plan_rejects_missing_forward_path(self) -> None:
        report = plan_upgrade(self.root, "999.0.0")
        self.assertEqual(report.status, "FAIL")
        self.assertIn("TEMPLATE_UPGRADE_PATH", {issue.code for issue in report.issues})

    def test_usability_release_has_a_forward_plan_from_1_0(self) -> None:
        write_model(self.root / "template-adoption.json", TemplateAdoptionRecord(
            template_version="1.0.0", project_id="adopted-board", status="initialized"))
        report = plan_upgrade(self.root, "1.1.0")
        self.assertEqual(report.status, "PASS", report.issues)
        self.assertEqual([upgrade.id for upgrade in report.upgrades], ["template-1.0-to-1.1"])

    def test_documentation_ownership_release_has_a_forward_plan_from_1_1(self) -> None:
        write_model(self.root / "template-adoption.json", TemplateAdoptionRecord(
            template_version="1.1.0", project_id="adopted-board", status="initialized"))
        report = plan_upgrade(self.root, "1.2.0")
        self.assertEqual(report.status, "PASS", report.issues)
        self.assertEqual(
            [upgrade.id for upgrade in report.upgrades],
            ["template-1.1.0-to-1.2.0"],
        )

    def test_dependency_maintenance_release_has_a_forward_plan_from_1_2(self) -> None:
        write_model(self.root / "template-adoption.json", TemplateAdoptionRecord(
            template_version="1.2.0", project_id="adopted-board", status="initialized"))
        report = plan_upgrade(self.root, "1.2.1")
        self.assertEqual(report.status, "PASS", report.issues)
        self.assertEqual(
            [upgrade.id for upgrade in report.upgrades],
            ["template-1.2.0-to-1.2.1"],
        )

    def test_pcb_only_import_release_has_a_forward_plan_from_1_2_1(self) -> None:
        write_model(self.root / "template-adoption.json", TemplateAdoptionRecord(
            template_version="1.2.1", project_id="adopted-board", status="initialized"))
        report = plan_upgrade(self.root, "1.3.0")
        self.assertEqual(report.status, "PASS", report.issues)
        self.assertEqual(
            [upgrade.id for upgrade in report.upgrades],
            ["template-1.2.1-to-1.3.0"],
        )

    def test_board_scaffold_defaults_have_a_forward_plan_from_1_3_0(self) -> None:
        write_model(self.root / "template-adoption.json", TemplateAdoptionRecord(
            template_version="1.3.0", project_id="adopted-board", status="initialized"))
        report = plan_upgrade(self.root, "1.3.1")
        self.assertEqual(report.status, "PASS", report.issues)
        self.assertEqual(
            [upgrade.id for upgrade in report.upgrades],
            ["template-1.3.0-to-1.3.1"],
        )

    def test_codex_review_corrections_have_a_forward_plan_from_1_3_1(self) -> None:
        write_model(self.root / "template-adoption.json", TemplateAdoptionRecord(
            template_version="1.3.1", project_id="adopted-board", status="initialized"))
        report = plan_upgrade(self.root, "1.3.2")
        self.assertEqual(report.status, "PASS", report.issues)
        self.assertEqual(
            [upgrade.id for upgrade in report.upgrades],
            ["template-1.3.1-to-1.3.2"],
        )

    def test_tooling_split_has_a_breaking_forward_plan_from_1_3_2(self) -> None:
        write_model(self.root / "template-adoption.json", TemplateAdoptionRecord(
            template_version="1.3.2", project_id="adopted-board", status="initialized"))
        report = plan_upgrade(self.root, "1.4.0")
        self.assertEqual(report.status, "PASS", report.issues)
        self.assertEqual([upgrade.id for upgrade in report.upgrades],
                         ["template-1.3.2-to-1.4.0"])
        self.assertTrue(report.upgrades[0].breaking)
        contract = read_model(self.root / "templates/template-contract.json", TemplateContract)
        self.assertIn("requirements-tooling.txt", contract.required_paths)
        self.assertFalse(any(path.startswith(("tools/", "tests/"))
                             for path in contract.required_paths))
        self.assertFalse((self.root / "tools").exists())
        self.assertFalse((self.root / "tests").exists())

    def test_upgrade_uses_adopted_version_after_upstream_contract_is_updated(self) -> None:
        write_model(self.root / "template-adoption.json", TemplateAdoptionRecord(
            template_version="0.2.0", project_id="adopted-board", status="initialized"))
        report = plan_upgrade(self.root, "0.3.0")
        self.assertEqual(report.status, "PASS", report.issues)
        self.assertEqual(report.current_version, "0.2.0")
        self.assertEqual([upgrade.id for upgrade in report.upgrades], ["template-0.2-to-0.3"])

    def test_production_workflow_has_a_forward_migration_without_changing_adopter_files(self) -> None:
        write_model(self.root / "template-adoption.json", TemplateAdoptionRecord(
            template_version="0.3.0", project_id="adopted-board", status="initialized"))
        before = (self.root / "catalog/projects.json").read_bytes()
        report = plan_upgrade(self.root, "1.0.0")
        self.assertEqual(report.status, "PASS", report.issues)
        self.assertEqual([upgrade.id for upgrade in report.upgrades], ["template-0.3-to-1.0"])
        self.assertEqual((self.root / "catalog/projects.json").read_bytes(), before)

    def test_source_only_migration_has_a_reviewable_forward_plan(self) -> None:
        path = self.root / "templates/template-contract.json"
        contract = read_model(path, TemplateContract)
        write_model(path, contract.model_copy(update={"template_version": "0.1.0"}))
        report = plan_upgrade(self.root, "0.2.0")
        self.assertEqual(report.status, "PASS", report.issues)
        self.assertEqual([upgrade.id for upgrade in report.upgrades], ["template-0.1-to-0.2"])
        self.assertTrue(report.upgrades[0].breaking)

    def test_same_version_plan_cannot_hide_failed_preflight(self) -> None:
        (self.root / "docs/workflow/START_HERE.md").unlink()
        report = plan_upgrade(self.root, "1.1.0")
        self.assertEqual(report.status, "FAIL")


if __name__ == "__main__":
    unittest.main()
