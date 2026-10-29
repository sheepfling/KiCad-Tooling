"""Keep lint-themed regression suites small and easy to select."""

from __future__ import annotations

import pytest

from tests.lint_architecture_support import (
    TESTS,
    THEME_SUITE_MAX_LINES,
)
from tests.lint_architecture_support import (
    line_count as _line_count,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.architecture]

SCHEMATIC_GEOMETRY_THEME_SUITES = (
    "test_schematic_geometry_text.py",
    "test_schematic_geometry_symbol_body.py",
    "test_schematic_geometry_pin_proximity.py",
    "test_schematic_geometry_wire_topology.py",
    "test_schematic_geometry_hierarchy.py",
    "test_schematic_geometry_native_text.py",
    "test_schematic_geometry_native_wire_body.py",
    "test_schematic_geometry_native_symbol_body.py",
    "test_schematic_geometry_native_pin_connectivity.py",
    "test_schematic_geometry_native_wire_topology.py",
)
PCB_REFERENCE_PLANE_THEME_SUITES = (
    "test_pcb_reference_plane_geometry.py",
    "test_pcb_reference_plane_layers.py",
    "test_pcb_reference_plane_contract.py",
    "test_ci_hosted_pcb_reference_planes.py",
)
CONNECTOR_COVERAGE_THEME_SUITES = (
    "test_connector_inventory_coverage.py",
    "test_connector_supply_peer_coverage.py",
    "test_connector_return_role_coverage.py",
    "test_connector_footprint_named_power_input_all_open.py",
    "test_ci_hosted_connector_returns.py",
    "test_ci_hosted_connector_inventory_native.py",
)
HOSTED_ORCHESTRATION_THEME_SUITES = ("test_ci_hosted_native_orchestration.py",)
OPEN_DRAIN_THEME_SUITES = ("test_open_drain_bias_fixture_lane.py",)
I2C_ADDRESS_THEME_SUITES = (
    "test_i2c_address_coverage.py",
    "test_i2c_address_collisions.py",
    "test_i2c_address_straps.py",
    "test_i2c_address_contract.py",
)
USB_HOSTED_THEME_SUITES = (
    "test_hosted_usb_requirements.py",
    "test_usb_data_path_native_fixture_lane.py",
    "test_usb_superspeed_peer_reference_native_fixture_lane.py",
)
USB_INLINE_COMPONENT_THEME_SUITES = (
    "test_usb_inline_component_paths.py",
    "test_usb_data_path_protection_shunts.py",
    "test_design_lint_mcp_parity_usb_protection_shunts.py",
)
POWER_PATH_HOSTED_THEME_SUITES = (
    "test_hosted_power_path_requirements.py",
    "test_power_path_fixture_lane.py",
    "test_power_path_native_fixture_lane.py",
)
IC_RAIL_NATIVE_THEME_SUITES = ("test_ic_rail_capacitor_native_fixture_lane.py",)
POWER_INPUT_THEME_SUITES = (
    "test_power_input_source_paths.py",
    "test_power_input_source_anchors.py",
    "test_power_input_policy.py",
)
DIGITAL_PEER_FIXTURE_THEME_SUITES = (
    "test_ci_hosted_digital_peer_spi.py",
    "test_ci_hosted_digital_peer_serial.py",
    "test_ci_hosted_component_peer_power.py",
    "test_digital_peer_spi_voltage_fixture_lane.py",
    "test_digital_peer_serial_voltage_fixture_lane.py",
    "test_digital_peer_serial_reference_fixture_lane.py",
)
NATIVE_INTERFACE_THEME_SUITES = (
    "test_ci_hosted_usb_c_ports.py",
    "test_ci_hosted_stm32.py",
    "test_ci_hosted_control_inputs.py",
    "test_rs485_unconnected_line_native_fixture_lane.py",
)
COMPONENT_PEER_POWER_THEME_SUITES = (
    "test_component_peer_power_input_divergence.py",
    "test_component_named_peer_power_input_divergence.py",
    "test_component_named_peer_power_input_all_open.py",
    "test_component_named_peer_power_input_all_open_native.py",
    "test_component_peer_power_input_native_fixture_lane.py",
    "test_component_peer_power_fixture_lane.py",
    "test_peer_power_assignment_symbol_groups.py",
    "test_peer_power_assignment_part_id_groups.py",
    "test_peer_power_assignment_cli_mcp.py",
    "test_peer_power_assignment_native.py",
)
COMPONENT_RATING_HOSTED_THEME_SUITES = ("test_component_rating_native_fixture_lane.py",)
COMPONENT_LED_THEME_SUITES = ("test_led_rail_native_fixture_lane.py",)
COMPONENT_POWER_OUTPUT_THEME_SUITES = ("test_component_unconnected_power_output.py",)
TWO_PIN_NATIVE_THEME_SUITES = ("test_two_pin_component_native_fixture_lane.py",)
COMPLEMENTARY_PAIR_THEME_SUITES = (
    "test_complementary_pair_native_fixture_lane.py",
    "test_usb_c_superspeed_lane_pairs.py",
    "test_usb_c_superspeed_lane_labels.py",
)
DC_REFERENCE_NATIVE_THEME_SUITES = ("test_net_dc_reference_native_fixture_lane.py",)
PCB_THEME_SUITES = (
    "test_ci_hosted_pcb_fixture_schedule.py",
    "test_pcb_reference_plane_native_fixture_lane.py",
    "test_pcb_switching_loop_native_fixture_lane.py",
    "test_pcb_return_path_native_fixture_lane.py",
    "test_pcb_decoupling_native_fixture_lane.py",
    "test_pcb_protection_path_native_fixture_lane.py",
    "test_pcb_track_width_native_fixture_lane.py",
    "test_pcb_switching_loop_geometry.py",
    "test_pcb_switching_loop_routes.py",
    "test_pcb_access_fixture_lane.py",
    "test_pcb_access_native_fixture_lane.py",
    "test_pcb_drc_coverage.py",
    "test_pcb_signal_path_coverage.py",
    "test_pcb_signal_path_evidence.py",
    "test_pcb_signal_path_mcp_parity.py",
    "test_ci_hosted_pcb_return_paths.py",
    "test_pcb_dru_rule_review.py",
    "test_pcb_drc_global_severity_review.py",
    "test_pcb_warning_default_drc_ignored.py",
    "test_design_lint_mcp_parity_pcb_warning_default_drc_ignored.py",
    "test_pcb_signal_integrity_drc_severity.py",
    "test_design_lint_mcp_parity_pcb_signal_integrity_drc_severity.py",
)


def test_design_lint_theme_suites_stay_below_review_limit() -> None:
    modules = sorted(
        path
        for path in (
            *TESTS.glob("test_design_lint_*.py"),
            *(
                TESTS / name
                for name in (
                    *PCB_THEME_SUITES,
                    *SCHEMATIC_GEOMETRY_THEME_SUITES,
                    *PCB_REFERENCE_PLANE_THEME_SUITES,
                    *CONNECTOR_COVERAGE_THEME_SUITES,
                    *HOSTED_ORCHESTRATION_THEME_SUITES,
                    *OPEN_DRAIN_THEME_SUITES,
                    *I2C_ADDRESS_THEME_SUITES,
                    *USB_HOSTED_THEME_SUITES,
                    *USB_INLINE_COMPONENT_THEME_SUITES,
                    *POWER_PATH_HOSTED_THEME_SUITES,
                    *IC_RAIL_NATIVE_THEME_SUITES,
                    *POWER_INPUT_THEME_SUITES,
                    *DIGITAL_PEER_FIXTURE_THEME_SUITES,
                    *NATIVE_INTERFACE_THEME_SUITES,
                    *COMPONENT_PEER_POWER_THEME_SUITES,
                    *COMPONENT_RATING_HOSTED_THEME_SUITES,
                    *COMPONENT_LED_THEME_SUITES,
                    *COMPONENT_POWER_OUTPUT_THEME_SUITES,
                    *TWO_PIN_NATIVE_THEME_SUITES,
                    *COMPLEMENTARY_PAIR_THEME_SUITES,
                    *DC_REFERENCE_NATIVE_THEME_SUITES,
                )
            ),
        )
    )
    assert modules, "Design-lint theme suites should be discoverable."

    module_sizes = {path.name: _line_count(path) for path in modules}
    oversized = {
        name: lines for name, lines in module_sizes.items() if lines >= THEME_SUITE_MAX_LINES
    }

    assert not oversized, (
        "Split design-lint theme suites at the 500-line review threshold; "
        f"oversized suites: {oversized}"
    )
