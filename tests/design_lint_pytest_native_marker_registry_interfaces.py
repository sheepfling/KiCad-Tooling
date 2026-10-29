"""Expected markers for focused interfaces lint suites."""

from types import MappingProxyType

PYTEST_NATIVE_LINT_SUITES = MappingProxyType(
    {
        "test_spi_composite_pin_functions.py": frozenset({"interface_lint"}),
        "test_ci_hosted_digital_peer_spi.py": frozenset({"interface_lint", "native_kicad", "slow"}),
        "test_design_lint_complementary_pairs.py": frozenset({"interface_lint"}),
        "test_usb_c_superspeed_lane_pairs.py": frozenset({"interface_lint"}),
        "test_usb_c_superspeed_lane_labels.py": frozenset({"interface_lint"}),
        "test_design_lint_architecture_usb_c_lane_labels.py": frozenset({"interface_lint"}),
        "test_can_line_polarity_native_fixture_lane.py": frozenset(
            {"interface_lint", "native_kicad", "slow"}
        ),
        "test_ethernet_data_label_native_fixture_lane.py": frozenset(
            {"interface_lint", "native_kicad", "slow"}
        ),
        "test_ethernet_management_label_native_fixture_lane.py": frozenset(
            {"interface_lint", "native_kicad", "slow"}
        ),
        "test_ethernet_management_unconnected_native_fixture_lane.py": frozenset(
            {"interface_lint", "native_kicad", "slow"}
        ),
        "test_i2c_signal_label_native_fixture_lane.py": frozenset(
            {"interface_lint", "native_kicad", "slow"}
        ),
        "test_i2c_signal_named_rail.py": frozenset({"interface_lint"}),
        "test_i3c_signal_named_rail.py": frozenset({"interface_lint"}),
        "test_design_lint_determinism_i3c_signal_named_rail.py": frozenset(
            {"interface_lint", "slow"}
        ),
        "test_i3c_signal_named_rail_native_fixture_lane.py": frozenset(
            {"interface_lint", "native_kicad", "slow"}
        ),
        "test_usb_data_same_net_native_fixture_lane.py": frozenset(
            {"interface_lint", "native_kicad", "slow"}
        ),
        "test_rs485_ab_same_net_native_fixture_lane.py": frozenset(
            {"interface_lint", "native_kicad", "slow"}
        ),
        "test_design_lint_determinism_i2c_signal_named_rail.py": frozenset(
            {"interface_lint", "slow"}
        ),
        "test_i2c_pullup_voltage_coverage.py": frozenset({"interface_lint"}),
        "test_serial_tx_rx_same_net_native_fixture_lane.py": frozenset(
            {"interface_lint", "native_kicad", "slow"}
        ),
        "test_serial_tx_rx_label_mismatch_native_fixture_lane.py": frozenset(
            {"interface_lint", "native_kicad", "slow"}
        ),
        "test_serial_tx_rx_same_net.py": frozenset({"interface_lint"}),
        "test_serial_tx_rx_label_mismatch.py": frozenset({"interface_lint"}),
        "test_serial_signal_named_rail.py": frozenset({"interface_lint"}),
        "test_design_lint_determinism_serial_signal_named_rail.py": frozenset(
            {"interface_lint", "slow"}
        ),
        "test_spi_signal_named_rail.py": frozenset({"interface_lint"}),
        "test_design_lint_determinism_spi_signal_named_rail.py": frozenset(
            {"interface_lint", "slow"}
        ),
        "test_can_signal_named_rail.py": frozenset({"interface_lint"}),
        "test_can_line_named_rail.py": frozenset({"interface_lint"}),
        "test_design_lint_determinism_can_line_named_rail.py": frozenset(
            {"interface_lint", "slow"}
        ),
        "test_can_line_named_rail_native_fixture_lane.py": frozenset(
            {"interface_lint", "native_kicad", "slow"}
        ),
        "test_usb_c_cc_named_rail.py": frozenset({"interface_lint"}),
        "test_design_lint_determinism_usb_c_cc_named_rail.py": frozenset(
            {"interface_lint", "slow"}
        ),
        "test_design_lint_determinism_usb_c_sbu_named_rail.py": frozenset(
            {"interface_lint", "slow"}
        ),
        "test_usb_c_cc_named_rail_native_fixture_lane.py": frozenset(
            {"interface_lint", "native_kicad", "slow"}
        ),
        "test_usb_c_cc_same_net.py": frozenset({"interface_lint"}),
        "test_design_lint_determinism_usb_c_cc_same_net.py": frozenset({"interface_lint", "slow"}),
        "test_usb_c_cc_same_net_native_fixture_lane.py": frozenset(
            {"interface_lint", "native_kicad", "slow"}
        ),
        "test_usb_c_cc_endpoint_pairing.py": frozenset({"interface_lint"}),
        "test_design_lint_determinism_usb_c_cc_endpoint_pairing.py": frozenset(
            {"interface_lint", "slow"}
        ),
        "test_usb_c_cc_endpoint_crossed_native_fixture_lane.py": frozenset(
            {"interface_lint", "native_kicad", "slow"}
        ),
        "test_serial_endpoint_role_collision.py": frozenset({"interface_lint"}),
        "test_serial_endpoint_role_collision_native_fixture_lane.py": frozenset(
            {"interface_lint", "native_kicad", "slow"}
        ),
        "test_design_lint_determinism_serial_endpoint_role_collision.py": frozenset(
            {"interface_lint", "slow"}
        ),
        "test_design_lint_architecture_usb_c_cc_endpoint_pairing.py": frozenset({"interface_lint"}),
        "test_usb_c_sbu_named_rail.py": frozenset({"interface_lint"}),
        "test_usb_c_sbu_unconnected_pin.py": frozenset({"interface_lint"}),
        "test_design_lint_determinism_usb_c_sbu_unconnected_pin.py": frozenset(
            {"interface_lint", "slow"}
        ),
        "test_usb_c_sbu_unconnected_native_fixture_lane.py": frozenset(
            {"interface_lint", "native_kicad", "slow"}
        ),
        "test_usb_c_sbu_named_rail_native_fixture_lane.py": frozenset(
            {"interface_lint", "native_kicad", "slow"}
        ),
        "test_ethernet_signal_named_rail.py": frozenset({"interface_lint"}),
        "test_design_lint_determinism_ethernet_signal_named_rail.py": frozenset(
            {"interface_lint", "slow"}
        ),
        "test_design_lint_determinism_can_signal_named_rail.py": frozenset(
            {"interface_lint", "slow"}
        ),
        "test_can_signal_named_rail_native_fixture_lane.py": frozenset(
            {"interface_lint", "native_kicad", "slow"}
        ),
        "test_ethernet_signal_named_rail_native_fixture_lane.py": frozenset(
            {"interface_lint", "native_kicad", "slow"}
        ),
        "test_spi_signal_named_rail_native_fixture_lane.py": frozenset(
            {"interface_lint", "native_kicad", "slow"}
        ),
        "test_rs485_data_direction_label_mismatch_native_fixture_lane.py": frozenset(
            {"interface_lint", "native_kicad", "slow"}
        ),
        "test_rs485_data_direction_label_mismatch.py": frozenset({"interface_lint"}),
        "test_rs485_data_input_output_same_net.py": frozenset({"interface_lint"}),
        "test_rs485_data_input_output_same_net_native_fixture_lane.py": frozenset(
            {"interface_lint", "native_kicad", "slow"}
        ),
        "test_rs485_line_label_mismatch.py": frozenset({"interface_lint"}),
        "test_rs485_line_label_mismatch_native_fixture_lane.py": frozenset(
            {"interface_lint", "native_kicad", "slow"}
        ),
        "test_design_lint_mcp_parity_rs485_line_label_mismatch.py": frozenset(
            {"interface_lint", "parity_lint", "slow", "template_checkout"}
        ),
        "test_rs485_unconnected_data_pins.py": frozenset({"interface_lint"}),
        "test_rs485_unconnected_data_pins_native_fixture_lane.py": frozenset(
            {"interface_lint", "native_kicad", "slow"}
        ),
        "test_serial_tx_output_sharing.py": frozenset({"interface_lint"}),
        "test_serial_tx_output_sharing_native_fixture_lane.py": frozenset(
            {"interface_lint", "native_kicad", "slow"}
        ),
        "test_spi_data_polarity_native_fixture_lane.py": frozenset(
            {"interface_lint", "native_kicad", "slow"}
        ),
        "test_spi_unconnected_data_pins_native_fixture_lane.py": frozenset(
            {"interface_lint", "native_kicad", "slow"}
        ),
        "test_spi_clock_select_label_mismatch.py": frozenset({"interface_lint"}),
        "test_spi_clock_select_label_mismatch_native_fixture_lane.py": frozenset(
            {"interface_lint", "native_kicad", "slow"}
        ),
        "test_spi_shared_chip_select.py": frozenset({"interface_lint"}),
        "test_spi_shared_data_outputs.py": frozenset({"interface_lint"}),
        "test_spi_shared_chip_select_native_fixture_lane.py": frozenset(
            {"interface_lint", "native_kicad", "slow"}
        ),
        "test_spi_shared_data_outputs_native_fixture_lane.py": frozenset(
            {"interface_lint", "native_kicad", "slow"}
        ),
        "test_usb_data_polarity_native_fixture_lane.py": frozenset(
            {"interface_lint", "native_kicad", "slow"}
        ),
        "test_usb_peer_reference_superspeed.py": frozenset({"interface_lint"}),
        "test_usb_superspeed_peer_reference_native_fixture_lane.py": frozenset({"interface_lint"}),
        "test_electrical_can_termination.py": frozenset({"interface_lint"}),
        "test_design_lint_i2c_missing_pullups.py": frozenset({"interface_lint"}),
        "test_design_lint_i2c_equivalent_resistance.py": frozenset({"interface_lint"}),
        "test_design_lint_i2c_pullup_rail_families.py": frozenset({"interface_lint"}),
        "test_ci_hosted_control_inputs.py": frozenset({"interface_lint"}),
        "test_electrical_rs485_contract.py": frozenset({"interface_lint"}),
        "test_design_lint_peer_voltage.py": frozenset({"interface_lint"}),
        "test_design_lint_serial_peer_voltage.py": frozenset({"interface_lint"}),
        "test_connector_footprint_peer_metadata.py": frozenset(
            {"connector_lint", "interface_lint", "parity_lint"}
        ),
        "test_connector_footprint_peer_metadata_open.py": frozenset(
            {"connector_lint", "interface_lint", "parity_lint"}
        ),
        "test_connector_footprint_peer_metadata_native_fixture_lane.py": frozenset(
            {"connector_lint", "interface_lint"}
        ),
        "test_connector_footprint_peer_metadata_open_native_fixture_lane.py": frozenset(
            {"connector_lint", "interface_lint"}
        ),
        "test_connector_footprint_peer_missing_metadata.py": frozenset(
            {"connector_lint", "interface_lint", "parity_lint"}
        ),
        "test_connector_footprint_peer_missing_metadata_native_fixture_lane.py": frozenset(
            {"connector_lint", "interface_lint"}
        ),
        "test_connector_footprint_peer_missing_metadata_open.py": frozenset(
            {"connector_lint", "interface_lint"}
        ),
        "test_connector_footprint_peer_missing_metadata_open_native_fixture_lane.py": frozenset(
            {"connector_lint", "interface_lint"}
        ),
        "test_connector_mapped_interface_other_named_rail_native_fixture_lane.py": frozenset(
            {"connector_lint", "interface_lint"}
        ),
        "test_connector_mapped_interface_supply_on_return_net_native_fixture_lane.py": frozenset(
            {"connector_lint", "interface_lint"}
        ),
        "test_connector_mapped_interface_signal_on_named_rail_native_fixture_lane.py": frozenset(
            {"connector_lint", "interface_lint"}
        ),
        "test_connector_mapped_interface_shield_on_return_net_native_fixture_lane.py": frozenset(
            {"connector_lint", "interface_lint"}
        ),
        "test_connector_stateful_contacts.py": frozenset({"connector_lint", "interface_lint"}),
        "test_connector_stateful_contact_architecture.py": frozenset(
            {"connector_lint", "interface_lint"}
        ),
        "test_connector_signal_peer_pin_all_open.py": frozenset(
            {"connector_lint", "interface_lint"}
        ),
        "test_design_lint_determinism_connector_peers.py": frozenset(
            {"connector_lint", "interface_lint", "power_lint", "return_path_lint"}
        ),
        "test_design_lint_determinism_interfaces.py": frozenset(
            {"component_lint", "connector_lint", "interface_lint", "power_lint", "return_path_lint"}
        ),
        "test_design_lint_determinism_control_inputs.py": frozenset(
            {"interface_lint", "power_lint"}
        ),
        "test_design_lint_control_input_bias_paths.py": frozenset({"interface_lint", "power_lint"}),
    }
)
