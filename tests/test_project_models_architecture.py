"""Guard the project-contract owner and registry compatibility boundary."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from kicad_tooling.hwrepo import models, project_models

pytestmark = pytest.mark.architecture

_REPOSITORY_ROOT = Path(__file__).parents[1]
_PROJECT_MODEL_NAMES = frozenset(
    {
        "ToolchainRecord",
        "ToolchainsCatalog",
        "ComponentIdentity",
        "ProjectKind",
        "ProjectRecord",
        "CatalogPaths",
        "ProjectRegistry",
        "ComponentContract",
        "IgnoredChecks",
        "PcbValidationContract",
        "PcbOnlyValidationContract",
        "SchematicValidationContract",
        "ProductTraceabilityValidationContract",
        "SystemWiringValidationContract",
        "HarnessInterfaceValidationContract",
        "ProjectValidationContract",
        "ProjectConfig",
        "ProjectDiscovery",
        "ReleaseExportSettings",
        "ProjectManifest",
        "ProjectTestContract",
        "ProjectScaffoldReport",
        "ProjectImportReport",
        "KiCadForeignImportSummary",
        "ImportInventoryCandidate",
        "ImportInventoryReport",
    }
)


def test_project_models_are_bounded_and_depend_on_contract_owners() -> None:
    path = _REPOSITORY_ROOT / "kicad_tooling/hwrepo/project_models.py"
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
        "collections.abc",
        "enum",
        "typing",
        "pydantic",
        "connector_coverage_models",
        "design_lint_policy_models",
        "model_primitives",
    }


def test_production_modules_import_project_contracts_from_their_owner() -> None:
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
            imported = _PROJECT_MODEL_NAMES.intersection(alias.name for alias in node.names)
            if imported:
                names = ", ".join(sorted(imported))
                violations.append(f"{path.relative_to(_REPOSITORY_ROOT)}:{node.lineno}: {names}")

    assert not violations, "Production imports must use project_models: " + "; ".join(violations)


def test_registry_exports_and_project_json_contracts_remain_compatible() -> None:
    for name in _PROJECT_MODEL_NAMES:
        assert getattr(models, name) is getattr(project_models, name)

    ignored = project_models.IgnoredChecks(erc=(), drc=())
    identity = project_models.ComponentIdentity(required=False, part_ids=())
    validation = project_models.PcbOnlyValidationContract(
        kind=project_models.ProjectKind.PCB_ONLY,
        expected_ignored_checks=ignored,
    )
    config = project_models.ProjectConfig(
        schema_version="1",
        kind=project_models.ProjectKind.PCB_ONLY,
        assurance_profile="development",
        not_for_manufacture=True,
        project_id="board-1",
        component_identity=identity,
        toolchain_id="kicad-10",
        kicad_version="10.0.5",
        image="example.invalid/kicad:10.0.5",
        project="projects/board-1/board-1.kicad_pro",
        source_roots=("projects/board-1",),
        required_inputs=(),
        validation=validation,
    )

    assert models.ProjectConfig.model_validate_json(config.model_dump_json()) == config
    assert (
        models.ProjectConfig.model_json_schema() == project_models.ProjectConfig.model_json_schema()
    )
