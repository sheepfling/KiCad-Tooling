"""Guard project inventory contract ownership and registry compatibility."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from kicad_tooling.hwrepo import models, project_inventory_models, project_models

pytestmark = pytest.mark.architecture

_REPOSITORY_ROOT = Path(__file__).parents[1]
_INVENTORY_MODEL_NAMES = frozenset(
    {
        "InventoryProject",
        "McpProjectReport",
        "InventoryGroup",
        "InventoryToolchain",
        "TemplateInventoryReport",
    }
)


def test_project_inventory_models_have_narrow_dependencies_and_reviewable_size() -> None:
    path = _REPOSITORY_ROOT / "kicad_tooling/hwrepo/project_inventory_models.py"
    source = path.read_text(encoding="utf-8")
    imported_modules = {
        node.module
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ImportFrom)
        and node.module is not None
        and node.module != "__future__"
    }

    assert len(source.splitlines()) < 500
    assert imported_modules == {
        "typing",
        "model_primitives",
        "policy_issue_models",
        "project_models",
    }


def test_production_modules_use_the_project_inventory_owner() -> None:
    tooling_root = _REPOSITORY_ROOT / "kicad_tooling"
    compatibility_registry = tooling_root / "hwrepo/models.py"
    violations: list[str] = []
    for path in tooling_root.rglob("*.py"):
        if path == compatibility_registry:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or node.module not in {
                "models",
                "hwrepo.models",
                "kicad_tooling.hwrepo.models",
            }:
                continue
            imported = _INVENTORY_MODEL_NAMES.intersection(alias.name for alias in node.names)
            if imported:
                names = ", ".join(sorted(imported))
                violations.append(f"{path.relative_to(_REPOSITORY_ROOT)}:{node.lineno}: {names}")

    assert not violations, "Production imports must use project_inventory_models: " + "; ".join(
        violations
    )


def test_legacy_exports_and_inventory_json_remain_compatible() -> None:
    for name in _INVENTORY_MODEL_NAMES:
        assert getattr(models, name) is getattr(project_inventory_models, name)

    inventory_project = project_inventory_models.InventoryProject(
        id="board-1",
        kind=project_models.ProjectKind.PCB,
        status="engineering",
        assurance_profile="development",
        manifest="projects/board-1/project.json",
        project="projects/board-1/board-1.kicad_pro",
        toolchain_id="kicad-10",
        tags=(),
        products=(),
        readiness="INPUTS_PRESENT",
        next_command="kicad-team verify --project board-1",
    )
    inventory = project_inventory_models.TemplateInventoryReport(
        status="PASS",
        projects=(inventory_project,),
    )
    ignored = project_models.IgnoredChecks(erc=(), drc=())
    identity = project_models.ComponentIdentity(required=False, part_ids=())
    manifest = project_models.ProjectManifest(
        id="board-1",
        kind=project_models.ProjectKind.PCB_ONLY,
        status="engineering",
        assurance_profile="development",
        toolchain_id="kicad-10",
        project="board-1.kicad_pro",
        source_roots=("kicad",),
        required_inputs=(),
        component_identity=identity,
    )
    contract = project_models.ProjectTestContract(
        validation=project_models.PcbOnlyValidationContract(
            kind=project_models.ProjectKind.PCB_ONLY,
            expected_ignored_checks=ignored,
        )
    )
    mcp_report = project_inventory_models.McpProjectReport(
        project=inventory_project,
        manifest=manifest,
        contract=contract,
    )

    assert (
        models.TemplateInventoryReport.model_validate_json(inventory.model_dump_json()) == inventory
    )
    assert models.McpProjectReport.model_validate_json(mcp_report.model_dump_json()) == mcp_report
    assert (
        models.TemplateInventoryReport.model_json_schema()
        == project_inventory_models.TemplateInventoryReport.model_json_schema()
    )
