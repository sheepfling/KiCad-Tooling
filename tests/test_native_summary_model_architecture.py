"""Guard doctor and native project-summary model ownership."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from kicad_tooling.hwrepo import doctor_models, models, native_project_check_models
from kicad_tooling.hwrepo.governance_lint_models import GovernanceLintReport
from kicad_tooling.hwrepo.product_models import ProductPolicyReport
from kicad_tooling.hwrepo.repository_policy_models import RepositoryPolicyReport

pytestmark = pytest.mark.architecture

_ROOT = Path(__file__).parents[1]
_MODEL_NAMES = frozenset(
    {"CheckAllSummary", "EnvironmentCheck", "ProjectCheckSummary", "TemplateDoctorReport"}
)


def _imports(path: Path) -> set[str]:
    return {
        node.module
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, ast.ImportFrom)
        and node.module is not None
        and node.module != "__future__"
    }


def test_doctor_and_native_summary_owners_have_explicit_dependencies() -> None:
    doctor_owner = _ROOT / "kicad_tooling/hwrepo/doctor_models.py"
    native_owner = _ROOT / "kicad_tooling/hwrepo/native_project_check_models.py"

    assert len(doctor_owner.read_text(encoding="utf-8").splitlines()) < 500
    assert len(native_owner.read_text(encoding="utf-8").splitlines()) < 500
    assert _imports(doctor_owner) == {"typing", "model_primitives"}
    assert _imports(native_owner) == {
        "pathlib",
        "typing",
        "governance_lint_models",
        "model_primitives",
        "product_models",
        "repository_policy_models",
    }


def test_production_services_import_doctor_and_native_reports_from_owners() -> None:
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

    assert not violations, "Import operation reports from their owners: " + "; ".join(violations)


def test_models_registry_preserves_identity_and_json_contracts() -> None:
    assert models.EnvironmentCheck is doctor_models.EnvironmentCheck
    assert models.TemplateDoctorReport is doctor_models.TemplateDoctorReport
    assert models.ProjectCheckSummary is native_project_check_models.ProjectCheckSummary
    assert models.CheckAllSummary is native_project_check_models.CheckAllSummary

    doctor = doctor_models.TemplateDoctorReport(
        native_requested=False,
        status="PASS",
        checks=(
            doctor_models.EnvironmentCheck(
                id="python",
                required=True,
                status="PASS",
                expected="Python 3.11 or newer",
                observed="3.11.9",
                next_action="Continue",
            ),
        ),
    )
    native = native_project_check_models.CheckAllSummary(
        governance=GovernanceLintReport(projects=("board",), issues=(), status="PASS"),
        repository=RepositoryPolicyReport(status="PASS", issues=()),
        product_policy=ProductPolicyReport(status="PASS", products=(), open_items={}, issues=()),
        projects=(
            native_project_check_models.ProjectCheckSummary(
                id="board", status="PASS", summary="build/native/board.json"
            ),
        ),
        status="PASS",
    )

    assert models.TemplateDoctorReport.model_validate_json(doctor.model_dump_json()) == doctor
    assert models.CheckAllSummary.model_validate_json(native.model_dump_json()) == native
