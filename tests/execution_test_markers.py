"""Explicit pytest marker ownership for exact-native and slower test modules."""

from __future__ import annotations

_NATIVE_KICAD_MODULES = frozenset(
    {
        "tests/test_component_rating_native_fixture_lane.py",
        "tests/test_polarized_capacitor_native_fixture.py",
        "tests/test_bjt_base_bias_native_fixture.py",
        "tests/test_bjt_terminal_order_native_fixture.py",
        "tests/test_can_native_fixture_lanes.py",
        "tests/test_can_line_polarity_native_fixture_lane.py",
        "tests/test_i2c_signal_label_native_fixture_lane.py",
        "tests/test_serial_tx_rx_same_net_native_fixture_lane.py",
        "tests/test_serial_tx_output_sharing_native_fixture_lane.py",
        "tests/test_spi_data_polarity_native_fixture_lane.py",
        "tests/test_spi_shared_chip_select_native_fixture_lane.py",
        "tests/test_spi_shared_data_outputs_native_fixture_lane.py",
        "tests/test_empty_netlist_evidence_native_fixture_lane.py",
        "tests/test_i2c_pullup_native_fixture_lane.py",
        "tests/test_i2c_peer_reference_native_fixture_lane.py",
        "tests/test_usb_superspeed_peer_reference_native_fixture_lane.py",
        "tests/test_usb_data_polarity_native_fixture_lane.py",
        "tests/test_spi_peer_reference_native_fixture_lane.py",
        "tests/test_native_connector_return_lint.py",
        "tests/test_pcb_access_native_fixture_lane.py",
        "tests/test_pcb_reference_plane_native_fixture_lane.py",
        "tests/test_pcb_switching_loop_native_fixture_lane.py",
        "tests/test_pcb_return_path_native_fixture_lane.py",
        "tests/test_pcb_component_inventory_native_fixture_lane.py",
        "tests/test_power_path_native_fixture_lane.py",
        "tests/test_power_sequence_native_fixture_lane.py",
        "tests/test_pcb_keepouts_native.py",
        "tests/test_pcb_touch_pad_clearance_native.py",
        "tests/test_pcb_mechanical_edge_clearance_native.py",
        "tests/test_pcb_signal_path_native.py",
        "tests/test_schematic_geometry_native_pin_connectivity.py",
        "tests/test_schematic_geometry_native_symbol_body.py",
        "tests/test_schematic_geometry_native_text.py",
        "tests/test_schematic_geometry_native_wire_body.py",
        "tests/test_schematic_geometry_native_wire_topology.py",
    }
)

_SLOW_MODULES = frozenset(
    {
        "tests/test_design_lint_determinism.py",
        "tests/test_design_lint_determinism_generic_peer_pins.py",
        "tests/test_design_lint_determinism_power_input_peers.py",
        "tests/test_electrical_parity.py",
        "tests/test_electrical_connector_return_parity.py",
        "tests/test_electrical_digital_peer_voltage_parity.py",
        "tests/test_electrical_component_rating_parity.py",
        "tests/test_electrical_component_evidence.py",
        "tests/test_electrical_connector_evidence.py",
        "tests/test_electrical_pcb_return_evidence.py",
        "tests/test_electrical_test_access_evidence.py",
        "tests/test_electrical_evidence.py",
        "tests/test_electrical_serial_peer_parity.py",
        "tests/test_electrical_i2c_parity.py",
        "tests/test_electrical_usb_c_parity.py",
        "tests/test_package_ci.py",
        "tests/test_can_native_fixture_lanes.py",
        "tests/test_can_line_polarity_native_fixture_lane.py",
        "tests/test_i2c_signal_label_native_fixture_lane.py",
        "tests/test_serial_tx_rx_same_net_native_fixture_lane.py",
        "tests/test_serial_tx_output_sharing_native_fixture_lane.py",
        "tests/test_spi_data_polarity_native_fixture_lane.py",
        "tests/test_spi_shared_chip_select_native_fixture_lane.py",
        "tests/test_spi_shared_data_outputs_native_fixture_lane.py",
        "tests/test_empty_netlist_evidence_native_fixture_lane.py",
        "tests/test_i2c_pullup_native_fixture_lane.py",
        "tests/test_i2c_peer_reference_native_fixture_lane.py",
        "tests/test_usb_superspeed_peer_reference_native_fixture_lane.py",
        "tests/test_usb_data_polarity_native_fixture_lane.py",
        "tests/test_spi_peer_reference_native_fixture_lane.py",
        "tests/test_component_rating_native_fixture_lane.py",
        "tests/test_polarized_capacitor_native_fixture.py",
        "tests/test_bjt_base_bias_native_fixture.py",
        "tests/test_bjt_terminal_order_native_fixture.py",
        "tests/test_pcb_access_native_fixture_lane.py",
        "tests/test_pcb_reference_plane_native_fixture_lane.py",
        "tests/test_pcb_switching_loop_native_fixture_lane.py",
        "tests/test_pcb_return_path_native_fixture_lane.py",
        "tests/test_pcb_component_inventory_native_fixture_lane.py",
        "tests/test_pcb_mechanical_edge_clearance_native.py",
        "tests/test_power_path_native_fixture_lane.py",
        "tests/test_power_sequence_native_fixture_lane.py",
        "tests/test_schematic_geometry_native_pin_connectivity.py",
        "tests/test_schematic_geometry_native_symbol_body.py",
        "tests/test_schematic_geometry_native_text.py",
        "tests/test_schematic_geometry_native_wire_body.py",
        "tests/test_schematic_geometry_native_wire_topology.py",
    }
)


def execution_markers_for_path(path: str) -> tuple[str, ...]:
    """Return execution-scope markers assigned to one test module path."""
    markers: list[str] = []
    if path in _NATIVE_KICAD_MODULES:
        markers.append("native_kicad")
    if path in _SLOW_MODULES:
        markers.append("slow")
    return tuple(markers)
