"""Keep design-lint inspection requests typed and shared by the application surfaces."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo import design_lint
from kicad_tooling.hwrepo.design_lint_inspection_models import DesignLintInspectionRequest

pytestmark = [pytest.mark.architecture, pytest.mark.design_lint]

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
            evaluator="custom",  # type: ignore[call-arg]
        )


def test_legacy_inspection_adapter_builds_the_typed_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
    ("relative_path", "request_type", "operation"),
    (
        ("design_lint.py", "DesignLintInspectionRequest", "inspect_request"),
        ("hwrepo/mcp_workflow.py", "DesignLintInspectionRequest", "inspect_request"),
        ("verify.py", "ProjectVerificationRequest", "verify_request"),
    ),
)
def test_cli_mcp_and_verify_use_their_shared_typed_operation(
    relative_path: str, request_type: str, operation: str
) -> None:
    source = (PACKAGE / relative_path).read_text(encoding="utf-8")

    assert request_type in source
    assert operation in source


def test_inspection_service_owns_evaluation_without_surface_dependencies() -> None:
    path = PACKAGE / "hwrepo/design_lint_project_inspection.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
    imported = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }

    assert "design_lint_evaluator" in imported
    assert "design_lint_evaluation_types" in imported
    assert "design_lint_inspection_models" in imported
    assert any(
        isinstance(node, ast.ImportFrom)
        and node.module == "design_lint_evaluator"
        and "evaluate_request" in {alias.name for alias in node.names}
        for node in ast.walk(tree)
    )
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "evaluate"
        for node in ast.walk(tree)
    )
    assert (
        sum(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "evaluate_request"
            for node in ast.walk(tree)
        )
        == 2
    )
    assert not any(
        module.endswith((".cli", ".mcp_server", ".ci")) or ".mcp_" in module for module in imported
    )


def test_project_inspection_passes_external_protection_into_typed_evaluation() -> None:
    path = PACKAGE / "hwrepo/design_lint_project_inspection.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
    request = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "DesignLintEvaluationRequest"
        and any(keyword.arg == "pcb_input_coverage" for keyword in node.keywords)
    )
    external_protection = next(
        keyword for keyword in request.keywords if keyword.arg == "external_protection_coverage"
    )

    assert isinstance(external_protection.value, ast.Name)
    assert external_protection.value.id == "protection_coverage"


def test_public_evaluator_adapter_is_not_imported_by_internal_services() -> None:
    facade = PACKAGE / "hwrepo/design_lint.py"
    legacy_importers: list[str] = []

    for path in (PACKAGE / "hwrepo").rglob("*.py"):
        if path == facade:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
        if any(
            isinstance(node, ast.ImportFrom)
            and node.module is not None
            and node.module.endswith("design_lint_evaluator")
            and "evaluate" in {alias.name for alias in node.names}
            for node in ast.walk(tree)
        ):
            legacy_importers.append(path.relative_to(PACKAGE).as_posix())

    assert legacy_importers == []
