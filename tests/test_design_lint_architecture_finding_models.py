"""Finding and review-policy records have a focused compatibility owner."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import get_args

import pytest

from kicad_tooling.hwrepo import design_lint_finding_models, models
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport

pytestmark = [pytest.mark.design_lint, pytest.mark.architecture]

REPOSITORY = Path(__file__).resolve().parents[1]
TOOLING = REPOSITORY / "kicad_tooling"
OWNER = TOOLING / "hwrepo" / "design_lint_finding_models.py"
COMPATIBILITY_EXPORTS = (
    "DesignLintFinding",
    "DesignLintIgnore",
    "DesignLintRuleOverride",
)


def test_design_lint_finding_owner_stays_below_review_limit() -> None:
    assert len(OWNER.read_text(encoding="utf-8").splitlines()) < 500


def test_compatibility_registry_reexports_owner_identities() -> None:
    for name in COMPATIBILITY_EXPORTS:
        assert getattr(models, name) is getattr(design_lint_finding_models, name)

    assert get_args(models.DesignLintPolicy.model_fields["rules"].annotation)[0] is (
        design_lint_finding_models.DesignLintRuleOverride
    )
    assert get_args(models.DesignLintPolicy.model_fields["ignores"].annotation)[0] is (
        design_lint_finding_models.DesignLintIgnore
    )
    assert get_args(DesignLintReport.model_fields["findings"].annotation)[0] is (
        design_lint_finding_models.DesignLintFinding
    )


def test_internal_code_uses_the_finding_owner_directly() -> None:
    compatibility_imports: list[str] = []
    for path in TOOLING.rglob("*.py"):
        if path == TOOLING / "hwrepo" / "models.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.as_posix())
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or node.module is None:
                continue
            is_compatibility_registry = node.module == "models" or (
                node.module.endswith(".models") and not node.module.endswith("_models")
            )
            if is_compatibility_registry and any(
                alias.name in COMPATIBILITY_EXPORTS for alias in node.names
            ):
                compatibility_imports.append(path.relative_to(REPOSITORY).as_posix())

    assert not compatibility_imports, (
        f"Internal services use the compatibility registry: {compatibility_imports}"
    )
