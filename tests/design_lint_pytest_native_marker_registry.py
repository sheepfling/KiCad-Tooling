from types import MappingProxyType

"""Expected pytest markers for focused lint regression suites."""

PYTEST_NATIVE_LINT_SUITES = MappingProxyType(
    {
        "test_design_lint_mcp_parity_mosfet_gate.py": frozenset(
            {"component_lint", "parity_lint", "slow"}
        ),
        "test_spi_composite_pin_functions.py": frozenset({"interface_lint"}),
        "test_ci_hosted_digital_peer_spi.py": frozenset({"interface_lint", "native_kicad", "slow"}),
        "test_connector_supply_scope.py": frozenset({"connector_lint"}),
        "test_design_lint_complementary_pairs.py": frozenset({"interface_lint"}),
        "test_usb_c_superspeed_lane_pairs.py": frozenset({"interface_lint"}),
        "test_usb_c_superspeed_lane_labels.py": frozenset({"interface_lint"}),
        "test_design_lint_architecture_usb_c_lane_labels.py": frozenset({"interface_lint"}),
        "test_can_line_polarity_native_fixture_lane.py": frozenset(
            {"interface_lint", "native_kicad", "slow"}
        ),
        "test_ethernet_data_label_native_fixture_lane.py": frozenset(
            {
                "interface_lint",
                "native_kicad",
                "slow",
            }
        ),
        "test_ethernet_management_label_native_fixture_lane.py": frozenset(
            {
                "interface_lint",
                "native_kicad",
                "slow",
            }
        ),
        "test_ethernet_management_unconnected_native_fixture_lane.py": frozenset(
            {
                "interface_lint",
                "native_kicad",
                "slow",
            }
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
            {
                "interface_lint",
                "native_kicad",
                "slow",
            }
        ),
        "test_usb_data_same_net_native_fixture_lane.py": frozenset(
            {
                "interface_lint",
                "native_kicad",
                "slow",
            }
        ),
        "test_rs485_ab_same_net_native_fixture_lane.py": frozenset(
            {
                "interface_lint",
                "native_kicad",
                "slow",
            }
        ),
        "test_design_lint_determinism_i2c_signal_named_rail.py": frozenset(
            {"interface_lint", "slow"}
        ),
        "test_i2c_pullup_voltage_coverage.py": frozenset({"interface_lint"}),
        "test_serial_tx_rx_same_net_native_fixture_lane.py": frozenset(
            {
                "interface_lint",
                "native_kicad",
                "slow",
            }
        ),
        "test_serial_tx_rx_label_mismatch_native_fixture_lane.py": frozenset(
            {
                "interface_lint",
                "native_kicad",
                "slow",
            }
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
            {
                "interface_lint",
                "native_kicad",
                "slow",
            }
        ),
        "test_usb_c_cc_named_rail.py": frozenset({"interface_lint"}),
        "test_design_lint_determinism_usb_c_cc_named_rail.py": frozenset(
            {"interface_lint", "slow"}
        ),
        "test_design_lint_determinism_usb_c_sbu_named_rail.py": frozenset(
            {"interface_lint", "slow"}
        ),
        "test_usb_c_cc_named_rail_native_fixture_lane.py": frozenset(
            {
                "interface_lint",
                "native_kicad",
                "slow",
            }
        ),
        "test_usb_c_cc_same_net.py": frozenset({"interface_lint"}),
        "test_design_lint_determinism_usb_c_cc_same_net.py": frozenset({"interface_lint", "slow"}),
        "test_usb_c_cc_same_net_native_fixture_lane.py": frozenset(
            {
                "interface_lint",
                "native_kicad",
                "slow",
            }
        ),
        "test_usb_c_sbu_named_rail.py": frozenset({"interface_lint"}),
        "test_usb_c_sbu_named_rail_native_fixture_lane.py": frozenset(
            {
                "interface_lint",
                "native_kicad",
                "slow",
            }
        ),
        "test_ethernet_signal_named_rail.py": frozenset({"interface_lint"}),
        "test_design_lint_determinism_ethernet_signal_named_rail.py": frozenset(
            {
                "interface_lint",
                "slow",
            }
        ),
        "test_design_lint_determinism_can_signal_named_rail.py": frozenset(
            {"interface_lint", "slow"}
        ),
        "test_can_signal_named_rail_native_fixture_lane.py": frozenset(
            {
                "interface_lint",
                "native_kicad",
                "slow",
            }
        ),
        "test_ethernet_signal_named_rail_native_fixture_lane.py": frozenset(
            {
                "interface_lint",
                "native_kicad",
                "slow",
            }
        ),
        "test_spi_signal_named_rail_native_fixture_lane.py": frozenset(
            {
                "interface_lint",
                "native_kicad",
                "slow",
            }
        ),
        "test_rs485_data_direction_label_mismatch_native_fixture_lane.py": frozenset(
            {
                "interface_lint",
                "native_kicad",
                "slow",
            }
        ),
        "test_rs485_data_direction_label_mismatch.py": frozenset({"interface_lint"}),
        "test_rs485_data_input_output_same_net.py": frozenset({"interface_lint"}),
        "test_rs485_data_input_output_same_net_native_fixture_lane.py": frozenset(
            {
                "interface_lint",
                "native_kicad",
                "slow",
            }
        ),
        "test_rs485_unconnected_data_pins.py": frozenset({"interface_lint"}),
        "test_rs485_unconnected_data_pins_native_fixture_lane.py": frozenset(
            {
                "interface_lint",
                "native_kicad",
                "slow",
            }
        ),
        "test_serial_tx_output_sharing.py": frozenset({"interface_lint"}),
        "test_serial_tx_output_sharing_native_fixture_lane.py": frozenset(
            {
                "interface_lint",
                "native_kicad",
                "slow",
            }
        ),
        "test_spi_data_polarity_native_fixture_lane.py": frozenset(
            {"interface_lint", "native_kicad", "slow"}
        ),
        "test_spi_unconnected_data_pins_native_fixture_lane.py": frozenset(
            {
                "interface_lint",
                "native_kicad",
                "slow",
            }
        ),
        "test_spi_clock_select_label_mismatch.py": frozenset({"interface_lint"}),
        "test_spi_clock_select_label_mismatch_native_fixture_lane.py": frozenset(
            {
                "interface_lint",
                "native_kicad",
                "slow",
            }
        ),
        "test_spi_shared_chip_select.py": frozenset({"interface_lint"}),
        "test_spi_shared_data_outputs.py": frozenset({"interface_lint"}),
        "test_spi_shared_chip_select_native_fixture_lane.py": frozenset(
            {
                "interface_lint",
                "native_kicad",
                "slow",
            }
        ),
        "test_spi_shared_data_outputs_native_fixture_lane.py": frozenset(
            {
                "interface_lint",
                "native_kicad",
                "slow",
            }
        ),
        "test_usb_data_polarity_native_fixture_lane.py": frozenset(
            {"interface_lint", "native_kicad", "slow"}
        ),
        "test_design_lint_decoupling.py": frozenset({"component_lint", "power_lint"}),
        "test_design_lint_dc_reference.py": frozenset({"power_lint"}),
        "test_design_lint_determinism_power_connectivity.py": frozenset({"power_lint"}),
        "test_usb_peer_reference_superspeed.py": frozenset({"interface_lint"}),
        "test_usb_superspeed_peer_reference_native_fixture_lane.py": frozenset({"interface_lint"}),
        "test_design_lint_policy.py": frozenset({"connector_lint", "return_path_lint"}),
        "test_electrical_can_termination.py": frozenset({"interface_lint"}),
        "test_electrical_power_connectivity.py": frozenset({"power_lint"}),
        "test_regulator_feedback.py": frozenset({"power_lint"}),
        "test_regulator_feedback_native_fixture.py": frozenset(
            {"power_lint", "native_kicad", "slow"}
        ),
        "test_power_sequences.py": frozenset({"power_lint"}),
        "test_power_paths.py": frozenset({"power_lint"}),
        "test_power_sequence_fixture_lane.py": frozenset({"power_lint"}),
        "test_power_sequence_native_fixture_lane.py": frozenset({"power_lint"}),
        "test_electrical_component_evidence.py": frozenset({"component_lint", "evidence_lint"}),
        "test_mosfet_stress.py": frozenset({"component_lint"}),
        "test_mosfet_gate_connectivity.py": frozenset({"component_lint"}),
        "test_mosfet_gate_source_bias.py": frozenset({"component_lint"}),
        "test_mosfet_gate_direct_drive.py": frozenset({"component_lint"}),
        "test_mosfet_gate_native_fixture.py": frozenset({"component_lint", "native_kicad", "slow"}),
        "test_polarized_capacitor_native_fixture.py": frozenset(
            {
                "component_lint",
                "native_kicad",
                "slow",
            }
        ),
        "test_diode_rail_orientation_native_fixture.py": frozenset(
            {
                "component_lint",
                "native_kicad",
                "slow",
            }
        ),
        "test_mosfet_terminal_order_native_fixture.py": frozenset(
            {
                "component_lint",
                "native_kicad",
                "slow",
            }
        ),
        "test_mosfet_drain_source_same_net.py": frozenset({"component_lint"}),
        "test_mosfet_gate_source_same_net.py": frozenset({"component_lint"}),
        "test_mosfet_gate_drain_same_net.py": frozenset({"component_lint"}),
        "test_mosfet_drain_source_same_net_native_fixture.py": frozenset(
            {
                "component_lint",
                "native_kicad",
                "slow",
            }
        ),
        "test_design_lint_determinism_mosfet_drain_source.py": frozenset(
            {"component_lint", "slow"}
        ),
        "test_bjt_terminal_order_native_fixture.py": frozenset(
            {
                "component_lint",
                "native_kicad",
                "slow",
            }
        ),
        "test_bjt_base_emitter_same_net.py": frozenset({"component_lint"}),
        "test_bjt_base_collector_same_net.py": frozenset({"component_lint"}),
        "test_bjt_base_collector_same_net_native_fixture.py": frozenset(
            {
                "component_lint",
                "native_kicad",
                "slow",
            }
        ),
        "test_bjt_base_drive_native_fixture.py": frozenset(
            {
                "component_lint",
                "native_kicad",
                "slow",
            }
        ),
        "test_bjt_base_drive.py": frozenset({"component_lint"}),
        "test_bjt_base_bias.py": frozenset({"component_lint"}),
        "test_design_lint_determinism_bjt_base_bias.py": frozenset({"component_lint", "slow"}),
        "test_bjt_base_bias_native_fixture.py": frozenset(
            {
                "component_lint",
                "native_kicad",
                "slow",
            }
        ),
        "test_electrical_connector_evidence.py": frozenset({"connector_lint", "evidence_lint"}),
        "test_electrical_connector_return_parity.py": frozenset(
            {
                "connector_lint",
                "return_path_lint",
                "parity_lint",
            }
        ),
        "test_pin_connectivity_acceptance.py": frozenset({"connector_lint"}),
        "test_electrical_pcb_return_evidence.py": frozenset({"return_path_lint", "evidence_lint"}),
        "test_electrical_test_access_evidence.py": frozenset({"pcb_lint", "evidence_lint"}),
        "test_design_lint_i2c_missing_pullups.py": frozenset({"interface_lint"}),
        "test_design_lint_i2c_equivalent_resistance.py": frozenset({"interface_lint"}),
        "test_design_lint_i2c_pullup_rail_families.py": frozenset({"interface_lint"}),
        "test_ci_hosted_control_inputs.py": frozenset({"interface_lint"}),
        "test_electrical_rs485_contract.py": frozenset({"interface_lint"}),
        "test_design_lint_led_topology.py": frozenset({"component_lint", "power_lint"}),
        "test_design_lint_peer_voltage.py": frozenset({"interface_lint"}),
        "test_design_lint_serial_peer_voltage.py": frozenset({"interface_lint"}),
        "test_design_lint_schematic_connectivity.py": frozenset({"schematic_lint"}),
        "test_design_lint_schematic_text.py": frozenset({"schematic_lint"}),
        "test_schematic_geometry_symbol_arc_body.py": frozenset({"schematic_lint"}),
        "test_connector_peer_pin_all_open.py": frozenset({"connector_lint"}),
        "test_connector_footprint_peer_metadata.py": frozenset(
            {
                "connector_lint",
                "interface_lint",
                "parity_lint",
            }
        ),
        "test_connector_footprint_peer_metadata_open.py": frozenset(
            {
                "connector_lint",
                "interface_lint",
                "parity_lint",
            }
        ),
        "test_connector_footprint_peer_metadata_native_fixture_lane.py": frozenset(
            {
                "connector_lint",
                "interface_lint",
            }
        ),
        "test_connector_footprint_peer_metadata_open_native_fixture_lane.py": frozenset(
            {
                "connector_lint",
                "interface_lint",
            }
        ),
        "test_connector_footprint_peer_missing_metadata.py": frozenset(
            {
                "connector_lint",
                "interface_lint",
                "parity_lint",
            }
        ),
        "test_connector_footprint_peer_missing_metadata_native_fixture_lane.py": frozenset(
            {
                "connector_lint",
                "interface_lint",
            }
        ),
        "test_connector_footprint_peer_missing_metadata_open.py": frozenset(
            {
                "connector_lint",
                "interface_lint",
            }
        ),
        "test_connector_footprint_peer_missing_metadata_open_native_fixture_lane.py": frozenset(
            {
                "connector_lint",
                "interface_lint",
            }
        ),
        "test_connector_mapped_interface_other_named_rail_native_fixture_lane.py": frozenset(
            {
                "connector_lint",
                "interface_lint",
            }
        ),
        "test_connector_mapped_interface_supply_on_return_net_native_fixture_lane.py": frozenset(
            {
                "connector_lint",
                "interface_lint",
            }
        ),
        "test_connector_mapped_interface_signal_on_named_rail_native_fixture_lane.py": frozenset(
            {
                "connector_lint",
                "interface_lint",
            }
        ),
        "test_connector_mapped_interface_shield_on_return_net_native_fixture_lane.py": frozenset(
            {
                "connector_lint",
                "interface_lint",
            }
        ),
        "test_design_lint_determinism_connector_all_open.py": frozenset({"connector_lint"}),
        "test_design_lint_connector_power_pins.py": frozenset({"connector_lint", "power_lint"}),
        "test_connector_stateful_contacts.py": frozenset({"connector_lint", "interface_lint"}),
        "test_connector_stateful_contact_architecture.py": frozenset(
            {"connector_lint", "interface_lint"}
        ),
        "test_design_lint_connector_named_power_input_peers.py": frozenset(
            {
                "connector_lint",
                "power_lint",
            }
        ),
        "test_design_lint_connector_named_power_input_divergence.py": frozenset(
            {
                "connector_lint",
                "power_lint",
            }
        ),
        "test_design_lint_connector_named_power_output_peers.py": frozenset(
            {
                "connector_lint",
                "power_lint",
            }
        ),
        "test_design_lint_connector_named_power_output_divergence.py": frozenset(
            {
                "connector_lint",
                "power_lint",
            }
        ),
        "test_design_lint_mcp_parity_connector_named_power_peers.py": frozenset(
            {
                "connector_lint",
                "power_lint",
                "parity_lint",
            }
        ),
        "test_connector_named_power_input_native_fixture_lane.py": frozenset(
            {
                "connector_lint",
                "power_lint",
            }
        ),
        "test_connector_named_power_output_native_fixture_lane.py": frozenset(
            {
                "connector_lint",
                "power_lint",
            }
        ),
        "test_native_db9_return_contracts.py": frozenset({"connector_lint", "return_path_lint"}),
        "test_connector_signal_peer_pin_all_open.py": frozenset(
            {"connector_lint", "interface_lint"}
        ),
        "test_component_peer_pin_all_open.py": frozenset({"component_lint"}),
        "test_component_peer_pin_mixed_open.py": frozenset({"component_lint"}),
        "test_component_peer_pin_assignment_outlier.py": frozenset({"component_lint"}),
        "test_component_peer_pin_assignment_native_fixture_lane.py": frozenset({"component_lint"}),
        "test_component_named_peer_power_input_all_open.py": frozenset(
            {"component_lint", "power_lint"}
        ),
        "test_component_named_peer_power_input_all_open_native.py": frozenset(
            {
                "component_lint",
                "power_lint",
            }
        ),
        "test_design_lint_determinism_component_peers.py": frozenset(
            {
                "component_lint",
                "connector_lint",
                "power_lint",
            }
        ),
        "test_design_lint_determinism_components.py": frozenset(
            {
                "component_lint",
                "power_lint",
                "return_path_lint",
            }
        ),
        "test_design_lint_determinism_connector_peers.py": frozenset(
            {
                "connector_lint",
                "interface_lint",
                "power_lint",
                "return_path_lint",
            }
        ),
        "test_design_lint_determinism_interfaces.py": frozenset(
            {
                "interface_lint",
                "connector_lint",
                "component_lint",
                "power_lint",
                "return_path_lint",
            }
        ),
        "test_design_lint_determinism_control_inputs.py": frozenset(
            {"power_lint", "interface_lint"}
        ),
        "test_design_lint_control_input_bias_paths.py": frozenset({"interface_lint", "power_lint"}),
        "test_design_lint_mcp_parity_peer_pin_assignment_outlier.py": frozenset(
            {
                "component_lint",
                "parity_lint",
            }
        ),
        "test_pcb_reference_plane_native_fixture_lane.py": frozenset(
            {"pcb_lint", "return_path_lint"}
        ),
        "test_pcb_switching_loop_native_fixture_lane.py": frozenset(
            {"pcb_lint", "return_path_lint"}
        ),
        "test_pcb_return_path_native_fixture_lane.py": frozenset({"pcb_lint", "return_path_lint"}),
        "test_pcb_access_fixture_lane.py": frozenset({"pcb_lint"}),
        "test_pcb_touch_pad_clearance.py": frozenset({"pcb_lint"}),
        "test_design_lint_determinism_pcb_touch_pad_clearance.py": frozenset({"pcb_lint"}),
        "test_design_lint_determinism_pcb_required_fitted_reference.py": frozenset({"pcb_lint"}),
        "test_design_lint_determinism_pcb_board_only.py": frozenset({"pcb_lint"}),
        "test_design_lint_determinism_pcb_dnp.py": frozenset({"pcb_lint"}),
        "test_design_lint_determinism_pcb_value.py": frozenset({"pcb_lint"}),
        "test_design_lint_determinism_pcb_pad_net.py": frozenset({"pcb_lint"}),
        "test_pcb_touch_pad_clearance_native.py": frozenset({"pcb_lint"}),
        "test_ci_hosted_pcb_fixture_schedule.py": frozenset({"pcb_lint", "return_path_lint"}),
    }
)
