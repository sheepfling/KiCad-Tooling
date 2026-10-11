"""Architecture guards for the focused design-lint report model owner."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import get_args

import pytest

from kicad_tooling.hwrepo import design_lint_report_models, models

pytestmark = [pytest.mark.design_lint, pytest.mark.architecture]

REPOSITORY = Path(__file__).resolve().parents[1]
TOOLING = REPOSITORY / "kicad_tooling"
OWNER = TOOLING / "hwrepo" / "design_lint_report_models.py"


def test_design_lint_report_owner_stays_below_review_limit() -> None:
    assert len(OWNER.read_text(encoding="utf-8").splitlines()) < 500


def test_internal_services_import_report_from_its_owner() -> None:
    legacy_imports: list[str] = []
    for path in TOOLING.rglob("*.py"):
        if path == TOOLING / "hwrepo" / "models.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.as_posix())
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or node.module is None:
                continue
            is_compatibility_registry = node.module in {"models", "hwrepo.models"} or (
                node.module.endswith(".models") and not node.module.endswith("_models")
            )
            if is_compatibility_registry and any(
                alias.name == "DesignLintReport" for alias in node.names
            ):
                legacy_imports.append(path.relative_to(REPOSITORY).as_posix())

    assert not legacy_imports, f"Internal services use the compatibility registry: {legacy_imports}"


def test_models_compatibility_export_and_forward_field_use_the_owner() -> None:
    assert models.DesignLintReport is design_lint_report_models.DesignLintReport
    annotation = models.ProjectVerificationReport.model_fields["design_lint"].annotation
    assert design_lint_report_models.DesignLintReport in get_args(annotation)

    model_tree = ast.parse((TOOLING / "hwrepo" / "models.py").read_text(encoding="utf-8"))
    local_report_definitions = [
        node.name
        for node in model_tree.body
        if isinstance(node, ast.ClassDef) and node.name == "DesignLintReport"
    ]
    assert local_report_definitions == []
