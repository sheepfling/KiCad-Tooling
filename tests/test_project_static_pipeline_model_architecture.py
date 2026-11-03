"""Guard ownership of portable project pipeline reports."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from kicad_tooling.hwrepo import (
    governance_lint_models,
    models,
    project_static_pipeline_models,
    repository_policy_models,
)
from kicad_tooling.hwrepo.policy_issue_models import PolicyIssue
from kicad_tooling.hwrepo.product_models import ProductPolicyReport

pytestmark = pytest.mark.architecture

_ROOT = Path(__file__).parents[1]
_MODEL_NAMES = frozenset(
    {
        "GenerationReport",
        "GovernanceLintReport",
        "ProjectStaticPipelineReport",
        "ProjectTestsReport",
        "RepositoryPolicyReport",
    }
)


def _imports(path: Path) -> set[str]:
    return {
        node.module
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, ast.ImportFrom)
        and node.module is not None
        and node.module != "__future__"
    }


def test_portable_pipeline_model_owners_are_small_with_explicit_dependencies() -> None:
    owners = {
        "governance_lint_models.py": {"typing", "model_primitives"},
        "repository_policy_models.py": {"typing", "model_primitives"},
        "project_static_pipeline_models.py": {
            "collections.abc",
            "typing",
            "pydantic",
            "command_evidence_models",
            "governance_lint_models",
            "model_primitives",
            "product_models",
            "repository_policy_models",
        },
    }
    for name, expected_imports in owners.items():
        path = _ROOT / "kicad_tooling/hwrepo" / name
        assert len(path.read_text(encoding="utf-8").splitlines()) < 500
        assert _imports(path) == expected_imports


def test_production_consumers_import_portable_reports_from_their_owners() -> None:
    tooling = _ROOT / "kicad_tooling"
    registry = tooling / "hwrepo/models.py"
    violations: list[str] = []

    for path in tooling.rglob("*.py"):
        if path == registry:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.ImportFrom) or node.module not in {
                "models",
                "hwrepo.models",
                "kicad_tooling.hwrepo.models",
            }:
                continue
            misplaced = _MODEL_NAMES.intersection(alias.name for alias in node.names)
            if misplaced:
                violations.append(f"{path.relative_to(_ROOT)}:{node.lineno}: {sorted(misplaced)}")

    assert not violations, "Import portable reports from their owners: " + "; ".join(violations)


def test_registry_exports_preserve_identity_and_portable_report_json() -> None:
    assert models.GovernanceLintReport is governance_lint_models.GovernanceLintReport
    assert models.RepositoryPolicyReport is repository_policy_models.RepositoryPolicyReport
    for name in ("GenerationReport", "ProjectStaticPipelineReport", "ProjectTestsReport"):
        assert getattr(models, name) is getattr(project_static_pipeline_models, name)

    report = project_static_pipeline_models.ProjectStaticPipelineReport(
        status="FAIL",
        projects=("controller",),
        registry=governance_lint_models.GovernanceLintReport(
            projects=("controller",), issues=(), status="PASS"
        ),
        repository=repository_policy_models.RepositoryPolicyReport(status="PASS", issues=()),
        product=ProductPolicyReport(
            status="FAIL",
            products=(),
            open_items={},
            issues=(PolicyIssue(code="POLICY", location="project", message="reviewed"),),
        ),
        generation=project_static_pipeline_models.GenerationReport(status="PASS", issues=()),
        project_tests=project_static_pipeline_models.ProjectTestsReport(status="PASS", commands={}),
    )

    assert (
        models.ProjectStaticPipelineReport.model_validate_json(report.model_dump_json()) == report
    )
