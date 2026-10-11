"""Keep connector native acceptance selectable and pytest-native."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint, pytest.mark.architecture]


def test_native_connector_acceptance_uses_version_parameterized_pytest() -> None:
    source_path = Path(__file__).with_name("test_ci_hosted_connector_returns.py")
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    assert not any(
        isinstance(node, ast.Import)
        and any(alias.name == "unittest" for alias in node.names)
        or isinstance(node, ast.ImportFrom)
        and node.module == "unittest"
        or isinstance(node, ast.ClassDef)
        for node in ast.walk(tree)
    )

    expected = {
        "test_return_pin_on_positive_rail",
        "test_return_net_and_cross_symbol_findings",
        "test_peer_pin_assignments_and_offboard_scope",
        "test_power_pin_and_reviewed_role_cases",
        "test_grounding_and_pin_connectivity_contracts",
    }
    version_parameterized = {
        node.name
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name in expected
        and any(
            isinstance(decorator, ast.Call)
            and ast.unparse(decorator.func) == "pytest.mark.parametrize"
            and decorator.args
            and isinstance(decorator.args[0], ast.Constant)
            and decorator.args[0].value == "version"
            for decorator in node.decorator_list
        )
    }
    assert version_parameterized == expected
