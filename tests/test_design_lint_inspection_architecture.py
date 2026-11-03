"""Keep design-lint inspection requests typed and shared by the application surfaces."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo import design_lint
from kicad_tooling.hwrepo.design_lint_inspection_models import DesignLintInspectionRequest

pytestmark = pytest.mark.architecture

REPOSITORY_ROOT = Path(__file__).parents[1]
PACKAGE = REPOSITORY_ROOT / "kicad_tooling"
IMPLEMENTATION_MAX_LINES = 500


def test_inspection_request_has_a_bounded_owner_and_explicit_fields() -> None:
    path = PACKAGE / "hwrepo/design_lint_inspection_models.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
    request = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "DesignLintInspectionRequest"
    )
    fields = {
        node.target.id
        for node in request.body
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    }

    assert len(path.read_text(encoding="utf-8").splitlines()) < IMPLEMENTATION_MAX_LINES
    assert fields == {"project_id", "native_summary"}
    with pytest.raises(ValidationError):
        DesignLintInspectionRequest(
            project_id="controller",
            native_summary=Path("summary.json"),
            evaluator="custom",
        )


def test_legacy_inspection_adapter_builds_the_typed_request(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[tuple[Path, DesignLintInspectionRequest]] = []

    def inspect(root: Path, request: DesignLintInspectionRequest) -> object:
        seen.append((root, request))
        return request

    monkeypatch.setattr(design_lint, "inspect_design_lint_request", inspect)
    root = Path("/checkout")
    native_summary = Path("build/native/summary.json")

    result = design_lint.inspect_summary(root, "controller", native_summary)

    assert result == DesignLintInspectionRequest(
        project_id="controller", native_summary=native_summary
    )
    assert seen == [(root, result)]


@pytest.mark.parametrize(
    "relative_path",
    (
        "design_lint.py",
        "hwrepo/mcp_workflow.py",
        "verify.py",
    ),
)
def test_cli_mcp_and_verify_use_the_shared_typed_operation(relative_path: str) -> None:
    source = (PACKAGE / relative_path).read_text(encoding="utf-8")

    assert "DesignLintInspectionRequest" in source
    assert "inspect_request" in source


def test_inspection_service_owns_evaluation_without_surface_dependencies() -> None:
    path = PACKAGE / "hwrepo/design_lint_project_inspection.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
    imported = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }

    assert "design_lint_evaluator" in imported
    assert "design_lint_inspection_models" in imported
    assert not any(
        module.endswith((".cli", ".mcp_server", ".ci")) or ".mcp_" in module
        for module in imported
    )
