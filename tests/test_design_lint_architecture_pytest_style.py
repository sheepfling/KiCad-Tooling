"""Keep connector native acceptance selectable and pytest-native."""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.design_lint_catalog import rule_catalog
from tests.design_lint_test_markers import design_lint_rule_ids_for_test

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
_PYTEST_NATIVE_LINT_SUITES = {
    "test_design_lint_dc_reference.py": {"power_lint"},
    "test_design_lint_policy.py": {"connector_lint", "return_path_lint"},
    "test_electrical_can_termination.py": {"interface_lint"},
    "test_electrical_power_connectivity.py": {"power_lint"},
    "test_electrical_component_evidence.py": {"component_lint", "evidence_lint"},
    "test_electrical_connector_evidence.py": {"connector_lint", "evidence_lint"},
    "test_electrical_pcb_return_evidence.py": {"return_path_lint", "evidence_lint"},
    "test_electrical_test_access_evidence.py": {"pcb_lint", "evidence_lint"},
    "test_design_lint_i2c_missing_pullups.py": {"interface_lint"},
    "test_design_lint_i2c_equivalent_resistance.py": {"interface_lint"},
    "test_design_lint_i2c_pullup_rail_families.py": {"interface_lint"},
    "test_electrical_rs485_contract.py": {"interface_lint"},
    "test_design_lint_led_topology.py": {"component_lint", "power_lint"},
    "test_design_lint_serial_peer_voltage.py": {"interface_lint"},
    "test_pcb_reference_plane_native_fixture_lane.py": {"pcb_lint", "return_path_lint"},
    "test_pcb_switching_loop_native_fixture_lane.py": {"pcb_lint", "return_path_lint"},
    "test_pcb_return_path_native_fixture_lane.py": {"pcb_lint", "return_path_lint"},
    "test_pcb_access_fixture_lane.py": {"pcb_lint"},
    "test_ci_hosted_pcb_fixture_schedule.py": {"pcb_lint", "return_path_lint"},
}


def test_active_catalog_fixture_references_receive_their_rule_marker() -> None:
    for rule in rule_catalog().rules:
        if rule.status != "active":
            continue
        references = (
            *rule.fault_fixtures,
            *rule.valid_control_fixtures,
            *rule.metamorphic_fixtures,
        )
        for reference in references:
            parts = reference.split(".")
            assert len(parts) >= 3 and parts[0] == "tests", reference
            module = ".".join(parts[:2])
            test_class = ".".join(parts[2:-1]) or None
            function = parts[-1]
            assert rule.rule_id in design_lint_rule_ids_for_test(
                module,
                test_class,
                function,
            ), reference


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


def test_external_electrical_template_consumers_are_template_marked() -> None:
    required_support_imports = {
        "tests.electrical_simulation_support": {"install_fixture"},
        "tests.electrical_evidence_support": {
            "create_electrical_evidence_workspace",
            "electrical_evidence_workspace",
        },
        "tests.electrical_parity_support": {"parity_harness"},
    }
    tests_root = Path(__file__).parent
    for source_path in sorted(tests_root.glob("test_*.py")):
        source = source_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=source_path.name)
        uses_external_electrical_setup = any(
            isinstance(node, ast.ImportFrom)
            and node.module in required_support_imports
            and any(alias.name in required_support_imports[node.module] for alias in node.names)
            for node in ast.walk(tree)
        )
        if uses_external_electrical_setup:
            assert "pytest.mark.template_checkout" in source, source_path.name


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


@pytest.mark.parametrize(
    ("rule_id", "expected_node"),
    (
        (
            "power.pin_function_net_role_conflict",
            "tests/test_power_pin_net_roles.py::test_positive_supply_pin_on_return_net",
        ),
        (
            "net.connector_capacitor_only_no_dc_anchor",
            "tests/test_design_lint_dc_reference.py::test_connector_capacitor_only_net_requests_dc_reference_review",
        ),
        (
            "connector.unconnected_supply_pin",
            "tests/test_design_lint_power_pin_patterns.py::TestDesignLintPowerPinPatterns::test_unconnected_supply_and_return_pins_without_a_peer_are_reported",
        ),
        (
            "bus.i2c_missing_pullup",
            "tests/test_design_lint_i2c_missing_pullups.py::test_connecting_one_line_leaves_only_the_other_pullup_missing",
        ),
        (
            "bus.i2c_low_equivalent_resistance",
            "tests/test_design_lint_i2c_equivalent_resistance.py::test_i2c_parallel_pullups_are_reviewed_by_nominal_equivalent_resistance",
        ),
        (
            "bus.i2c_multiple_pullup_rail_families",
            "tests/test_design_lint_i2c_pullup_rail_families.py::test_same_family_rails_remain_valid_controls[sda_rails0-scl_rails0]",
        ),
        (
            "component.led_directly_across_supply_and_return",
            "tests/test_design_lint_led_topology.py::test_led_non_matching_topologies_remain_valid_controls[series-resistor]",
        ),
        (
            "bus.serial_peer_voltage_review",
            "tests/test_design_lint_serial_peer_voltage.py::test_serial_peer_voltage_prompt_requires_matching_role_and_unambiguous_native_evidence",
        ),
    ),
)
def test_rule_marker_selects_catalogued_cases_without_external_checkout(
    rule_id: str,
    expected_node: str,
) -> None:
    environment = os.environ.copy()
    environment.pop("KICAD_TEMPLATE_ROOT", None)
    result = subprocess.run(
        (
            sys.executable,
            "-I",
            "-m",
            "pytest",
            "-q",
            "--collect-only",
            "-m",
            f'design_lint_rule(rule_id="{rule_id}")',
        ),
        cwd=Path(__file__).resolve().parents[1],
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert expected_node in result.stdout
    assert "tests/test_power_paths.py::" not in result.stdout


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


def test_focus_lint_suites_are_pytest_native_and_theme_scoped() -> None:
    for filename, area_markers in _PYTEST_NATIVE_LINT_SUITES.items():
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
        for marker in area_markers:
            assert f"pytest.mark.{marker}" in source
