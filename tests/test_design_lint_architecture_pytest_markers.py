"""Guard lint marker declarations and focused suite boundaries."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.design_lint_catalog import rule_catalog
from tests.design_lint_test_markers import design_lint_rule_ids_for_test

pytestmark = [pytest.mark.design_lint, pytest.mark.architecture]


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
    "test_design_lint_complementary_pairs.py": {"interface_lint"},
    "test_design_lint_decoupling.py": {"component_lint", "power_lint"},
    "test_design_lint_dc_reference.py": {"power_lint"},
    "test_design_lint_determinism_power_connectivity.py": {"power_lint"},
    "test_usb_peer_reference_superspeed.py": {"interface_lint"},
    "test_usb_superspeed_peer_reference_native_fixture_lane.py": {"interface_lint"},
    "test_design_lint_policy.py": {"connector_lint", "return_path_lint"},
    "test_electrical_can_termination.py": {"interface_lint"},
    "test_electrical_power_connectivity.py": {"power_lint"},
    "test_regulator_feedback.py": {"power_lint"},
    "test_power_sequences.py": {"power_lint"},
    "test_power_paths.py": {"power_lint"},
    "test_power_sequence_fixture_lane.py": {"power_lint"},
    "test_power_sequence_native_fixture_lane.py": {"power_lint"},
    "test_electrical_component_evidence.py": {"component_lint", "evidence_lint"},
    "test_electrical_connector_evidence.py": {"connector_lint", "evidence_lint"},
    "test_electrical_connector_return_parity.py": {
        "connector_lint",
        "return_path_lint",
        "parity_lint",
    },
    "test_pin_connectivity_acceptance.py": {"connector_lint"},
    "test_electrical_pcb_return_evidence.py": {"return_path_lint", "evidence_lint"},
    "test_electrical_test_access_evidence.py": {"pcb_lint", "evidence_lint"},
    "test_design_lint_i2c_missing_pullups.py": {"interface_lint"},
    "test_design_lint_i2c_equivalent_resistance.py": {"interface_lint"},
    "test_design_lint_i2c_pullup_rail_families.py": {"interface_lint"},
    "test_electrical_rs485_contract.py": {"interface_lint"},
    "test_design_lint_led_topology.py": {"component_lint", "power_lint"},
    "test_design_lint_peer_voltage.py": {"interface_lint"},
    "test_design_lint_serial_peer_voltage.py": {"interface_lint"},
    "test_design_lint_schematic_connectivity.py": {"schematic_lint"},
    "test_design_lint_schematic_text.py": {"schematic_lint"},
    "test_connector_peer_pin_all_open.py": {"connector_lint"},
    "test_design_lint_connector_power_pins.py": {"connector_lint", "power_lint"},
    "test_design_lint_connector_named_power_input_peers.py": {
        "connector_lint",
        "power_lint",
    },
    "test_design_lint_connector_named_power_input_divergence.py": {
        "connector_lint",
        "power_lint",
    },
    "test_design_lint_connector_named_power_output_peers.py": {
        "connector_lint",
        "power_lint",
    },
    "test_design_lint_connector_named_power_output_divergence.py": {
        "connector_lint",
        "power_lint",
    },
    "test_design_lint_mcp_parity_connector_named_power_peers.py": {
        "connector_lint",
        "power_lint",
        "parity_lint",
    },
    "test_connector_named_power_input_native_fixture_lane.py": {
        "connector_lint",
        "power_lint",
    },
    "test_connector_named_power_output_native_fixture_lane.py": {
        "connector_lint",
        "power_lint",
    },
    "test_native_db9_return_contracts.py": {"connector_lint", "return_path_lint"},
    "test_connector_signal_peer_pin_all_open.py": {"connector_lint", "interface_lint"},
    "test_component_peer_pin_all_open.py": {"component_lint"},
    "test_component_peer_pin_mixed_open.py": {"component_lint"},
    "test_component_peer_pin_assignment_outlier.py": {"component_lint"},
    "test_component_peer_pin_assignment_native_fixture_lane.py": {"component_lint"},
    "test_component_named_peer_power_input_all_open.py": {"component_lint", "power_lint"},
    "test_component_named_peer_power_input_all_open_native.py": {
        "component_lint",
        "power_lint",
    },
    "test_design_lint_determinism_component_peers.py": {"component_lint", "power_lint"},
    "test_design_lint_mcp_parity_peer_pin_assignment_outlier.py": {
        "component_lint",
        "parity_lint",
    },
    "test_pcb_reference_plane_native_fixture_lane.py": {"pcb_lint", "return_path_lint"},
    "test_pcb_switching_loop_native_fixture_lane.py": {"pcb_lint", "return_path_lint"},
    "test_pcb_return_path_native_fixture_lane.py": {"pcb_lint", "return_path_lint"},
    "test_pcb_access_fixture_lane.py": {"pcb_lint"},
    "test_pcb_touch_pad_clearance.py": {"pcb_lint"},
    "test_design_lint_determinism_pcb_touch_pad_clearance.py": {"pcb_lint"},
    "test_design_lint_determinism_pcb_required_fitted_reference.py": {"pcb_lint"},
    "test_design_lint_determinism_pcb_board_only.py": {"pcb_lint"},
    "test_design_lint_determinism_pcb_dnp.py": {"pcb_lint"},
    "test_design_lint_determinism_pcb_value.py": {"pcb_lint"},
    "test_pcb_touch_pad_clearance_native.py": {"pcb_lint"},
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


def test_cross_theme_architecture_suites_do_not_claim_area_markers() -> None:
    tests_root = Path(__file__).parent
    for filename in (
        "test_design_lint_architecture_pytest_markers.py",
        "test_design_lint_architecture_pytest_collection.py",
    ):
        tree = ast.parse((tests_root / filename).read_text(encoding="utf-8"))
        pytestmark = next(
            node.value
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "pytestmark"
                for target in node.targets
            )
        )
        assert isinstance(pytestmark, ast.List)
        marker_names = {ast.unparse(marker) for marker in pytestmark.elts}
        assert marker_names == {"pytest.mark.design_lint", "pytest.mark.architecture"}


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


def test_tests_using_hosted_reference_checkout_are_template_marked() -> None:
    tests_root = Path(__file__).parent
    for source_path in sorted(tests_root.glob("test_*.py")):
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=source_path.name)
        uses_hosted_reference_root = any(
            isinstance(node, ast.arg) and node.arg == "hosted_reference_root"
            for node in ast.walk(tree)
        )
        if uses_hosted_reference_root:
            assert "pytest.mark.template_checkout" in source_path.read_text(encoding="utf-8"), (
                source_path.name
            )


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

    serial_path = Path(__file__).with_name("test_ci_hosted_digital_peer_serial.py")
    serial_tree = ast.parse(serial_path.read_text(encoding="utf-8"))
    snapshot_test = next(
        node
        for node in serial_tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "test_native_connectivity_snapshot_captures_pin_roles_by_version"
    )
    assert "pytest.mark.evidence_lint" in {
        ast.unparse(decorator) for decorator in snapshot_test.decorator_list
    }

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
