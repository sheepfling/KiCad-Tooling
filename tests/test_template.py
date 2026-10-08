"""Typed template bootstrap and migration-plan tests."""

from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import patch

import pytest

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


@pytest.fixture
def template_root(tmp_path: Path) -> Path:
    root = tmp_path / "source-template"
    shutil.copytree(
        ROOT,
        root,
        ignore=shutil.ignore_patterns(".git", "build", ".evidence", "__pycache__"),
    )
    initialize_git(root)
    return root


def test_preflight_accepts_the_declared_template_contract(template_root: Path) -> None:
    report = preflight(template_root)
    assert report.status == "PASS", report.issues
    contract = read_model(template_root / "templates/template-contract.json", TemplateContract)
    assert report.template_version == contract.template_version
    assert not report.build_authorized


def test_preflight_rejects_a_missing_required_template_path(template_root: Path) -> None:
    (template_root / "docs/workflow/START_HERE.md").unlink()
    report = preflight(template_root)
    assert report.status == "FAIL"
    assert "TEMPLATE_REQUIRED_PATH" in {issue.code for issue in report.issues}


def test_bootstrap_creates_a_non_git_copy_with_pending_adoption_record(
    template_root: Path, tmp_path: Path
) -> None:
    destination = tmp_path / "adopting-repository"
    with patch("kicad_tooling.hwrepo.template.working_tree_is_clean", return_value=True):
        report = bootstrap(template_root, destination, "example-board")
    assert report.status == "PASS", report.issues
    assert not (destination / ".git").exists()
    assert (destination / "AGENTS.md").is_file()
    assert (destination / "CLAUDE.md").is_file()
    adoption = read_model(destination / "template-adoption.json", TemplateAdoptionRecord)
    assert adoption.project_id == "example-board"
    assert adoption.status == "needs_adoption"


def test_bootstrap_excludes_ignored_downloads_and_generated_outputs(
    template_root: Path, tmp_path: Path
) -> None:
    for name in (
        "private.zip",
        "generated/old.json",
        "schemas/old.schema.json",
        ".venv/private.txt",
    ):
        path = template_root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("local only", encoding="utf-8")
    destination = tmp_path / "source-only"
    with patch("kicad_tooling.hwrepo.template.working_tree_is_clean", return_value=True):
        report = bootstrap(template_root, destination, "example-board")
    assert report.status == "PASS", report.issues
    assert (destination / "README.md").is_file()
    for name in ("private.zip", "generated/old.json", "schemas/old.schema.json", ".venv"):
        assert not (destination / name).exists(), name


def test_upgrade_plan_requires_one_forward_catalog_path(template_root: Path) -> None:
    write_model(
        template_root / "template-adoption.json",
        TemplateAdoptionRecord(
            template_version="1.0.0", project_id="adopted-board", status="initialized"
        ),
    )
    catalog_path = template_root / "templates/template-upgrades.json"
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
    report = plan_upgrade(template_root, "1.1.0")
    assert report.status == "PASS", report.issues
    assert [upgrade.id for upgrade in report.upgrades] == ["template-1.0-to-1.1"]


def test_upgrade_plan_rejects_missing_forward_path(template_root: Path) -> None:
    report = plan_upgrade(template_root, "999.0.0")
    assert report.status == "FAIL"
    assert "TEMPLATE_UPGRADE_PATH" in {issue.code for issue in report.issues}


def test_usability_release_has_a_forward_plan_from_1_0(template_root: Path) -> None:
    write_model(
        template_root / "template-adoption.json",
        TemplateAdoptionRecord(
            template_version="1.0.0", project_id="adopted-board", status="initialized"
        ),
    )
    report = plan_upgrade(template_root, "1.1.0")
    assert report.status == "PASS", report.issues
    assert [upgrade.id for upgrade in report.upgrades] == ["template-1.0-to-1.1"]


def test_documentation_ownership_release_has_a_forward_plan_from_1_1(
    template_root: Path,
) -> None:
    write_model(
        template_root / "template-adoption.json",
        TemplateAdoptionRecord(
            template_version="1.1.0", project_id="adopted-board", status="initialized"
        ),
    )
    report = plan_upgrade(template_root, "1.2.0")
    assert report.status == "PASS", report.issues
    assert [upgrade.id for upgrade in report.upgrades] == ["template-1.1.0-to-1.2.0"]


def test_dependency_maintenance_release_has_a_forward_plan_from_1_2(
    template_root: Path,
) -> None:
    write_model(
        template_root / "template-adoption.json",
        TemplateAdoptionRecord(
            template_version="1.2.0", project_id="adopted-board", status="initialized"
        ),
    )
    report = plan_upgrade(template_root, "1.2.1")
    assert report.status == "PASS", report.issues
    assert [upgrade.id for upgrade in report.upgrades] == ["template-1.2.0-to-1.2.1"]


def test_pcb_only_import_release_has_a_forward_plan_from_1_2_1(template_root: Path) -> None:
    write_model(
        template_root / "template-adoption.json",
        TemplateAdoptionRecord(
            template_version="1.2.1", project_id="adopted-board", status="initialized"
        ),
    )
    report = plan_upgrade(template_root, "1.3.0")
    assert report.status == "PASS", report.issues
    assert [upgrade.id for upgrade in report.upgrades] == ["template-1.2.1-to-1.3.0"]


def test_board_scaffold_defaults_have_a_forward_plan_from_1_3_0(template_root: Path) -> None:
    write_model(
        template_root / "template-adoption.json",
        TemplateAdoptionRecord(
            template_version="1.3.0", project_id="adopted-board", status="initialized"
        ),
    )
    report = plan_upgrade(template_root, "1.3.1")
    assert report.status == "PASS", report.issues
    assert [upgrade.id for upgrade in report.upgrades] == ["template-1.3.0-to-1.3.1"]


def test_codex_review_corrections_have_a_forward_plan_from_1_3_1(template_root: Path) -> None:
    write_model(
        template_root / "template-adoption.json",
        TemplateAdoptionRecord(
            template_version="1.3.1", project_id="adopted-board", status="initialized"
        ),
    )
    report = plan_upgrade(template_root, "1.3.2")
    assert report.status == "PASS", report.issues
    assert [upgrade.id for upgrade in report.upgrades] == ["template-1.3.1-to-1.3.2"]


def test_tooling_split_has_a_breaking_forward_plan_from_1_3_2(template_root: Path) -> None:
    write_model(
        template_root / "template-adoption.json",
        TemplateAdoptionRecord(
            template_version="1.3.2", project_id="adopted-board", status="initialized"
        ),
    )
    report = plan_upgrade(template_root, "1.4.0")
    assert report.status == "PASS", report.issues
    assert [upgrade.id for upgrade in report.upgrades] == ["template-1.3.2-to-1.4.0"]
    assert report.upgrades[0].breaking
    contract = read_model(template_root / "templates/template-contract.json", TemplateContract)
    assert "requirements-tooling.txt" in contract.required_paths
    assert not any(path.startswith(("tools/", "tests/")) for path in contract.required_paths)
    assert not (template_root / "tools").exists()
    assert not (template_root / "tests").exists()


def test_upgrade_uses_adopted_version_after_upstream_contract_is_updated(
    template_root: Path,
) -> None:
    write_model(
        template_root / "template-adoption.json",
        TemplateAdoptionRecord(
            template_version="0.2.0", project_id="adopted-board", status="initialized"
        ),
    )
    report = plan_upgrade(template_root, "0.3.0")
    assert report.status == "PASS", report.issues
    assert report.current_version == "0.2.0"
    assert [upgrade.id for upgrade in report.upgrades] == ["template-0.2-to-0.3"]


def test_production_workflow_has_a_forward_migration_without_changing_adopter_files(
    template_root: Path,
) -> None:
    write_model(
        template_root / "template-adoption.json",
        TemplateAdoptionRecord(
            template_version="0.3.0", project_id="adopted-board", status="initialized"
        ),
    )
    before = (template_root / "catalog/projects.json").read_bytes()
    report = plan_upgrade(template_root, "1.0.0")
    assert report.status == "PASS", report.issues
    assert [upgrade.id for upgrade in report.upgrades] == ["template-0.3-to-1.0"]
    assert (template_root / "catalog/projects.json").read_bytes() == before


def test_source_only_migration_has_a_reviewable_forward_plan(template_root: Path) -> None:
    path = template_root / "templates/template-contract.json"
    contract = read_model(path, TemplateContract)
    write_model(path, contract.model_copy(update={"template_version": "0.1.0"}))
    report = plan_upgrade(template_root, "0.2.0")
    assert report.status == "PASS", report.issues
    assert [upgrade.id for upgrade in report.upgrades] == ["template-0.1-to-0.2"]
    assert report.upgrades[0].breaking


def test_same_version_plan_cannot_hide_failed_preflight(template_root: Path) -> None:
    (template_root / "docs/workflow/START_HERE.md").unlink()
    report = plan_upgrade(template_root, "1.1.0")
    assert report.status == "FAIL"
