"""Keep connector native acceptance selectable and pytest-native."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.interface_lint,
    pytest.mark.architecture,
]

_DIGITAL_PEER_SUITES = {
    "test_ci_hosted_digital_peer_spi.py": {"interface_lint"},
    "test_ci_hosted_digital_peer_serial.py": {
        "connector_lint",
        "interface_lint",
        "return_path_lint",
    },
    "test_ci_hosted_component_peer_power.py": {
        "component_lint",
        "interface_lint",
        "power_lint",
    },
}


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


def test_native_digital_peer_suites_are_pytest_native_and_theme_scoped() -> None:
    legacy_suite = Path(__file__).with_name("test_ci_hosted_digital_peers.py")
    assert not legacy_suite.exists()

    for filename, area_markers in _DIGITAL_PEER_SUITES.items():
        source_path = Path(__file__).with_name(filename)
        source = source_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        assert len(source.splitlines()) < 500
        assert not any(
            isinstance(node, ast.Import)
            and any(alias.name == "unittest" for alias in node.names)
            or isinstance(node, ast.ImportFrom)
            and node.module == "unittest"
            or isinstance(node, ast.ClassDef)
            for node in ast.walk(tree)
        )
        assert any(
            isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
            for node in tree.body
        )
        assert "pytest.mark.design_lint" in source
        assert "pytest.mark.native_kicad" in source
        for marker in area_markers:
            assert f"pytest.mark.{marker}" in source

    support_path = Path(__file__).with_name("digital_peer_native_acceptance.py")
    support_tree = ast.parse(support_path.read_text(encoding="utf-8"))
    native_fixture = next(
        node
        for node in support_tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "native_digital_peer_results"
    )
    assert any(
        isinstance(decorator, ast.Call)
        and ast.unparse(decorator.func) == "pytest.fixture"
        and any(
            keyword.arg == "scope"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value == "session"
            for keyword in decorator.keywords
        )
        for decorator in native_fixture.decorator_list
    )
