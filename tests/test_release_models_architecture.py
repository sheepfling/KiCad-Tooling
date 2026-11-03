"""Guard release report model ownership and compatibility exports."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from kicad_tooling.hwrepo import models, release_model_types, release_report_models
from kicad_tooling.hwrepo.policy_issue_models import PolicyIssue

pytestmark = pytest.mark.architecture

_REPOSITORY_ROOT = Path(__file__).parents[1]
_RELEASE_TYPE_NAMES = frozenset({"ReleaseClass"})
_RELEASE_REPORT_NAMES = frozenset({"ReleasePackageReport", "ReleaseReadinessReport"})


def _owner_imports(path: Path) -> set[str]:
    return {
        node.module
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, ast.ImportFrom)
        and node.module is not None
        and node.module != "__future__"
    }


def test_release_model_owners_are_small_and_have_closed_dependencies() -> None:
    type_path = _REPOSITORY_ROOT / "kicad_tooling/hwrepo/release_model_types.py"
    report_path = _REPOSITORY_ROOT / "kicad_tooling/hwrepo/release_report_models.py"

    assert len(type_path.read_text(encoding="utf-8").splitlines()) < 500
    assert len(report_path.read_text(encoding="utf-8").splitlines()) < 500
    assert _owner_imports(type_path) == {"enum"}
    assert _owner_imports(report_path) == {
        "typing",
        "model_primitives",
        "policy_issue_models",
        "release_model_types",
    }


def test_production_modules_import_release_models_from_their_owners() -> None:
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
            names = {alias.name for alias in node.names}
            misplaced = (_RELEASE_TYPE_NAMES | _RELEASE_REPORT_NAMES) & names
            if misplaced:
                violations.append(
                    f"{path.relative_to(_REPOSITORY_ROOT)}:{node.lineno}: {sorted(misplaced)}"
                )

    assert not violations, "Production imports must use release model owners: " + "; ".join(
        violations
    )


def test_models_registry_reexports_preserve_release_identity_and_json() -> None:
    assert models.ReleaseClass is release_model_types.ReleaseClass
    assert models.ReleasePackageReport is release_report_models.ReleasePackageReport
    assert models.ReleaseReadinessReport is release_report_models.ReleaseReadinessReport

    readiness = release_report_models.ReleaseReadinessReport(
        release_id="candidate-1",
        release_class=release_model_types.ReleaseClass.ENGINEERING_REVIEW,
        status="FAIL",
        issues=(PolicyIssue(code="SOURCE", location="manifest", message="source changed"),),
    )
    package = release_report_models.ReleasePackageReport(
        status="PASS",
        source_commit="a" * 40,
        package="build/packages/release.zip",
        package_sha256="b" * 64,
        manifest="build/releases/candidate-1/manifest.json",
    )

    assert (
        models.ReleaseReadinessReport.model_validate_json(readiness.model_dump_json()) == readiness
    )
    assert models.ReleasePackageReport.model_validate_json(package.model_dump_json()) == package
