"""Guard pytest collection and selector behavior for lint suites."""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.design_lint_test_markers import design_lint_markers_for_path

pytestmark = [pytest.mark.design_lint, pytest.mark.architecture]


def test_selector_architecture_suites_are_in_the_catalog_gate() -> None:
    for module in (
        "tests/test_design_lint_architecture_pytest_markers.py",
        "tests/test_design_lint_architecture_pytest_collection.py",
        "tests/test_design_lint_architecture_rule_selectors.py",
        "tests/test_design_lint_architecture_theme_suites.py",
    ):
        assert "catalog_lint" in design_lint_markers_for_path(module)


def test_rule_gate_also_collects_cross_rule_integrity_checks() -> None:
    environment = os.environ.copy()
    environment.pop("KICAD_TEMPLATE_ROOT", None)
    result = subprocess.run(
        (
            sys.executable,
            "-I",
            "-m",
            "pytest",
            "-q",
            "-m",
            'design_lint and (design_lint_rule(rule_id="bus.i2c_missing_pullup") or rule_gate_integrity)',
            "--collect-only",
        ),
        cwd=Path(__file__).resolve().parents[1],
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert (
        "tests/test_design_lint_architecture.py::test_each_active_rule_declares_a_source_owner_function"
        in result.stdout
    )
    assert (
        "tests/test_design_lint_architecture_catalog.py::test_active_rule_fixture_modules_have_design_lint_and_theme_markers"
        in result.stdout
    )
    assert (
        "tests/test_design_lint_architecture_pytest_markers.py::test_active_catalog_fixture_references_receive_their_rule_marker"
        in result.stdout
    )
    assert (
        "tests/test_design_lint_i2c_missing_pullups.py::test_connecting_one_line_leaves_only_the_other_pullup_missing"
        in result.stdout
    )
    assert "tests/test_design_lint_backlog.py::" not in result.stdout
    assert "tests/test_power_paths.py::" not in result.stdout


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
        "test_native_unconnected_named_connector_supply_pin_cases_repeat",
        "test_native_unconnected_named_connector_return_pin_cases_repeat",
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


def test_shared_reference_roots_are_not_resolved_during_collection() -> None:
    tests_root = Path(__file__).parent
    eager: list[str] = []
    for source_path in sorted(tests_root.glob("test_*.py")):
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=source_path.name)

        class EagerCallVisitor(ast.NodeVisitor):
            def __init__(self, source_name: str) -> None:
                self.source_name = source_name

            def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
                for expression in (
                    *node.decorator_list,
                    *node.args.defaults,
                    *node.args.kw_defaults,
                ):
                    if expression is not None:
                        self.visit(expression)

            visit_AsyncFunctionDef = visit_FunctionDef

            def visit_Lambda(self, node: ast.Lambda) -> None:
                for expression in (*node.args.defaults, *node.args.kw_defaults):
                    if expression is not None:
                        self.visit(expression)

            def visit_ClassDef(self, node: ast.ClassDef) -> None:
                for expression in (*node.decorator_list, *node.bases):
                    self.visit(expression)
                for keyword in node.keywords:
                    self.visit(keyword.value)
                for statement in node.body:
                    self.visit(statement)

            def visit_Call(self, node: ast.Call) -> None:
                if isinstance(node.func, ast.Name) and node.func.id == "reference_root":
                    eager.append(f"{self.source_name}:{node.lineno}")
                self.generic_visit(node)

        EagerCallVisitor(source_path.name).visit(tree)

    assert not eager, f"Resolve external template roots after pytest selects tests: {eager}"


def test_marker_selection_collects_without_the_external_template_checkout() -> None:
    environment = os.environ.copy()
    environment.pop("KICAD_TEMPLATE_ROOT", None)
    result = subprocess.run(
        (
            sys.executable,
            "-I",
            "-m",
            "pytest",
            "-qq",
            "-m",
            "design_lint and power_lint",
            "--collect-only",
        ),
        cwd=Path(__file__).resolve().parents[1],
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "tests/test_power_pin_net_roles.py:" in result.stdout
