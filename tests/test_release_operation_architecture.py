"""Keep release preparation requests and surface routes capability-owned."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from kicad_tooling.hwrepo import models, release_operation_models

pytestmark = pytest.mark.architecture

_ROOT = Path(__file__).parents[1]


def _tree(path: str) -> ast.Module:
    return ast.parse((_ROOT / path).read_text(encoding="utf-8"))


def _function(tree: ast.Module, name: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    return next(
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name
    )


def _called_names(function: ast.AST) -> set[str]:
    return {
        call.func.id if isinstance(call.func, ast.Name) else call.func.attr
        for call in ast.walk(function)
        if isinstance(call, ast.Call) and isinstance(call.func, (ast.Name, ast.Attribute))
    }


def test_release_preparation_request_has_one_operation_model_owner() -> None:
    owner = Path(release_operation_models.__file__)
    assert len(owner.read_text(encoding="utf-8").splitlines()) < 500
    assert release_operation_models.ReleasePreparationRequest.model_config.get("frozen") is True
    assert release_operation_models.ReleasePreparationRequest.model_config.get("extra") == "forbid"
    assert not hasattr(models, "ReleasePreparationRequest")


def test_release_prepare_is_a_compatibility_adapter_to_the_typed_operation() -> None:
    tree = _tree("kicad_tooling/hwrepo/releasing.py")
    adapter = _function(tree, "prepare")
    assert _called_names(adapter) == {"prepare_request", "ReleasePreparationRequest"}
    request_calls = [
        node
        for node in ast.walk(adapter)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "ReleasePreparationRequest"
    ]
    assert len(request_calls) == 1
    assert {keyword.arg for keyword in request_calls[0].keywords if keyword.arg is not None} == {
        "release_id",
        "project_ids",
        "variants",
        "release_class",
        "cli",
        "portable",
        "ngspice",
    }


@pytest.mark.parametrize(
    ("path", "function_name"),
    (
        ("kicad_tooling/release.py", "main"),
        ("kicad_tooling/hwrepo/mcp_workflow.py", "prepare_review_scope"),
    ),
)
def test_cli_and_mcp_construct_the_same_typed_preparation_request(
    path: str, function_name: str
) -> None:
    function = _function(_tree(path), function_name)
    calls = _called_names(function)
    assert "prepare_request" in calls
    assert "ReleasePreparationRequest" in calls
    assert "prepare" not in calls
