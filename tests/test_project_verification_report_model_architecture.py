"""Guard project-verification report ownership and compatibility exports."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from kicad_tooling.hwrepo import models, project_verification_report_models
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport

pytestmark = pytest.mark.architecture

_ROOT = Path(__file__).parents[1]
_OWNER = _ROOT / "kicad_tooling/hwrepo/project_verification_report_models.py"


def _imports(path: Path) -> set[str]:
    return {
        node.module
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, ast.ImportFrom)
        and node.module is not None
        and node.module != "__future__"
    }


def test_report_owner_has_only_typed_contract_dependencies() -> None:
    assert len(_OWNER.read_text(encoding="utf-8").splitlines()) < 500
    assert _imports(_OWNER) == {
        "typing",
        "command_evidence_models",
        "design_lint_report_models",
        "diagnostics_models",
        "doctor_models",
        "electrical_report_models",
        "model_primitives",
        "native_project_check_models",
        "project_static_pipeline_models",
    }


def test_production_consumers_import_report_from_its_owner() -> None:
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
            if any(alias.name == "ProjectVerificationReport" for alias in node.names):
                violations.append(f"{path.relative_to(_ROOT)}:{node.lineno}")

    assert not violations, "Import the report from its owner: " + "; ".join(violations)


def test_registry_export_and_nested_lint_report_keep_the_typed_json_contract() -> None:
    report_type = project_verification_report_models.ProjectVerificationReport
    assert models.ProjectVerificationReport is report_type
    assert report_type.model_fields["design_lint"].annotation == DesignLintReport | None

    lint = DesignLintReport(project_id="controller", status="BLOCKED")
    report = report_type(
        project_id="controller",
        depth="portable",
        run_directory="build/verify/controller",
        design_lint=lint,
        status="FAIL",
    )
    assert report_type.model_validate_json(report.model_dump_json()) == report
