"""Guard typed diagnostic requests and their adapter routes."""

from __future__ import annotations

import ast
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo.diagnostic_journal import DiagnosticJournal
from kicad_tooling.hwrepo.diagnostic_operation_models import (
    ImportDiagnosticRequest,
    ProjectDiagnosticRequest,
    ProjectRescueRequest,
)
from kicad_tooling.hwrepo.diagnostics import diagnose_import_request, diagnose_project_request
from kicad_tooling.hwrepo.project_static_pipeline_models import ProjectStaticPipelineReport
from kicad_tooling.hwrepo.rescue import rescue_project_request

pytestmark = pytest.mark.architecture

_ROOT = Path(__file__).parents[1]


def _function(path: Path, name: str) -> ast.FunctionDef:
    return next(
        node
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, ast.FunctionDef) and node.name == name
    )


def _calls(function: ast.FunctionDef) -> set[str]:
    return {
        node.func.id if isinstance(node.func, ast.Name) else node.func.attr
        for node in ast.walk(function)
        if isinstance(node, ast.Call) and isinstance(node.func, (ast.Name, ast.Attribute))
    }


def test_requests_are_strict_and_bind_evidence_to_the_selected_project() -> None:
    with pytest.raises(ValidationError):
        ImportDiagnosticRequest.model_validate(
            {
                "source": "incoming/controller.kicad_pro",
                "project_id": "controller",
                "toolchain_id": "kicad-10",
                "bypass": True,
            }
        )
    with pytest.raises(ValidationError):
        ProjectRescueRequest.model_validate({"project_id": "controller", "full_gate": True})
    with pytest.raises(ValidationError, match="requires the selected project's native_report"):
        ProjectDiagnosticRequest(project_id="controller", bom=Path("build/bom.csv"))

    captured = ProjectStaticPipelineReport.model_construct(projects=("other-board",))
    with pytest.raises(ValidationError, match="does not match the diagnosed project"):
        ProjectDiagnosticRequest(project_id="controller", portable_report=captured)


def test_diagnostic_operations_reject_a_receipt_for_another_scope() -> None:
    with TemporaryDirectory(prefix="diagnostic-operation-scope-") as temporary:
        root = Path(temporary)
        journal = DiagnosticJournal(root, "another-project")

        with pytest.raises(ValueError, match="receipt scope"):
            diagnose_import_request(
                root,
                ImportDiagnosticRequest(
                    source=root / "incoming.kicad_pro",
                    project_id="controller",
                    toolchain_id="kicad-10",
                ),
                journal,
            )
        with pytest.raises(ValueError, match="receipt scope"):
            diagnose_project_request(
                root, ProjectDiagnosticRequest(project_id="controller"), journal
            )
        with pytest.raises(ValueError, match="receipt scope"):
            rescue_project_request(root, ProjectRescueRequest(project_id="controller"), journal)

        with TemporaryDirectory(prefix="diagnostic-operation-other-root-") as other_temporary:
            other_root = Path(other_temporary)
            other_journal = DiagnosticJournal(other_root, "controller")
            with pytest.raises(ValueError, match="receipt scope"):
                diagnose_project_request(
                    root,
                    ProjectDiagnosticRequest(project_id="controller"),
                    other_journal,
                )


def test_cli_mcp_and_composed_services_build_typed_diagnostic_requests() -> None:
    cli = _ROOT / "kicad_tooling/template.py"
    workflow = _ROOT / "kicad_tooling/hwrepo/mcp_workflow.py"
    verification = _ROOT / "kicad_tooling/hwrepo/project_verification.py"
    import_review = _ROOT / "kicad_tooling/hwrepo/import_review.py"

    cli_calls = _calls(_function(cli, "main"))
    assert {
        "diagnose_import_request",
        "diagnose_project_request",
        "rescue_project",
        "ImportDiagnosticRequest",
        "ProjectDiagnosticRequest",
    } <= cli_calls

    assert {"diagnose_import_request", "ImportDiagnosticRequest"} <= _calls(
        _function(workflow, "diagnose_import")
    )
    assert {"diagnose_project_request", "ProjectDiagnosticRequest"} <= _calls(
        _function(workflow, "diagnose_project")
    )
    assert {"rescue_project_request", "ProjectRescueRequest"} <= _calls(
        _function(workflow, "rescue_project")
    )
    assert {"rescue_project_request", "ProjectRescueRequest"} <= _calls(
        _function(_ROOT / "kicad_tooling/hwrepo/rescue.py", "rescue_project")
    )
    assert {"diagnose_project_request", "ProjectDiagnosticRequest"} <= _calls(
        _function(verification, "diagnose")
    )
    assert {"diagnose_import_request", "ImportDiagnosticRequest"} <= _calls(
        _function(import_review, "_snapshot")
    )


def test_request_and_response_owners_remain_below_review_limits() -> None:
    for relative in (
        "kicad_tooling/hwrepo/diagnostic_operation_models.py",
        "kicad_tooling/hwrepo/diagnostics_models.py",
    ):
        path = _ROOT / relative
        assert len(path.read_text(encoding="utf-8").splitlines()) < 500
