"""Guard documentation policy model ownership and compatibility exports."""

from __future__ import annotations

import ast
from datetime import date
from pathlib import Path

import pytest

from kicad_tooling.hwrepo import documentation_models, models

pytestmark = pytest.mark.architecture

_ROOT = Path(__file__).parents[1]
_MODEL_NAMES = frozenset(
    {
        "DocumentationException",
        "DocumentationIssue",
        "DocumentationPolicy",
        "DocumentationPolicyReport",
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


def test_documentation_model_owner_has_only_primitive_dependencies() -> None:
    owner = _ROOT / "kicad_tooling/hwrepo/documentation_models.py"

    assert len(owner.read_text(encoding="utf-8").splitlines()) < 500
    assert _imports(owner) == {"datetime", "typing", "model_primitives"}


def test_production_consumers_import_documentation_models_from_the_owner() -> None:
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

    assert not violations, "Import documentation models from their owner: " + "; ".join(violations)


def test_registry_exports_preserve_documentation_identity_and_json() -> None:
    for name in _MODEL_NAMES:
        assert getattr(models, name) is getattr(documentation_models, name)

    policy = documentation_models.DocumentationPolicy(
        roots=("README.md",),
        exceptions=(
            documentation_models.DocumentationException(
                id="api-reference",
                code="MD001",
                path="docs/reference.md",
                reason="Generated heading order",
                expires=date(2027, 1, 31),
            ),
        ),
    )
    report = documentation_models.DocumentationPolicyReport(
        roots=policy.roots,
        documents=1,
        issues=(
            documentation_models.DocumentationIssue(
                code="MD001",
                path="docs/reference.md",
                line=3,
                message="Heading levels should not be skipped",
            ),
        ),
        status="FAIL",
    )

    assert models.DocumentationPolicy.model_validate_json(policy.model_dump_json()) == policy
    assert models.DocumentationPolicyReport.model_validate_json(report.model_dump_json()) == report
