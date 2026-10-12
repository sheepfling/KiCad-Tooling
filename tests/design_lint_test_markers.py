"""Explicit pytest marker ownership by lint theme and catalogued rule."""

from __future__ import annotations

from collections import defaultdict

from kicad_tooling.hwrepo.design_lint_catalog import rule_catalog

# Keep the area catalog explicit. Adding a lint test module here also includes
# it in the portable design_lint selection derived below.
_LINT_AREA_MODULES = {
    "catalog_lint": frozenset(
        {
            "tests/test_design_lint_backlog.py",
            "tests/test_design_lint_catalog.py",
            "tests/test_design_lint_catalog_fixtures.py",
            "tests/test_design_lint_catalog_reachability.py",
            "tests/test_design_lint_architecture_catalog.py",
        }
    ),
    "schematic_lint": frozenset(
        {
            "tests/test_schematic_geometry_text.py",
            "tests/test_design_lint_schematic_text.py",
            "tests/test_schematic_geometry_symbol_body.py",
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
        }
    ),
    "component_lint": frozenset(
        {
            "tests/test_component_unconnected_power_output.py",
            "tests/test_design_lint_mcp_parity_unconnected_power_output.py",
            "tests/test_electrical_component_rating_parity.py",
            "tests/test_component_power_ratings.py",
            "tests/test_component_voltage_ratings.py",
            "tests/test_component_rating_native_fixture_lane.py",
            "tests/test_electrical_component_evidence.py",
            "tests/test_component_peer_power_fixture_lane.py",
            "tests/test_peer_power_assignment_symbol_groups.py",
            "tests/test_peer_power_assignment_part_id_groups.py",
            "tests/test_peer_power_assignment_cli_mcp.py",
            "tests/test_peer_power_assignment_native.py",
            "tests/test_control_inputs.py",
            "tests/test_electrical_control_input_parity.py",
            "tests/test_electrical_rs485_parity.py",
            "tests/test_crystal_networks.py",
            "tests/test_design_lint_determinism_analog.py",
            "tests/test_design_lint_mcp_parity_analog.py",
            "tests/test_design_lint_mcp_parity_components.py",
            "tests/test_design_lint_mcp_parity_mapped_custom_passive.py",
            "tests/test_design_lint_mcp_parity_protection.py",
            "tests/test_design_lint_mcp_parity_two_pin_crystal_fuse.py",
            "tests/test_design_lint_mcp_parity_two_pin_passives.py",
            "tests/test_peer_power_output.py",
            "tests/test_peer_signal_output.py",
            "tests/test_peer_signal_input.py",
            "tests/test_peer_bidirectional_pin.py",
            "tests/test_peer_component_pin_identity.py",
            "tests/test_peer_component_pin_coverage.py",
            "tests/test_ci_hosted_component_peer_power.py",
            "tests/test_electrical_power_connectivity_parity.py",
            "tests/test_led_output_heuristics.py",
            "tests/test_led_rail_native_fixture_lane.py",
            "tests/test_open_drain_bias_fixture_lane.py",
            "tests/test_open_drain_heuristics.py",
            "tests/test_ci_hosted_control_inputs.py",
            "tests/test_rc_filters.py",
            "tests/test_two_pin_crystals.py",
            "tests/test_two_pin_diodes.py",
            "tests/test_two_pin_ferrites.py",
            "tests/test_two_pin_fuses.py",
            "tests/test_two_pin_passives.py",
            "tests/test_two_pin_component_native_fixture_lane.py",
            "tests/test_two_pin_switches.py",
        }
    ),
    "connector_lint": frozenset(
        {
            "tests/test_connector_unconnected_power_output.py",
            "tests/test_design_lint_mcp_parity_connector_power_output.py",
            "tests/test_connector_contact_ratings.py",
            "tests/test_electrical_connector_evidence.py",
            "tests/test_electrical_connector_rating_parity.py",
            "tests/test_electrical_connector_pin_relationship_parity.py",
            "tests/test_component_rating_native_fixture_lane.py",
            "tests/test_connector_inventory_coverage.py",
            "tests/test_connector_supply_peer_coverage.py",
            "tests/test_connector_return_role_coverage.py",
            "tests/test_electrical_connector_pin_contracts.py",
            "tests/test_design_lint_mcp_parity_connector_identity.py",
            "tests/test_design_lint_mcp_parity_connector_returns.py",
            "tests/test_design_lint_mcp_parity_peer_pins.py",
            "tests/test_connector_inventory_fixture_lane.py",
            "tests/test_connector_part_id_peers.py",
            "tests/test_connector_peer_pin_coverage.py",
            "tests/test_connector_peer_scope.py",
            "tests/test_connector_return_distribution.py",
            "tests/test_verify_design_lint.py",
            "tests/test_external_protection_contract.py",
            "tests/test_external_protection_review.py",
            "tests/test_connector_return_fixture_lane.py",
            "tests/test_design_lint_determinism_interfaces.py",
            "tests/test_native_connector_return_lint.py",
            "tests/test_ci_hosted_digital_peer_serial.py",
            "tests/test_serial_participants.py",
            "tests/test_serial_participant_net_labels.py",
            "tests/test_serial_peer_reference_review.py",
            "tests/test_serial_peer_reference_coverage.py",
            "tests/test_serial_peer_reference_maps.py",
            "tests/test_serial_peer_reference_boundaries.py",
            "tests/test_serial_peer_native_fixture_lane.py",
            "tests/test_serial_reference_bond_native_fixture_lane.py",
            "tests/test_spi_participants.py",
            "tests/test_usb_c_ports.py",
            "tests/test_ci_hosted_usb_c_ports.py",
            "tests/test_usb_data_paths.py",
            "tests/test_usb_inline_component_paths.py",
            "tests/test_usb_peer_reference_coverage.py",
            "tests/test_usb_peer_reference_paths.py",
            "tests/test_usb_peer_reference_maps.py",
            "tests/test_usb_peer_reference_boundaries.py",
            "tests/test_usb_peer_reference_superspeed.py",
            "tests/test_design_lint_mcp_parity_usb_reference.py",
        }
    ),
    "interface_lint": frozenset(
        {
            "tests/test_control_inputs.py",
            "tests/test_electrical_control_input_parity.py",
            "tests/test_external_protection_contract.py",
            "tests/test_external_protection_review.py",
            "tests/test_design_lint_i2c_parity.py",
            "tests/test_electrical_bus_contract_parity.py",
            "tests/test_electrical_digital_peer_voltage_parity.py",
            "tests/test_electrical_i2c_parity.py",
            "tests/test_electrical_serial_peer_parity.py",
            "tests/test_electrical_usb_c_parity.py",
            "tests/test_design_lint_mcp_parity_mapped_custom_passive.py",
            "tests/test_design_lint_determinism_interfaces.py",
            "tests/test_design_lint_serial_parity.py",
            "tests/test_design_lint_mcp_parity_i2c.py",
            "tests/test_design_lint_mcp_parity_peer_pins.py",
            "tests/test_design_lint_mcp_parity_serial.py",
            "tests/test_design_lint_mcp_parity_spi.py",
            "tests/test_design_lint_mcp_parity_stm32.py",
            "tests/test_spi_peer_reference_architecture.py",
            "tests/test_design_lint_mcp_parity_usb_can.py",
            "tests/test_design_lint_mcp_parity_usb_reference.py",
            "tests/test_design_lint_mcp_parity_usb_data.py",
            "tests/test_can_peer_reference_review.py",
            "tests/test_can_peer_reference_architecture.py",
            "tests/test_design_lint_mcp_parity_can_reference.py",
            "tests/test_can_native_fixture_lanes.py",
            "tests/test_digital_peer_spi_voltage_fixture_lane.py",
            "tests/test_digital_peer_serial_voltage_fixture_lane.py",
            "tests/test_design_lint_serial_peer_voltage.py",
            "tests/test_digital_peer_serial_reference_fixture_lane.py",
            "tests/test_ci_hosted_digital_peer_spi.py",
            "tests/test_ci_hosted_digital_peer_serial.py",
            "tests/test_ci_hosted_component_peer_power.py",
            "tests/test_digital_peer_voltages.py",
            "tests/test_design_lint_peer_voltage.py",
            "tests/test_i2c_address_coverage.py",
            "tests/test_i2c_address_collisions.py",
            "tests/test_i2c_address_straps.py",
            "tests/test_i2c_address_contract.py",
            "tests/test_i2c_pullup_heuristic_coverage.py",
            "tests/test_i2c_peer_reference_review.py",
            "tests/test_i2c_peer_reference_native_fixture_lane.py",
            "tests/test_spi_peer_reference_review.py",
            "tests/test_design_lint_mcp_parity_spi_reference.py",
            "tests/test_spi_peer_reference_native_fixture_lane.py",
            "tests/test_electrical_i2c_contracts.py",
            "tests/test_electrical_spi_contracts.py",
            "tests/test_i2c_pullup_native_fixture_lane.py",
            "tests/test_i2c_pullup_tolerance.py",
            "tests/test_open_drain_bias_fixture_lane.py",
            "tests/test_open_drain_heuristics.py",
            "tests/test_serial_participants.py",
            "tests/test_electrical_serial_contracts.py",
            "tests/test_serial_peer_reference_review.py",
            "tests/test_serial_peer_reference_coverage.py",
            "tests/test_serial_peer_reference_maps.py",
            "tests/test_serial_peer_reference_boundaries.py",
            "tests/test_serial_peer_native_fixture_lane.py",
            "tests/test_serial_reference_bond_native_fixture_lane.py",
            "tests/test_spi_participants.py",
            "tests/test_complementary_pair_native_fixture_lane.py",
            "tests/test_stm32_pin_map.py",
            "tests/test_ci_hosted_stm32.py",
            "tests/test_ci_hosted_control_inputs.py",
            "tests/test_ci_hosted_usb_c_ports.py",
            "tests/test_usb_c_ports.py",
            "tests/test_usb_data_paths.py",
            "tests/test_usb_inline_component_paths.py",
            "tests/test_usb_data_path_native_fixture_lane.py",
            "tests/test_usb_superspeed_peer_reference_native_fixture_lane.py",
            "tests/test_hosted_usb_requirements.py",
            "tests/test_usb_peer_reference_coverage.py",
            "tests/test_usb_peer_reference_paths.py",
            "tests/test_usb_peer_reference_maps.py",
            "tests/test_usb_peer_reference_boundaries.py",
            "tests/test_usb_peer_reference_superspeed.py",
        }
    ),
    "power_lint": frozenset(
        {
            "tests/test_connector_unconnected_power_output.py",
            "tests/test_design_lint_mcp_parity_connector_power_output.py",
            "tests/test_component_unconnected_power_output.py",
            "tests/test_design_lint_mcp_parity_unconnected_power_output.py",
            "tests/test_component_power_ratings.py",
            "tests/test_component_rating_native_fixture_lane.py",
            "tests/test_component_peer_power_fixture_lane.py",
            "tests/test_peer_power_assignment_symbol_groups.py",
            "tests/test_peer_power_assignment_part_id_groups.py",
            "tests/test_peer_power_assignment_cli_mcp.py",
            "tests/test_peer_power_assignment_native.py",
            "tests/test_ci_hosted_component_peer_power.py",
            "tests/test_net_dc_reference_native_fixture_lane.py",
            "tests/test_design_lint_determinism_interfaces.py",
            "tests/test_design_lint_determinism_power_connectivity.py",
            "tests/test_design_lint_determinism_regulator.py",
            "tests/test_design_lint_mcp_parity_analog.py",
            "tests/test_design_lint_mcp_parity_components.py",
            "tests/test_design_lint_mcp_parity_peer_pins.py",
            "tests/test_design_lint_mcp_parity_power_input.py",
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
            "tests/test_two_pin_fuses.py",
            "tests/test_two_pin_switches.py",
        }
    ),
    "evidence_lint": frozenset(
        {
            "tests/test_empty_netlist_evidence_native_fixture_lane.py",
            "tests/test_electrical_component_evidence.py",
            "tests/test_electrical_connector_evidence.py",
            "tests/test_electrical_pcb_return_evidence.py",
            "tests/test_electrical_test_access_evidence.py",
            "tests/test_electrical_test_access_parity.py",
        }
    ),
    "pcb_lint": frozenset(
        {
            "tests/test_electrical_test_access_parity.py",
            "tests/test_electrical_test_access_evidence.py",
            "tests/test_pcb_component_inventory.py",
            "tests/test_pcb_component_inventory_mcp_parity.py",
            "tests/test_pcb_component_inventory_native_fixture_lane.py",
            "tests/test_design_lint_determinism_pcb_component_inventory.py",
            "tests/test_native_connector_return_lint.py",
            "tests/test_pcb_access_native_fixture_lane.py",
            "tests/test_pcb_access_fixture_lane.py",
            "tests/test_pcb_decoupling.py",
            "tests/test_pcb_decoupling_return_vias.py",
            "tests/test_pcb_decoupling_native_fixture_lane.py",
            "tests/test_pcb_drc_coverage.py",
            "tests/test_pcb_footprint_observations.py",
            "tests/test_pcb_keepouts.py",
            "tests/test_pcb_keepouts_mcp_parity.py",
            "tests/test_pcb_keepouts_native.py",
            "tests/test_pcb_protection_path.py",
            "tests/test_pcb_protection_path_native_fixture_lane.py",
            "tests/test_design_lint_determinism_pcb_antenna.py",
            "tests/test_design_lint_determinism_pcb_drc.py",
            "tests/test_design_lint_determinism_pcb_protection.py",
            "tests/test_design_lint_determinism_pcb_track_width.py",
            "tests/test_design_lint_mcp_parity_pcb_layout.py",
            "tests/test_design_lint_mcp_parity_pcb_pairs.py",
            "tests/test_design_lint_mcp_parity_protection.py",
            "tests/test_design_lint_mcp_parity_usb_data.py",
            "tests/test_pcb_reference_plane_lint.py",
            "tests/test_ci_hosted_pcb_fixture_schedule.py",
            "tests/test_pcb_reference_plane_native_fixture_lane.py",
            "tests/test_pcb_switching_loop_native_fixture_lane.py",
            "tests/test_pcb_return_path_native_fixture_lane.py",
            "tests/test_pcb_reference_plane_geometry.py",
            "tests/test_pcb_reference_plane_layers.py",
            "tests/test_pcb_reference_plane_contract.py",
            "tests/test_ci_hosted_pcb_reference_planes.py",
            "tests/test_ci_hosted_pcb_return_paths.py",
            "tests/test_pcb_return_paths.py",
            "tests/test_hosted_pcb_lane_boundaries.py",
            "tests/test_pcb_rf_antenna.py",
            "tests/test_pcb_rf_antenna_mcp_parity.py",
            "tests/test_pcb_signal_path_coverage.py",
            "tests/test_pcb_signal_path_evidence.py",
            "tests/test_pcb_signal_path_hosted_schedule.py",
            "tests/test_pcb_signal_path_lane.py",
            "tests/test_pcb_signal_path_mcp_parity.py",
            "tests/test_pcb_signal_path_native.py",
            "tests/test_pcb_switching_loop_geometry.py",
            "tests/test_pcb_switching_loop_routes.py",
            "tests/test_pcb_track_width.py",
            "tests/test_pcb_track_width_native_fixture_lane.py",
        }
    ),
    "return_path_lint": frozenset(
        {
            "tests/test_electrical_connector_return_parity.py",
            "tests/test_electrical_connector_pin_relationship_parity.py",
            "tests/test_electrical_pcb_return_path_parity.py",
            "tests/test_electrical_pcb_return_evidence.py",
            "tests/test_electrical_serial_peer_parity.py",
            "tests/test_connector_return_distribution.py",
            "tests/test_connector_return_fixture_lane.py",
            "tests/test_ci_hosted_pcb_fixture_schedule.py",
            "tests/test_ci_hosted_digital_peer_serial.py",
            "tests/test_native_connector_return_lint.py",
            "tests/test_design_lint_determinism_pcb_protection.py",
            "tests/test_pcb_decoupling_native_fixture_lane.py",
            "tests/test_pcb_decoupling_return_vias.py",
            "tests/test_pcb_protection_path_native_fixture_lane.py",
            "tests/test_design_lint_mcp_parity_connector_returns.py",
            "tests/test_design_lint_mcp_parity_serial.py",
            "tests/test_pcb_reference_plane_lint.py",
            "tests/test_pcb_reference_plane_native_fixture_lane.py",
            "tests/test_pcb_switching_loop_native_fixture_lane.py",
            "tests/test_pcb_return_path_native_fixture_lane.py",
            "tests/test_pcb_reference_plane_geometry.py",
            "tests/test_pcb_reference_plane_layers.py",
            "tests/test_pcb_reference_plane_contract.py",
            "tests/test_ci_hosted_pcb_reference_planes.py",
            "tests/test_ci_hosted_pcb_return_paths.py",
            "tests/test_pcb_return_paths.py",
            "tests/test_hosted_pcb_lane_boundaries.py",
            "tests/test_pcb_signal_path_coverage.py",
            "tests/test_pcb_signal_path_evidence.py",
            "tests/test_pcb_signal_path_hosted_schedule.py",
            "tests/test_pcb_signal_path_lane.py",
            "tests/test_pcb_signal_path_native.py",
            "tests/test_pcb_switching_loop_geometry.py",
            "tests/test_pcb_switching_loop_routes.py",
            "tests/test_return_net_lint.py",
            "tests/test_electrical_return_contracts.py",
            "tests/test_serial_peer_reference_review.py",
            "tests/test_serial_peer_reference_coverage.py",
            "tests/test_serial_peer_reference_maps.py",
            "tests/test_serial_peer_reference_boundaries.py",
            "tests/test_serial_reference_bond_native_fixture_lane.py",
            "tests/test_usb_peer_reference_coverage.py",
            "tests/test_usb_peer_reference_paths.py",
            "tests/test_usb_peer_reference_maps.py",
            "tests/test_usb_peer_reference_boundaries.py",
            "tests/test_usb_peer_reference_superspeed.py",
        }
    ),
    "parity_lint": frozenset(
        {
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
            "tests/test_electrical_digital_peer_voltage_parity.py",
            "tests/test_electrical_component_rating_parity.py",
            "tests/test_electrical_connector_rating_parity.py",
            "tests/test_electrical_serial_peer_parity.py",
            "tests/test_electrical_parity.py",
            "tests/test_electrical_i2c_parity.py",
            "tests/test_electrical_usb_c_parity.py",
            "tests/test_design_lint_mcp_parity_usb_reference.py",
            "tests/test_pcb_component_inventory_mcp_parity.py",
            "tests/test_pcb_keepouts_mcp_parity.py",
            "tests/test_pcb_rf_antenna_mcp_parity.py",
            "tests/test_pcb_signal_path_mcp_parity.py",
        }
    ),
}

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
