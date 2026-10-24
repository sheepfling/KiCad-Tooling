"""Keep representative lint selectors focused on their catalogued cases."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.design_lint, pytest.mark.architecture]


def _collect_rule_nodes(rule_id: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment.pop("KICAD_TEMPLATE_ROOT", None)
    return subprocess.run(
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
            "bus.i2c_signal_label_role_mismatch",
            "tests/test_i2c_signal_label_roles.py::test_crossed_i2c_line_labels_are_reviewed_while_both_pins_stay_assigned",
        ),
        (
            "bus.serial_tx_rx_same_net",
            "tests/test_serial_tx_rx_same_net.py::test_same_net_uart_tx_rx_pair_is_reviewed_and_full_duplex_control_is_quiet",
        ),
        (
            "bus.serial_signal_on_named_rail",
            "tests/test_serial_signal_named_rail.py::test_project_policy_and_exact_ignore_control_the_review",
        ),
        (
            "bus.spi_signal_on_named_rail",
            "tests/test_spi_signal_named_rail.py::test_neutral_labels_and_unsupported_spi_functions_are_quiet",
        ),
        (
            "bus.can_signal_on_named_rail",
            "tests/test_can_signal_named_rail.py::test_neutral_labels_and_unsupported_functions_are_quiet",
        ),
        (
            "bus.can_line_on_named_rail",
            "tests/test_can_line_named_rail.py::test_neutral_rail_labels_and_non_line_functions_are_quiet",
        ),
        (
            "bus.ethernet_signal_on_named_rail",
            "tests/test_ethernet_signal_named_rail.py::test_neutral_labels_and_unsupported_functions_are_quiet",
        ),
        (
            "bus.ethernet_management_signal_on_named_rail",
            "tests/test_ethernet_management_signal_named_rail.py::test_neutral_rail_names_and_unrecognized_functions_are_quiet",
        ),
        (
            "bus.usb_signal_on_named_rail",
            "tests/test_usb_signal_named_rail.py::test_neutral_net_labels_do_not_request_review",
        ),
        (
            "bus.usb_c_cc_signal_on_named_rail",
            "tests/test_usb_c_cc_named_rail.py::test_neutral_labels_and_non_cc_functions_are_quiet",
        ),
        (
            "bus.usb_c_sbu_signal_on_named_rail",
            "tests/test_usb_c_sbu_named_rail.py::test_neutral_labels_and_unrecognized_functions_are_quiet",
        ),
        (
            "bus.i3c_signal_on_named_rail",
            "tests/test_i3c_signal_named_rail.py::test_neutral_labels_mismatched_channels_and_unsupported_functions_are_controls",
        ),
        (
            "bus.i3c_sda_scl_same_net",
            "tests/test_i3c_signal_same_net.py::test_dnp_open_duplicate_mismatched_channel_and_incomplete_inventory_are_skipped",
        ),
        (
            "bus.serial_tx_rx_label_mismatch",
            "tests/test_serial_tx_rx_label_mismatch.py::test_opposite_uart_labels_are_reviewed_while_pins_remain_separate",
        ),
        (
            "bus.rs485_data_direction_label_mismatch",
            "tests/test_rs485_data_direction_label_mismatch.py::test_crossed_driver_and_receiver_labels_are_reviewed",
        ),
        (
            "bus.rs485_data_input_output_same_net",
            "tests/test_rs485_data_input_output_same_net.py::test_explicit_rs485_driver_input_and_receiver_output_on_one_net_are_reviewed",
        ),
        (
            "bus.rs485_ab_same_net",
            "tests/test_rs485_ab_same_net.py::test_explicit_rs485_a_b_pins_on_one_net_request_review",
        ),
        (
            "bus.rs485_signal_on_named_rail",
            "tests/test_rs485_signal_named_rail.py::test_explicit_rs485_data_pins_on_named_rails_request_review[U1.1-GND-D-tx]",
        ),
        (
            "bus.rs485_line_on_named_rail",
            "tests/test_rs485_line_named_rail.py::test_explicit_rs485_line_pins_on_named_rails_request_review[U1.1-GND-A-a-U1.2]",
        ),
        (
            "bus.rs485_unconnected_data_pin",
            "tests/test_rs485_unconnected_data_pins.py::test_open_rs485_data_pin_emits_pair_identity_and_net_evidence",
        ),
        (
            "bus.serial_tx_outputs_share_net",
            "tests/test_serial_tx_output_sharing.py::test_multiple_fitted_transmit_functions_on_one_net_are_reviewed",
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
            "bus.spi_chip_select_inputs_share_net",
            "tests/test_spi_shared_chip_select.py::test_multiple_fitted_device_select_inputs_on_one_net_are_reviewed",
        ),
        (
            "bus.spi_data_outputs_share_net",
            "tests/test_spi_shared_data_outputs.py::test_multiple_fitted_spi_data_outputs_on_one_net_are_reviewed",
        ),
        (
            "bus.spi_clock_control_data_same_net",
            (
                "tests/test_spi_clock_control_same_net.py::"
                "test_bounded_spi_clock_control_and_data_aliases_keep_channel_identity"
            ),
        ),
        (
            "bus.usb_dp_dm_same_net",
            (
                "tests/test_usb_data_same_net.py::"
                "test_usb_data_pins_on_same_net_are_reviewed_and_separate_lines_are_control"
            ),
        ),
        (
            "bus.spi_clock_chip_select_same_net",
            (
                "tests/test_spi_clock_chip_select_same_net.py::"
                "test_same_channel_spi_clock_and_chip_select_sharing_one_net_is_reviewed"
            ),
        ),
        (
            "bus.spi_clock_select_label_mismatch",
            (
                "tests/test_spi_clock_select_label_mismatch.py::"
                "test_crossed_spi_clock_select_labels_are_reviewed"
            ),
        ),
        (
            "bus.can_tx_rx_same_net",
            (
                "tests/test_can_tx_rx_same_net.py::"
                "test_explicit_same_channel_can_tx_rx_pins_on_one_net_are_reviewed"
            ),
        ),
        (
            "bus.can_tx_outputs_share_net",
            (
                "tests/test_can_tx_output_sharing.py::"
                "test_multiple_fitted_can_tx_functions_on_one_net_are_reviewed"
            ),
        ),
        (
            "bus.can_tx_rx_label_mismatch",
            (
                "tests/test_can_tx_rx_label_mismatch.py::"
                "test_explicit_can_tx_rx_functions_on_opposite_role_labels_are_reviewed"
            ),
        ),
        (
            "bus.serial_peer_voltage_review",
            "tests/test_design_lint_serial_peer_voltage.py::test_serial_peer_voltage_prompt_requires_matching_role_and_unambiguous_native_evidence",
        ),
        (
            "schematic.coincident_text_anchors",
            "tests/test_design_lint_schematic_text.py::test_coincident_text_anchor_rule_is_configurable_and_review_only_by_default",
        ),
        (
            "component.mosfet_gate_direct_drive",
            "tests/test_mosfet_gate_direct_drive.py::test_output_capable_pin_directly_sharing_gate_net_is_reviewed",
        ),
        (
            "pcb.mechanical_edge_clearance_rule_coverage",
            "tests/test_design_lint_determinism_pcb_mechanical_edge.py::test_mechanical_edge_fault_and_control_reports_are_source_bound_and_deterministic",
        ),
        (
            "connector.return_supply_scope_singleton",
            "tests/test_design_lint_determinism_connector_scope_singletons.py::test_return_scope_singleton_fault_and_control_reports_are_deterministic",
        ),
        (
            "connector.mapped_interface_other_unassigned",
            "tests/test_design_lint_determinism_mapped_interface_other_unassigned.py::test_other_contact_fault_and_control_reports_are_deterministic",
        ),
    ),
)
def test_rule_marker_selects_catalogued_cases_without_external_checkout(
    rule_id: str,
    expected_node: str,
) -> None:
    result = _collect_rule_nodes(rule_id)
    assert result.returncode == 0, result.stdout + result.stderr
    assert expected_node in result.stdout
    assert "tests/test_power_paths.py::" not in result.stdout


@pytest.mark.parametrize(
    ("rule_id", "selected_node"),
    (
        (
            "component.peer_power_output_unconnected",
            "tests/test_design_lint_mcp_parity_peer_pins.py::test_peer_power_output_unconnected_lint_cli_mcp_parity",
        ),
        (
            "component.peer_signal_output_unconnected",
            "tests/test_design_lint_mcp_parity_peer_pins.py::test_peer_signal_output_unconnected_lint_cli_mcp_parity",
        ),
        (
            "component.peer_signal_input_unconnected",
            "tests/test_design_lint_mcp_parity_peer_pins.py::test_peer_signal_input_unconnected_lint_cli_mcp_parity",
        ),
        (
            "component.peer_bidirectional_pin_unconnected",
            "tests/test_design_lint_mcp_parity_peer_pins.py::test_peer_bidirectional_pin_unconnected_lint_cli_mcp_parity",
        ),
    ),
)
def test_peer_pin_rule_selector_collects_only_its_parity_case(
    rule_id: str,
    selected_node: str,
) -> None:
    result = _collect_rule_nodes(rule_id)
    assert result.returncode == 0, result.stdout + result.stderr
    selected_peer_cases = {
        line
        for line in result.stdout.splitlines()
        if line.startswith("tests/test_design_lint_mcp_parity_peer_pins.py::test_peer_")
    }
    assert selected_peer_cases == {selected_node}


def test_rule_selector_filters_parametrized_peer_identity_cases() -> None:
    result = _collect_rule_nodes("component.peer_signal_input_unconnected")
    assert result.returncode == 0, result.stdout + result.stderr
    selected_identity_cases = {
        line
        for line in result.stdout.splitlines()
        if line.startswith("tests/test_peer_component_pin_identity.py::")
    }
    assert selected_identity_cases == {
        "tests/test_peer_component_pin_identity.py::test_shared_part_id_aliases_cover_each_typed_peer_rule[input-IN-component.peer_signal_input_unconnected]",
        "tests/test_peer_component_pin_identity.py::test_shared_part_id_peer_pin_assignment_matches_between_cli_and_mcp[signal-input]",
        "tests/test_peer_component_pin_identity.py::test_shared_part_id_aliases_accept_identical_generic_pin_metadata[input-component.peer_signal_input_unconnected]",
        "tests/test_peer_component_pin_identity.py::test_shared_part_id_aliases_skip_mismatched_pin_functions[input-IN-component.peer_signal_input_unconnected]",
    }


def test_serial_reference_rule_selects_its_exact_native_regressions() -> None:
    rule_id = "bus.serial_peer_reference_review"
    result = _collect_rule_nodes(rule_id)
    assert result.returncode == 0, result.stdout + result.stderr
    for function in (
        "test_serial_peer_voltage_fault_and_controls_by_native_version",
        "test_serial_connector_and_optical_isolation_boundaries_by_native_version",
        "test_serial_label_alias_fault_and_control_by_native_version",
        "test_serial_peer_normalized_netlists_match_across_native_versions",
    ):
        assert f"tests/test_ci_hosted_digital_peer_serial.py::{function}" in result.stdout
    assert "tests/test_power_paths.py::" not in result.stdout
