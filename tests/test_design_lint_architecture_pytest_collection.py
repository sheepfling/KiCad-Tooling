"""Guard pytest collection and selector behavior for lint suites."""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.design_lint, pytest.mark.architecture]


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


@pytest.mark.parametrize(
    ("rule_id", "expected_node"),
    (
        (
            "power.pin_function_net_role_conflict",
            "tests/test_power_pin_net_roles.py::test_positive_supply_pin_on_return_net",
        ),
        (
            "power.named_supply_pin_on_negative_rail",
            "tests/test_power_negative_rail.py::test_named_supply_pin_on_negative_rail_is_reviewed",
        ),
        (
            "power.mapped_sequence_dependency_mismatch",
            "tests/test_power_sequence_native_fixture_lane.py::test_control_fault_and_cycle_repeat_on_pinned_kicad_versions",
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
            "connector.generic_peer_pin_all_open",
            "tests/test_connector_peer_pin_all_open.py::test_all_open_generic_passive_peer_pin_is_opt_in_review",
        ),
        (
            "connector.generic_peer_pin_all_open",
            "tests/test_connector_signal_peer_pin_all_open.py::test_all_open_generic_signal_peer_pin_is_opt_in_review",
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
            "component.peer_power_input_named_assignment_divergence",
            "tests/test_component_named_peer_power_input_divergence.py::test_named_peer_power_input_split_is_reviewed_with_controls",
        ),
        (
            "component.peer_power_input_named_all_open",
            "tests/test_component_named_peer_power_input_all_open.py::test_named_peer_power_input_open_on_every_peer_is_reviewed",
        ),
        (
            "connector.peer_power_input_open_assignment",
            "tests/test_design_lint_connector_named_power_input_peers.py::test_open_named_power_input_on_one_connector_symbol_alias_is_reviewed",
        ),
        (
            "connector.peer_power_input_named_all_open",
            "tests/test_design_lint_connector_named_power_input_peers.py::test_named_power_input_open_on_every_connector_alias_is_reviewed",
        ),
        (
            "connector.peer_power_input_named_assignment_divergence",
            "tests/test_design_lint_connector_named_power_input_divergence.py::test_named_power_input_aliases_on_distinct_nets_are_reviewed",
        ),
        (
            "connector.peer_power_output_open_assignment",
            "tests/test_design_lint_connector_named_power_output_peers.py::test_open_named_power_output_on_one_connector_symbol_alias_is_reviewed",
        ),
        (
            "connector.peer_power_output_named_all_open",
            "tests/test_design_lint_connector_named_power_output_peers.py::test_named_power_output_open_on_every_connector_alias_is_reviewed",
        ),
        (
            "connector.peer_power_output_named_assignment_divergence",
            "tests/test_design_lint_connector_named_power_output_divergence.py::test_named_power_output_aliases_on_distinct_nets_are_reviewed",
        ),
        (
            "bus.spi_peer_voltage_review",
            "tests/test_design_lint_peer_voltage.py::test_spi_peer_voltage_prompt_requires_unambiguous_native_evidence",
        ),
        (
            "bus.serial_peer_voltage_review",
            "tests/test_design_lint_serial_peer_voltage.py::test_serial_peer_voltage_prompt_requires_matching_role_and_unambiguous_native_evidence",
        ),
        (
            "schematic.coincident_text_anchors",
            "tests/test_design_lint_schematic_text.py::test_coincident_text_anchor_rule_is_configurable_and_review_only_by_default",
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


def test_serial_reference_rule_selects_its_exact_native_regressions() -> None:
    environment = os.environ.copy()
    environment.pop("KICAD_TEMPLATE_ROOT", None)
    rule_id = "bus.serial_peer_reference_review"
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
    for function in (
        "test_serial_peer_voltage_fault_and_controls_by_native_version",
        "test_serial_connector_and_optical_isolation_boundaries_by_native_version",
        "test_serial_label_alias_fault_and_control_by_native_version",
        "test_serial_peer_normalized_netlists_match_across_native_versions",
    ):
        assert f"tests/test_ci_hosted_digital_peer_serial.py::{function}" in result.stdout
    assert "tests/test_power_paths.py::" not in result.stdout
