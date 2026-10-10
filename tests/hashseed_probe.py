"""Pytest-invoked worker that emits complete synthetic lint reports."""

from __future__ import annotations

import importlib
import json
import os
import sys

from tests.hashseed_probe_cases import HASHSEED_REPORT_FAMILIES

HASHSEED_FAMILIES_ENV = "KICAD_TEAM_TOOLING_HASHSEED_FAMILIES"

REPORT_ORDER = (
    "i2c_array_fault",
    "i2c_array_control",
    "i2c_array_contract_fault",
    "i2c_array_contract_control",
    "i2c_address_map_fault",
    "i2c_address_map_control",
    "external_protection_fault",
    "external_protection_control",
    "parsed_netlist_pin_metadata",
    "fault",
    "common_control",
    "letter_suffixed_unindexed_return_fault",
    "letter_suffixed_numbered_return_fault",
    "letter_suffixed_return_roles_control",
    "generic_power_input_fault",
    "generic_power_input_control",
    "generic_component_power_input_fault",
    "generic_component_power_input_control",
    "control_input_unconnected_fault",
    "control_input_connected_control",
    "peer_signal_input_fault",
    "peer_signal_input_control",
    "peer_signal_output_fault",
    "peer_signal_output_control",
    "peer_signal_output_part_id_fault",
    "peer_signal_output_part_id_control",
    "peer_signal_input_part_id_fault",
    "peer_signal_input_part_id_control",
    "peer_bidirectional_part_id_fault",
    "peer_bidirectional_part_id_control",
    "peer_bidirectional_fault",
    "peer_bidirectional_control",
    "peer_power_output_part_id_fault",
    "peer_power_output_part_id_control",
    "peer_power_output_part_id_incomplete_identity",
    "peer_power_output_part_id_dedup_fault",
    "peer_power_output_part_id_dedup_control",
    "peer_power_assignment_part_id_fault",
    "peer_power_assignment_part_id_control",
    "db9_split_against_common_requirement",
    "db9_split_against_isolated_requirement",
    "db9_common_against_common_requirement",
    "db9_common_against_isolated_requirement",
    "unconnected_pin_inventory",
    "diode_fault",
    "diode_control",
    "crystal_fault",
    "crystal_control",
    "mapped_crystal_network_fault",
    "mapped_crystal_network_control",
    "mapped_regulator_feedback_fault",
    "mapped_regulator_feedback_control",
    "mapped_rc_filter_fault",
    "mapped_rc_filter_control",
    "fuse_fault",
    "fuse_control",
    "ferrite_fault",
    "ferrite_control",
    "switch_fault",
    "switch_control",
    "peer_pin_fault",
    "connector_part_id_alias_open_fault",
    "connector_part_id_alias_split_fault",
    "connector_part_id_alias_common_control",
    "peer_pin_control",
    "mapped_return_fault",
    "mapped_return_control",
    "mapped_supply_open_peer_fault",
    "mapped_supply_common_control",
    "connector_peer_scope_separate",
    "connector_peer_scope_shared",
    "unlisted_peer_scope_separate_fault",
    "unlisted_peer_scope_shared_fault",
    "unlisted_peer_scope_shared_control",
    "connector_contact_rating_over_limit",
    "connector_contact_rating_boundary_control",
    "mosfet_stress_q2_over_limit",
    "mosfet_stress_multi_device_control",
    "partial_mapped_peer_pin_fault",
    "complete_mapped_peer_pin_control",
    "common_peer_pin_control",
    "pcb_decoupling_distance_fault",
    "pcb_decoupling_distance_control",
    "pcb_signal_path_fault",
    "pcb_signal_path_control",
    "pcb_keepout_fault",
    "pcb_keepout_control",
    "pcb_reference_plane_fault",
    "pcb_reference_plane_control",
    "pcb_protection_path_fault",
    "pcb_protection_path_control",
    "pcb_track_width_fault",
    "pcb_track_width_control",
    "pcb_return_path_disconnected_fault",
    "pcb_return_path_connected_control",
    "pcb_return_path_split_plane_fault",
    "pcb_return_path_single_plane_control",
    "pcb_return_path_unfitted_bond_fault",
    "pcb_return_path_fitted_bond_control",
    "pcb_return_path_unstitched_layer_fault",
    "pcb_return_path_via_stitch_control",
    "pcb_antenna_keepout_fault",
    "pcb_antenna_keepout_control",
    "pcb_differential_pair_rule_fault",
    "pcb_differential_pair_rule_control",
    "pcb_switching_loop_route_ambiguity",
    "pcb_switching_loop_unique_trace",
    "mapped_power_path_fault",
    "mapped_power_path_control",
    "mapped_power_sequence_fault",
    "mapped_power_sequence_control",
    "serial_label_unmapped",
    "serial_label_mapped_control",
    "serial_reference_fault",
    "serial_reference_control",
    "spi_peer_voltage_unmapped",
    "spi_peer_voltage_mapped_control",
    "serial_peer_voltage_unmapped",
    "serial_peer_voltage_mapped_control",
    "can_peer_fault",
    "can_peer_control",
    "usb_data_path_series_fault",
    "usb_data_path_series_control",
    "usb_data_path_direct_topology_control",
    "usb_reference_bond_fault",
    "usb_reference_bond_control",
    "serial_reference_bond_fault",
    "serial_reference_bond_control",
    "usb_multiport_peer_fault",
    "usb_multiport_peer_control",
    "led_output_direct_fault",
    "led_output_parallel_resistor_fault",
    "led_output_series_control",
    "header_only_spi_uart_boundary",
    "serial_label_reference_fault",
    "serial_label_reference_control",
    "stm32_pin_map_fault",
    "stm32_pin_map_control",
    "schematic_wire_crossing_fault",
    "schematic_wire_crossing_junction_control",
)


REPORT_BUILDERS = {
    "returns": "tests.hashseed_probe_cases.returns",
    "connectors": "tests.hashseed_probe_cases.connectors",
    "component_peers": "tests.hashseed_probe_cases.component_peers",
    "components": "tests.hashseed_probe_cases.components",
    "control_inputs": "tests.hashseed_probe_cases.control_inputs",
    "pcb_power": "tests.hashseed_probe_cases.pcb_power",
    "pcb_antenna": "tests.hashseed_probe_cases.pcb_antenna",
    "pcb_drc": "tests.hashseed_probe_cases.pcb_drc",
    "pcb_return_paths": "tests.hashseed_probe_cases.pcb_return_paths",
    "pcb_measurements": "tests.hashseed_probe_cases.pcb_measurements",
    "interfaces": "tests.hashseed_probe_cases.interfaces",
    "analog": "tests.hashseed_probe_cases.analog",
    "schematic_geometry": "tests.hashseed_probe_cases.schematic_geometry",
}


def test_emit_complete_synthetic_design_lint_reports() -> None:
    requested = os.environ.get(HASHSEED_FAMILIES_ENV)
    families = HASHSEED_REPORT_FAMILIES if requested is None else tuple(requested.split(","))
    if not families or any(not family for family in families):
        raise ValueError(f"{HASHSEED_FAMILIES_ENV} must name at least one report family")
    unknown = sorted(set(families) - set(REPORT_BUILDERS))
    if unknown:
        raise ValueError(f"unknown hash-seed report families: {unknown}")
    if len(set(families)) != len(families):
        raise ValueError("hash-seed report families must not be repeated")

    grouped: dict[str, object] = {}
    family_keys: dict[str, tuple[str, ...]] = {}
    for family in families:
        module = importlib.import_module(REPORT_BUILDERS[family])
        family_reports = module.report_cases()
        keys = tuple(name for name in REPORT_ORDER if name in family_reports)
        if len(keys) != len(family_reports):
            raise ValueError(f"{family} produced report names absent from REPORT_ORDER")
        duplicates = sorted(set(grouped) & set(family_reports))
        if duplicates:
            raise ValueError(f"duplicate hash-seed report names: {duplicates}")
        grouped.update(family_reports)
        family_keys[family] = keys
    if requested is None:
        reports = {name: grouped[name] for name in REPORT_ORDER}
    else:
        reports = {name: grouped[name] for name in REPORT_ORDER if name in grouped}
    if not reports:
        raise ValueError("hash-seed report selection produced no cases")
    payload = {
        "hash_marker": hash("kicad-tooling-hash-seed-probe"),
        "hash_randomization": sys.flags.hash_randomization,
        "report_families": family_keys,
        "reports": reports,
    }
    print(
        "DESIGN_LINT_HASHSEED_REPORTS="
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    )
