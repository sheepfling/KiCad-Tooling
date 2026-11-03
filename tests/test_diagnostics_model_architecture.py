"""Guard diagnostic contract ownership and compatibility exports."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from kicad_tooling.hwrepo import diagnostics_models, models

pytestmark = pytest.mark.architecture

_ROOT = Path(__file__).parents[1]
_MODEL_NAMES = frozenset({"DiagnosticFinding", "DiagnosticReport", "LocalRescueReport"})


def _imports(path: Path) -> set[str]:
    return {
        node.module
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, ast.ImportFrom)
        and node.module is not None
        and node.module != "__future__"
    }


def test_diagnostic_contract_owner_has_only_primitive_dependencies() -> None:
    owner = _ROOT / "kicad_tooling/hwrepo/diagnostics_models.py"

    assert len(owner.read_text(encoding="utf-8").splitlines()) < 500
    assert _imports(owner) == {"typing", "model_primitives"}


def test_production_consumers_import_diagnostic_models_from_the_owner() -> None:
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

    assert not violations, "Import diagnostic records from their owner: " + "; ".join(violations)


def test_compatibility_exports_keep_identity_and_json_contracts() -> None:
    assert models.DiagnosticFinding is diagnostics_models.DiagnosticFinding
    assert models.DiagnosticReport is diagnostics_models.DiagnosticReport
    assert models.LocalRescueReport is diagnostics_models.LocalRescueReport

    finding = diagnostics_models.DiagnosticFinding(
        severity="BLOCKING",
        code="PROJECT_CONFIG",
        location="projects/controller/project.json",
        observed="The project configuration is invalid.",
        action="Repair the authored project configuration.",
        guide="docs/workflow/DIAGNOSTICS.md",
    )
    report = diagnostics_models.DiagnosticReport(
        project_id="controller",
        scope="project",
        status="NEEDS_WORK",
        findings=(finding,),
        next_command="kicad_tooling.template diagnose --project-id controller",
    )
    rescue = diagnostics_models.LocalRescueReport(
        project_id="controller",
        local_inspection="NEEDS_REPAIR",
        findings=(finding,),
        omitted_checks=("Global registry uniqueness",),
        next_command="kicad_tooling.template diagnose --project-id controller",
        run_directory="build/diagnostics/controller",
    )

    assert (
        diagnostics_models.DiagnosticReport.model_validate_json(report.model_dump_json()) == report
    )
    assert (
        diagnostics_models.LocalRescueReport.model_validate_json(rescue.model_dump_json()) == rescue
    )
