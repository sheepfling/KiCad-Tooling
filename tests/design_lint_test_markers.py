"""Explicit pytest marker ownership by lint theme and catalogued rule."""

from __future__ import annotations

from collections import defaultdict
from types import MappingProxyType

from kicad_tooling.hwrepo.design_lint_catalog import rule_catalog
from tests.design_lint_component_test_markers import COMPONENT_LINT_TEST_MODULES
from tests.design_lint_connector_test_markers import CONNECTOR_LINT_TEST_MODULES
from tests.design_lint_interface_test_markers import INTERFACE_LINT_TEST_MODULES
from tests.design_lint_pcb_test_markers import PCB_LINT_TEST_MODULES
from tests.design_lint_return_path_test_markers import RETURN_PATH_LINT_TEST_MODULES

# Keep the area catalog explicit. Adding a lint test module here also includes
# it in the portable design_lint selection derived below.
_LINT_AREA_MODULES = MappingProxyType(
    {
        "catalog_lint": frozenset(
            {
                "tests/test_design_lint_backlog.py",
                "tests/test_design_lint_catalog_documentation.py",
                "tests/test_design_lint_catalog.py",
                "tests/test_design_lint_default_mode_policy.py",
                "tests/test_design_lint_catalog_fixtures.py",
                "tests/test_design_lint_catalog_reachability.py",
                "tests/test_lint_tag_selection_catalog.py",
                "tests/test_design_lint_architecture_catalog.py",
                "tests/test_design_lint_field_maturity.py",
                "tests/test_design_lint_field_evidence_sources.py",
                "tests/test_design_lint_fixture_reachability.py",
                "tests/test_design_lint_architecture_theme_suites.py",
                "tests/test_design_lint_architecture_pcb_mechanical_edge.py",
                "tests/test_design_lint_native_gate_architecture.py",
                "tests/test_design_lint_native_fixture_inventory_architecture.py",
                "tests/test_design_lint_architecture_pytest_markers.py",
                "tests/test_design_lint_architecture_pytest_collection.py",
                "tests/test_design_lint_architecture_rule_selectors.py",
                "tests/test_design_lint_architecture_component_supply_voltage_range.py",
                "tests/test_design_lint_power_native_gate_architecture.py",
                "tests/test_design_lint_architecture_pcb_dru_rule_selectors.py",
                "tests/test_design_lint_architecture_serial_endpoint_role_collision.py",
                "tests/test_design_lint_architecture_named_rail_protocols.py",
                "tests/test_design_lint_architecture_signal_divider.py",
            }
        ),
        "schematic_lint": frozenset(
            {
                "tests/test_schematic_geometry_text.py",
                "tests/test_design_lint_schematic_text.py",
                "tests/test_schematic_erc_unknown_rule_key.py",
                "tests/test_design_lint_mcp_parity_schematic_erc_unknown_rule_key.py",
                "tests/test_schematic_erc_invalid_severity_value.py",
                "tests/test_design_lint_mcp_parity_schematic_erc_invalid_severity_value.py",
                "tests/test_schematic_erc_nonstring_severity_value.py",
                "tests/test_design_lint_mcp_parity_schematic_erc_nonstring_severity_value.py",
                "tests/test_schematic_erc_nonstring_severity_value_native.py",
                "tests/test_schematic_geometry_symbol_body.py",
                "tests/test_schematic_geometry_symbol_arc_body.py",
                "tests/test_schematic_geometry_pin_proximity.py",
                "tests/test_schematic_geometry_wire_topology.py",
                "tests/test_schematic_geometry_hierarchy.py",
                "tests/test_schematic_geometry_native_text.py",
                "tests/test_schematic_geometry_native_wire_body.py",
                "tests/test_schematic_geometry_native_symbol_body.py",
                "tests/test_schematic_geometry_native_pin_connectivity.py",
                "tests/test_schematic_geometry_native_wire_topology.py",
                "tests/test_design_lint_clock_series_trial.py",
                "tests/test_design_lint_mcp_parity_schematic_connectivity.py",
                "tests/test_design_lint_mcp_parity_schematic_geometry.py",
                "tests/test_design_lint_mcp_parity_schematic_hierarchy.py",
                "tests/test_design_lint_architecture_schematic_candidate_evidence.py",
                "tests/test_schematic_pin_candidate_evidence.py",
                "tests/test_schematic_wire_topology_candidate_evidence.py",
                "tests/test_schematic_label_candidate_evidence.py",
                "tests/test_schematic_text_candidate_evidence.py",
                "tests/test_schematic_symbol_body_candidate_evidence.py",
            }
        ),
        "component_lint": COMPONENT_LINT_TEST_MODULES,
        "connector_lint": CONNECTOR_LINT_TEST_MODULES,
        "interface_lint": INTERFACE_LINT_TEST_MODULES,
        "power_lint": frozenset(
            {
                "tests/test_design_lint_control_input_arrays.py",
                "tests/test_open_drain_control_voltage.py",
                "tests/test_design_lint_mcp_parity_open_drain_control_voltage.py",
                "tests/test_open_drain_control_voltage_native_fixture_lane.py",
                "tests/test_connector_unconnected_power_output.py",
                "tests/test_design_lint_connector_power_pins.py",
                "tests/test_design_lint_connector_named_power_input_peers.py",
                "tests/test_design_lint_connector_named_power_input_divergence.py",
                "tests/test_design_lint_architecture_connector_named_power_alias_candidate_evidence.py",
                "tests/test_design_lint_architecture_connector_footprint_named_divergence_evidence.py",
                "tests/test_connector_footprint_power_input.py",
                "tests/test_connector_footprint_power_output.py",
                "tests/test_design_lint_connector_named_power_output_peers.py",
                "tests/test_design_lint_connector_named_power_output_divergence.py",
                "tests/test_design_lint_mcp_parity_connector_named_power_peers.py",
                "tests/test_connector_named_power_input_native_fixture_lane.py",
                "tests/test_connector_footprint_named_power_input_native_fixture_lane.py",
                "tests/test_connector_footprint_named_power_input_all_open.py",
                "tests/test_connector_footprint_named_power_input_all_open_native_fixture_lane.py",
                "tests/test_connector_footprint_named_power_output_all_open.py",
                "tests/test_connector_footprint_named_power_output_all_open_native_fixture_lane.py",
                "tests/test_connector_footprint_named_power_output_divergence.py",
                "tests/test_connector_footprint_named_power_output_native_fixture_lane.py",
                "tests/test_connector_footprint_peer_parity.py",
                "tests/test_connector_footprint_same_voltage_power_input_parity.py",
                "tests/test_connector_named_power_output_native_fixture_lane.py",
                "tests/test_design_lint_mcp_parity_connector_power_output.py",
                "tests/test_component_unconnected_power_output.py",
                "tests/test_component_power_input_native_fixture_lane.py",
                "tests/test_design_lint_mcp_parity_unconnected_power_output.py",
                "tests/test_component_power_ratings.py",
                "tests/test_component_supply_voltage_range.py",
                "tests/test_component_supply_voltage_range_parity.py",
                "tests/test_component_supply_range_map_coverage.py",
                "tests/test_component_supply_range_map_coverage_parity.py",
                "tests/test_component_rating_native_fixture_lane.py",
                "tests/test_design_lint_power_native_gate_architecture.py",
                "tests/test_component_peer_power_fixture_lane.py",
                "tests/test_peer_power_assignment_symbol_groups.py",
                "tests/test_peer_power_assignment_part_id_groups.py",
                "tests/test_peer_power_assignment_cli_mcp.py",
                "tests/test_peer_power_assignment_native.py",
                "tests/test_component_named_peer_power_input_divergence.py",
                "tests/test_component_named_peer_power_input_all_open.py",
                "tests/test_component_named_peer_power_input_all_open_native.py",
                "tests/test_design_lint_determinism_component_peers.py",
                "tests/test_design_lint_determinism_power_input_peers.py",
                "tests/test_ci_hosted_component_peer_power.py",
                "tests/test_net_dc_reference_native_fixture_lane.py",
                "tests/test_design_lint_determinism_interfaces.py",
                "tests/test_design_lint_determinism_power_connectivity.py",
                "tests/test_design_lint_determinism_regulator.py",
                "tests/test_design_lint_mcp_parity_analog.py",
                "tests/test_design_lint_mcp_parity_components.py",
                "tests/test_led_current_range.py",
                "tests/test_design_lint_mcp_parity_led_current.py",
                "tests/test_design_lint_mcp_parity_peer_pins.py",
                "tests/test_design_lint_mcp_parity_usb_generic_connector_pair.py",
                "tests/test_can_generic_connector_pair_review.py",
                "tests/test_can_generic_connector_native_fixture_lane.py",
                "tests/test_can_generic_connector_native_fixture_registry.py",
                "tests/test_design_lint_architecture_can_generic_connector.py",
                "tests/test_design_lint_mcp_parity_can_generic_connector_pair.py",
                "tests/test_design_lint_mcp_parity_spi_generic_connector_triad.py",
                "tests/test_design_lint_mcp_parity_power_input.py",
                "tests/test_connector_named_power_pin_fixture_lane.py",
                "tests/test_design_lint_mcp_parity_power_paths.py",
                "tests/test_design_lint_mcp_parity_protection.py",
                "tests/test_peer_power_output.py",
                "tests/test_hosted_power_path_requirements.py",
                "tests/test_power_path_fixture_lane.py",
                "tests/test_power_path_native_fixture_lane.py",
                "tests/test_power_paths.py",
                "tests/test_power_input_source_paths.py",
                "tests/test_power_input_source_anchors.py",
                "tests/test_power_input_policy.py",
                "tests/test_power_sequence_fixture_lane.py",
                "tests/test_power_sequence_native_fixture_lane.py",
                "tests/test_power_sequence_cycles.py",
                "tests/test_ic_rail_capacitor_native_fixture_lane.py",
                "tests/test_power_sequences.py",
                "tests/test_regulator_feedback.py",
                "tests/test_regulator_feedback_native_fixture.py",
                "tests/test_design_lint_architecture_mapped_candidate_evidence.py",
                "tests/test_connector_mapped_interface_candidate_evidence.py",
                "tests/test_design_lint_architecture_connector_mapped_interface_candidate_evidence.py",
                "tests/test_design_lint_architecture_mapped_contact_sharing_candidate_evidence.py",
                "tests/test_design_lint_mcp_parity_mapped_contact_sharing.py",
                "tests/test_connector_mapped_named_peer_supply_split.py",
                "tests/test_connector_mapped_named_peer_supply_split_native.py",
                "tests/test_connector_mapped_named_peer_signal_split.py",
                "tests/test_connector_mapped_named_peer_signal_split_native.py",
                "tests/test_design_lint_mcp_parity_mapped_peer_supply_split.py",
                "tests/test_connector_mapped_shield_signal_sharing.py",
                "tests/test_connector_mapped_signal_return_sharing.py",
                "tests/test_design_lint_architecture_power_candidate_evidence.py",
                "tests/test_power_candidate_evidence.py",
                "tests/test_design_lint_architecture_return_candidate_evidence.py",
                "tests/test_return_candidate_evidence.py",
                "tests/test_two_pin_fuses.py",
                "tests/test_two_pin_switches.py",
            }
        ),
        "evidence_lint": frozenset(
            {
                "tests/test_connector_fixture_lane_evidence.py",
                "tests/test_ethernet_data_labels.py",
                "tests/test_ethernet_management_labels.py",
                "tests/test_design_lint_architecture_ethernet.py",
                "tests/test_ethernet_unconnected_candidate_evidence.py",
                "tests/test_design_lint_architecture_ethernet_unconnected_candidate_evidence.py",
                "tests/test_can_tx_rx_same_net_candidate_evidence.py",
                "tests/test_design_lint_architecture_can_tx_rx_candidate_evidence.py",
                "tests/test_spi_same_net_candidate_evidence.py",
                "tests/test_design_lint_architecture_spi_same_net_candidate_evidence.py",
                "tests/test_named_rail_candidate_evidence.py",
                "tests/test_named_rail_line_candidate_evidence.py",
                "tests/test_connector_footprint_all_open_candidate_evidence.py",
                "tests/test_connector_footprint_peer_metadata_evidence.py",
                "tests/test_design_lint_architecture_connector_footprint_peer_metadata_evidence.py",
                "tests/test_connector_footprint_named_open_candidate_evidence.py",
                "tests/test_connector_mapped_interface_signal_peer_context_native.py",
                "tests/test_design_lint_architecture_connector_footprint_named_open_evidence.py",
                "tests/test_connector_unanchored_scope_candidate_evidence.py",
                "tests/test_design_lint_architecture_connector_unanchored_scope_candidate_evidence.py",
                "tests/test_connector_unanchored_coverage_candidate_evidence.py",
                "tests/test_design_lint_architecture_connector_unanchored_coverage_candidate_evidence.py",
                "tests/test_connector_unanchored_assignment_candidate_evidence.py",
                "tests/test_design_lint_architecture_connector_unanchored_assignment_candidate_evidence.py",
                "tests/test_signal_label_role_candidate_evidence.py",
                "tests/test_design_lint_architecture_signal_label_candidate_evidence.py",
                "tests/test_connector_stateful_contacts.py",
                "tests/test_connector_stateful_contact_architecture.py",
                "tests/test_design_lint_connectivity_reconciliation.py",
                "tests/test_design_lint_connectivity_snapshot_inspection.py",
                "tests/test_design_lint_mcp_parity_reconciliation.py",
                "tests/test_design_lint_mcp_parity_signal_divider.py",
                "tests/test_design_lint_mcp_parity_led_current.py",
                "tests/test_contract_coach_capture.py",
                "tests/test_contract_coach_evidence.py",
                "tests/test_empty_netlist_evidence_native_fixture_lane.py",
                "tests/test_electrical_component_evidence.py",
                "tests/test_electrical_connector_evidence.py",
                "tests/test_design_lint_mcp_parity_mapped_peer_supply_split.py",
                "tests/test_electrical_pcb_return_evidence.py",
                "tests/test_electrical_test_access_evidence.py",
                "tests/test_test_access_probe_holes.py",
                "tests/test_electrical_test_access_parity.py",
                "tests/test_design_lint_architecture_pcb_measurement_candidate_evidence.py",
                "tests/test_pcb_measurement_candidate_evidence.py",
                "tests/test_design_lint_architecture_mapped_candidate_evidence.py",
                "tests/test_design_lint_architecture_connector_all_open_candidate_evidence.py",
                "tests/test_design_lint_architecture_connector_footprint_named_divergence_evidence.py",
                "tests/test_design_lint_architecture_mosfet_gate_candidate_evidence.py",
                "tests/test_design_lint_architecture_bjt_base_candidate_evidence.py",
                "tests/test_tx_output_sharing_candidate_evidence.py",
                "tests/test_design_lint_architecture_tx_output_sharing_candidate_evidence.py",
                "tests/test_two_wire_same_net_candidate_evidence.py",
                "tests/test_design_lint_architecture_two_wire_same_net_candidate_evidence.py",
                "tests/test_usb_c_cc_same_net_candidate_evidence.py",
                "tests/test_design_lint_architecture_usb_c_cc_same_net_candidate_evidence.py",
                "tests/test_design_lint_architecture_component_repeated_signal_candidate_evidence.py",
                "tests/test_component_peer_open_candidate_evidence.py",
                "tests/test_design_lint_architecture_component_peer_open_candidate_evidence.py",
                "tests/test_bjt_base_candidate_evidence.py",
                "tests/test_design_lint_architecture_power_candidate_evidence.py",
                "tests/test_power_candidate_evidence.py",
                "tests/test_component_terminal_order_candidate_evidence.py",
                "tests/test_design_lint_architecture_component_terminal_order_candidate_evidence.py",
                "tests/test_component_polarity_candidate_evidence.py",
                "tests/test_design_lint_architecture_component_polarity_candidate_evidence.py",
                "tests/test_design_lint_architecture_external_protection_models.py",
                "tests/test_design_lint_architecture_digital_peer_voltage_candidate_evidence.py",
                "tests/test_digital_peer_voltage_candidate_evidence.py",
                "tests/test_design_lint_architecture_return_distribution_candidate_evidence.py",
                "tests/test_return_distribution_candidate_evidence.py",
                "tests/test_design_lint_architecture_serial_peer_candidate_evidence.py",
                "tests/test_serial_peer_candidate_evidence.py",
                "tests/test_design_lint_architecture_spi_bias_candidate_evidence.py",
                "tests/test_spi_bias_candidate_evidence.py",
                "tests/test_design_lint_architecture_spi_peer_candidate_evidence.py",
                "tests/test_spi_peer_candidate_evidence.py",
                "tests/test_design_lint_architecture_i2c_peer_candidate_evidence.py",
                "tests/test_i2c_peer_candidate_evidence.py",
                "tests/test_design_lint_architecture_can_peer_reference_candidate_evidence.py",
                "tests/test_can_peer_reference_candidate_evidence.py",
                "tests/test_design_lint_architecture_rs485_peer_candidate_evidence.py",
                "tests/test_rs485_peer_candidate_evidence.py",
                "tests/test_design_lint_architecture_i3c_unconnected_candidate_evidence.py",
                "tests/test_i3c_unconnected_candidate_evidence.py",
                "tests/test_design_lint_architecture_two_pin_candidate_evidence.py",
                "tests/test_two_pin_candidate_evidence.py",
                "tests/test_design_lint_architecture_spi_participant_candidate_evidence.py",
                "tests/test_spi_participant_candidate_evidence.py",
                "tests/test_design_lint_architecture_usb_c_port_candidate_evidence.py",
                "tests/test_usb_c_port_candidate_evidence.py",
                "tests/test_design_lint_architecture_usb_peer_candidate_evidence.py",
                "tests/test_usb_peer_candidate_evidence.py",
                "tests/test_design_lint_architecture_usb_data_polarity_candidate_evidence.py",
                "tests/test_usb_data_polarity_candidate_evidence.py",
                "tests/test_design_lint_architecture_transformer_candidate_evidence.py",
                "tests/test_transformer_candidate_evidence.py",
                "tests/test_connector_supply_domain_net_sharing.py",
                "tests/test_design_lint_architecture_connector_supply_domain_candidate_evidence.py",
                "tests/test_design_lint_architecture_connector_named_power_alias_candidate_evidence.py",
                "tests/test_design_lint_connector_named_power_input_peers.py",
                "tests/test_design_lint_connector_named_power_input_divergence.py",
                "tests/test_design_lint_connector_named_power_output_peers.py",
                "tests/test_design_lint_connector_named_power_output_divergence.py",
                "tests/test_design_lint_mcp_parity_connector_named_power_peers.py",
                "tests/test_design_lint_mcp_parity_connector_supply_domains.py",
                "tests/test_design_lint_mcp_parity_mapped_contact_sharing.py",
                "tests/test_connector_mapped_interface_candidate_evidence.py",
                "tests/test_design_lint_architecture_connector_mapped_interface_candidate_evidence.py",
                "tests/test_design_lint_architecture_mapped_contact_sharing_candidate_evidence.py",
                "tests/test_connector_mapped_shield_signal_sharing.py",
                "tests/test_connector_mapped_signal_return_sharing.py",
                "tests/test_design_lint_architecture_pcb_drc_global_severity_candidate_evidence.py",
                "tests/test_design_lint_architecture_pcb_dru_rule_candidate_evidence.py",
                "tests/test_pcb_dru_rule_review.py",
                "tests/test_pcb_dru_severity_exclusion_review.py",
                "tests/test_pcb_dru_text_variable_review.py",
                "tests/test_pcb_dru_duplicate_rule_names.py",
                "tests/test_pcb_dru_duplicate_rule_names_native.py",
                "tests/test_pcb_dru_conflicting_severities.py",
                "tests/test_pcb_dru_conflicting_severities_native.py",
                "tests/test_design_lint_mcp_parity_pcb_dru_rule_review.py",
                "tests/test_design_lint_mcp_parity_pcb_dru_severity_exclusion.py",
                "tests/test_design_lint_mcp_parity_pcb_dru_text_variable.py",
                "tests/test_design_lint_mcp_parity_pcb_dru_duplicate_rule_names.py",
                "tests/test_design_lint_mcp_parity_pcb_dru_conflicting_severities.py",
                "tests/test_pcb_drc_global_severity_review.py",
                "tests/test_design_lint_architecture_schematic_candidate_evidence.py",
                "tests/test_schematic_pin_candidate_evidence.py",
                "tests/test_schematic_wire_topology_candidate_evidence.py",
                "tests/test_schematic_label_candidate_evidence.py",
                "tests/test_schematic_text_candidate_evidence.py",
                "tests/test_schematic_symbol_body_candidate_evidence.py",
            }
        ),
        "pcb_lint": PCB_LINT_TEST_MODULES,
        "return_path_lint": RETURN_PATH_LINT_TEST_MODULES,
        "parity_lint": frozenset(
            {
                "tests/test_component_supply_range_map_coverage_parity.py",
                "tests/test_design_lint_mcp_parity_connector_named_power_peers.py",
                "tests/test_design_lint_mcp_parity_mapped_interface_signal.py",
                "tests/test_design_lint_mcp_parity_mapped_contact_sharing.py",
                "tests/test_design_lint_mcp_parity_mapped_peer_supply_split.py",
                "tests/test_design_lint_mcp_parity_reviewed_peer_signal_domains.py",
                "tests/test_design_lint_mcp_parity_peer_pin_assignment_outlier.py",
                "tests/test_connector_footprint_peer_parity.py",
                "tests/test_connector_footprint_peer_metadata_open.py",
                "tests/test_design_lint_mcp_parity_peer_pins.py",
                "tests/test_design_lint_mcp_parity_two_pin_varistors.py",
                "tests/test_design_lint_mcp_parity_two_pin_speakers.py",
                "tests/test_design_lint_mcp_parity_unconnected_power_output.py",
                "tests/test_design_lint_i2c_parity.py",
                "tests/test_design_lint_serial_parity.py",
                "tests/test_electrical_connector_return_parity.py",
                "tests/test_electrical_control_input_parity.py",
                "tests/test_electrical_power_connectivity_parity.py",
                "tests/test_electrical_rs485_parity.py",
                "tests/test_electrical_simulator_parity.py",
                "tests/test_electrical_test_access_parity.py",
                "tests/test_design_lint_mcp_parity_connector_returns.py",
                "tests/test_design_lint_mcp_parity_led_current.py",
                "tests/test_connector_peer_unanchored_scope.py",
                "tests/test_connector_peer_unanchored_coverage_parity.py",
                "tests/test_design_lint_mcp_parity_reconciliation.py",
                "tests/test_electrical_digital_peer_voltage_parity.py",
                "tests/test_electrical_component_rating_parity.py",
                "tests/test_electrical_connector_rating_parity.py",
                "tests/test_design_lint_mcp_parity_jtag_connector_return.py",
                "tests/test_electrical_serial_peer_parity.py",
                "tests/test_electrical_parity.py",
                "tests/test_electrical_i2c_parity.py",
                "tests/test_electrical_usb_c_parity.py",
                "tests/test_design_lint_mcp_parity_usb_reference.py",
                "tests/test_design_lint_mcp_parity_usb_c_sbu_unconnected.py",
                "tests/test_design_lint_mcp_parity_i3c_unconnected.py",
                "tests/test_design_lint_mcp_parity_transformer.py",
                "tests/test_pcb_component_inventory_mcp_parity.py",
                "tests/test_pcb_keepouts_mcp_parity.py",
                "tests/test_pcb_rf_antenna_mcp_parity.py",
                "tests/test_pcb_touch_pad_clearance_mcp_parity.py",
                "tests/test_pcb_signal_path_mcp_parity.py",
                "tests/test_design_lint_mcp_parity_pcb_dru_rule_review.py",
                "tests/test_design_lint_mcp_parity_pcb_dru_severity_exclusion.py",
                "tests/test_design_lint_mcp_parity_pcb_dru_text_variable.py",
                "tests/test_design_lint_mcp_parity_pcb_drc_global_severity_review.py",
                "tests/test_design_lint_mcp_parity_pcb_drc_global_warning_review.py",
                "tests/test_design_lint_mcp_parity_pcb_drc_dfm_warning_review.py",
                "tests/test_design_lint_mcp_parity_pcb_drc_dfm_ignored_review.py",
                "tests/test_design_lint_mcp_parity_pcb_signal_integrity_drc_severity.py",
                "tests/test_design_lint_mcp_parity_pcb_miscellaneous_drc_severity.py",
                "tests/test_design_lint_mcp_parity_pcb_warning_default_drc_ignored.py",
                "tests/test_design_lint_mcp_parity_oscillator_output_paths.py",
                "tests/test_design_lint_mcp_parity_pcb_drc_exclusions.py",
            }
        ),
    }
)

_CORE_DESIGN_LINT_MODULES = frozenset(
    {
        "tests/test_design_lint_catalog.py",
        "tests/test_design_lint_determinism.py",
        "tests/test_electrical.py",
        "tests/test_empty_netlist_evidence_native_fixture_lane.py",
    }
)

_DESIGN_LINT_MODULES = _CORE_DESIGN_LINT_MODULES.union(
    *(modules for modules in _LINT_AREA_MODULES.values())
)


def design_lint_markers_for_path(path: str) -> tuple[str, ...]:
    """Return lint-scope markers assigned to one test module path."""
    markers: list[str] = []
    if path in _DESIGN_LINT_MODULES:
        markers.append("design_lint")
    markers.extend(marker for marker, paths in _LINT_AREA_MODULES.items() if path in paths)
    return tuple(markers)


def _test_reference(reference: str) -> tuple[str, str | None, str] | None:
    """Split a catalogued test reference into module, class, and function."""
    parts = reference.split(".")
    if len(parts) < 3 or parts[0] != "tests":
        return None
    module = ".".join(parts[:2])
    test_class = ".".join(parts[2:-1]) or None
    return module, test_class, parts[-1]


def _catalogued_test_rule_ids() -> dict[tuple[str, str | None, str], tuple[str, ...]]:
    references: dict[tuple[str, str | None, str], set[str]] = defaultdict(set)
    for rule in rule_catalog().rules:
        if rule.status != "active":
            continue
        fixture_references = (
            *rule.fault_fixtures,
            *rule.valid_control_fixtures,
            *rule.metamorphic_fixtures,
        )
        for reference in fixture_references:
            test_reference = _test_reference(reference)
            if test_reference is not None:
                references[test_reference].add(rule.rule_id)
    return {key: tuple(sorted(rule_ids)) for key, rule_ids in references.items()}


_RULE_IDS_BY_TEST = _catalogued_test_rule_ids()


def design_lint_rule_ids_for_test(
    module: str,
    test_class: str | None,
    function: str,
) -> tuple[str, ...]:
    """Return active rule IDs whose catalog names this pytest test."""
    exact = _RULE_IDS_BY_TEST.get((module, test_class, function))
    if exact is not None:
        return exact
    if test_class is not None:
        return _RULE_IDS_BY_TEST.get((module, None, function), ())
    return ()
