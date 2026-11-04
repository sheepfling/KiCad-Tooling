"""Guard theme-owned admission for netlist-bound heuristic coverage."""

from __future__ import annotations

import ast
from collections.abc import Callable
from dataclasses import fields
from pathlib import Path
from typing import Any, get_type_hints

import pytest

from kicad_tooling.hwrepo.control_input_bias import (
    ControlInputBiasCoverageRequest,
    ControlInputBiasCoverageResolution,
    resolve_control_input_bias_coverage,
)
from kicad_tooling.hwrepo.i2c_pullup_heuristics import (
    I2cPullupCoverageRequest,
    I2cPullupCoverageResolution,
    resolve_i2c_pullup_coverage,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.power_lint,
    pytest.mark.architecture,
]

_ROOT = Path(__file__).parents[1]


@pytest.mark.parametrize(
    ("request_type", "resolution_type", "resolver", "coverage_argument"),
    (
        (
            ControlInputBiasCoverageRequest,
            ControlInputBiasCoverageResolution,
            resolve_control_input_bias_coverage,
            "request.control_input_bias_coverage",
        ),
        (
            I2cPullupCoverageRequest,
            I2cPullupCoverageResolution,
            resolve_i2c_pullup_coverage,
            "request.i2c_pullup_heuristic_coverage",
        ),
    ),
)
def test_evaluation_preparation_uses_each_theme_owned_admission_request(
    request_type: type[Any],
    resolution_type: type[Any],
    resolver: Callable[..., Any],
    coverage_argument: str,
) -> None:
    assert {item.name for item in fields(request_type)} == {
        "coverage",
        "current_netlist_sha256",
    }
    assert {item.name for item in fields(resolution_type)} == {"coverage", "binding_issue"}
    assert request_type.__module__ == resolver.__module__
    assert get_type_hints(resolver)["request"] is request_type
    assert get_type_hints(resolver)["return"] is resolution_type

    preparation_path = _ROOT / "kicad_tooling/hwrepo/design_lint_evaluation_preparation.py"
    tree = ast.parse(preparation_path.read_text(encoding="utf-8"))
    request_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == request_type.__name__
    ]
    resolver_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == resolver.__name__
    ]
    assert len(request_calls) == len(resolver_calls) == 1
    request_arguments = {
        keyword.arg: ast.unparse(keyword.value) for keyword in request_calls[0].keywords
    }
    assert request_arguments == {
        "coverage": coverage_argument,
        "current_netlist_sha256": "coach.netlist_sha256",
    }
    assert len(resolver_calls[0].args) == 1
    assert resolver_calls[0].args[0] is request_calls[0]
