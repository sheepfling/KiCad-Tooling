"""Project verification request ownership and surface routing stay explicit."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from pydantic import ValidationError

from kicad_tooling.hwrepo.native_project_validation_models import (
    NativeProjectValidationRequest,
)
from kicad_tooling.hwrepo.project_verification_models import ProjectVerificationRequest

pytestmark = pytest.mark.architecture

_ROOT = Path(__file__).parents[1]


def _function(path: Path, name: str) -> ast.FunctionDef:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return next(
        node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == name
    )


def _calls(function: ast.FunctionDef) -> set[str]:
    return {
        node.func.id
        for node in ast.walk(function)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }


def test_request_rejects_unknown_fields_and_incompatible_runner_depth() -> None:
    with pytest.raises(ValidationError):
        ProjectVerificationRequest.model_validate(
            {"project_id": "controller", "opaque_options": {"fast": True}}
        )

    with pytest.raises(ValidationError, match="requires native depth"):
        ProjectVerificationRequest(project_id="controller", runner="local")


def test_cli_and_mcp_adapters_construct_the_shared_typed_operation() -> None:
    cli = _ROOT / "kicad_tooling/verify.py"
    mcp = _ROOT / "kicad_tooling/hwrepo/mcp_server.py"
    service = _ROOT / "kicad_tooling/hwrepo/project_verification.py"

    assert {"verify_request", "ProjectVerificationRequest"} <= _calls(_function(cli, "main"))
    assert {"verify_request", "ProjectVerificationRequest"} <= _calls(
        _function(mcp, "check_project")
    )
    assert "verify_request" in {
        node.name
        for node in ast.walk(ast.parse(service.read_text(encoding="utf-8")))
        if isinstance(node, ast.FunctionDef)
    }
    service_imports = ast.walk(ast.parse(service.read_text(encoding="utf-8")))
    assert not any(
        isinstance(node, ast.ImportFrom)
        and (
            (node.module or "").startswith(("mcp_", "kicad_tooling.hwrepo.mcp_"))
            or node.module == "mcp_server"
            or (node.module is None and any(alias.name.startswith("mcp_") for alias in node.names))
        )
        for node in service_imports
    )

    stage_modules = {
        node.module
        for node in ast.walk(ast.parse(service.read_text(encoding="utf-8")))
        if isinstance(node, ast.ImportFrom) and node.level == 2
    }
    assert stage_modules == set()


def test_legacy_verify_api_builds_the_same_request_contract() -> None:
    adapter = _function(_ROOT / "kicad_tooling/verify.py", "verify")
    assert {"verify_request", "ProjectVerificationRequest"} <= _calls(adapter)


def test_project_check_adapters_use_owned_stage_requests() -> None:
    ci = _ROOT / "kicad_tooling/ci.py"
    native_cli = _ROOT / "kicad_tooling/check_all.py"
    mcp = _ROOT / "kicad_tooling/hwrepo/mcp_checks.py"

    assert {"run_project_static_pipeline", "ProjectStaticPipelineRequest"} <= _calls(
        _function(ci, "static_pipeline")
    )
    assert {"run_native_project_check", "NativeProjectCheckRequest"} <= _calls(
        _function(native_cli, "main")
    )
    assert {"run_native_project_check", "NativeProjectCheckRequest"} <= _calls(
        _function(mcp, "check_native_scope")
    )


def test_stage_requests_reject_unknown_fields_and_invalid_workers() -> None:
    from kicad_tooling.hwrepo.native_project_check_models import NativeProjectCheckRequest
    from kicad_tooling.hwrepo.project_static_pipeline_models import ProjectStaticPipelineRequest

    with pytest.raises(ValidationError):
        ProjectStaticPipelineRequest(project_ids=("controller",), workers=0)
    with pytest.raises(ValidationError):
        NativeProjectCheckRequest.model_validate(
            {"output": Path("build/native"), "untyped_policy": {"bypass": True}}
        )


def test_native_validation_request_is_strict_and_requires_a_cli() -> None:
    with pytest.raises(ValidationError):
        NativeProjectValidationRequest.model_validate(
            {"output": Path("build/native/project"), "cli": "kicad-cli", "policy": "skip"}
        )
    with pytest.raises(ValidationError):
        NativeProjectValidationRequest(output=Path("build/native/project"), cli="")


def test_native_validation_adapters_use_the_typed_service() -> None:
    facade = _ROOT / "kicad_tooling/validate.py"
    native_stage = _ROOT / "kicad_tooling/hwrepo/native_project_check.py"
    release = _ROOT / "kicad_tooling/hwrepo/releasing.py"

    assert {"validate_project", "NativeProjectValidationRequest"} <= _calls(
        _function(facade, "validate")
    )
    assert {"validate_project", "NativeProjectValidationRequest"} <= _calls(
        _function(native_stage, "run_native_project_check")
    )
    assert {"validate_project", "NativeProjectValidationRequest"} <= _calls(
        _function(release, "run_native")
    )
