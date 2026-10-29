"""Surface and shared policy records have transport-neutral owners."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from kicad_tooling.hwrepo import models, policy_issue_models, surface_models
from kicad_tooling.hwrepo.contracts import read_model

pytestmark = pytest.mark.architecture
PACKAGE = Path(__file__).parents[1] / "kicad_tooling/hwrepo"
SURFACE_NAMES = (
    "ToolCliSnapshot",
    "ToolMcpSnapshot",
    "ToolSurfaceMapping",
    "ToolSurfacesCatalog",
    "ToolSurfaceReport",
)


@pytest.mark.parametrize("name", SURFACE_NAMES)
def test_surface_legacy_exports_keep_type_identity(name: str) -> None:
    assert getattr(models, name) is getattr(surface_models, name)


def test_policy_issue_legacy_export_keeps_type_identity() -> None:
    assert models.PolicyIssue is policy_issue_models.PolicyIssue
    assert surface_models.PolicyIssue is policy_issue_models.PolicyIssue


def test_internal_services_import_policy_issue_from_its_owner() -> None:
    violations: list[str] = []
    for path in PACKAGE.glob("*.py"):
        if path.name == "models.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.ImportFrom)
                and node.module in {"models", "kicad_tooling.hwrepo.models"}
                and any(alias.name == "PolicyIssue" for alias in node.names)
            ):
                violations.append(path.name)
    assert not violations, f"Import PolicyIssue from policy_issue_models: {violations}"


def test_saved_catalog_and_report_round_trip_through_owner() -> None:
    catalog = read_model(PACKAGE.parent / "tool-surfaces.json", models.ToolSurfacesCatalog)
    assert (
        surface_models.ToolSurfacesCatalog.model_validate_json(catalog.model_dump_json()) == catalog
    )
    report = models.ToolSurfaceReport(
        status="FAIL",
        coverage_status="PASS",
        parity_status="FAIL",
        mcp_verification="STATIC_ONLY",
        cli=catalog.cli,
        mcp=catalog.mcp,
        capabilities=catalog.capabilities,
        issues=(models.PolicyIssue(code="PARITY", location="fixture", message="Review parity"),),
    )
    restored = surface_models.ToolSurfaceReport.model_validate_json(report.model_dump_json())
    assert restored == report
    assert restored.issues[0] == policy_issue_models.PolicyIssue(
        code="PARITY", location="fixture", message="Review parity"
    )


def test_owners_do_not_import_registry_and_surface_consumers_import_owner() -> None:
    for filename in ("surface_models.py", "policy_issue_models.py"):
        source = (PACKAGE / filename).read_text(encoding="utf-8")
        assert len(source.splitlines()) < 500
        tree = ast.parse(source)
        assert all(
            node.module != "models" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
        )
    for filename in ("surface.py", "mcp_server.py"):
        tree = ast.parse((PACKAGE / filename).read_text(encoding="utf-8"))
        assert any(
            isinstance(node, ast.ImportFrom) and node.module == "surface_models"
            for node in ast.walk(tree)
        )
        assert not any(
            isinstance(node, ast.ImportFrom)
            and node.module == "models"
            and any(alias.name in SURFACE_NAMES for alias in node.names)
            for node in ast.walk(tree)
        )
