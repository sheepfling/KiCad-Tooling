"""Apply explicit pytest groups for focused design-lint and cost-aware runs."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.schematic_geometry import (
    SUPPORTED_KICAD_VERSION,
    SUPPORTED_KICAD_VERSIONS,
)
from tests.hosted_ci_support import copy_reference_checkout

pytest_plugins = ("tests.digital_peer_voltage_lane_support",)

_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def native_schematic_geometry_toolchain() -> tuple[Path, str]:
    """Require the exact native KiCad executable for schematic parity checks."""
    cli_value = os.environ.get("KICAD_GEOMETRY_TEST_CLI")
    if not cli_value:
        pytest.skip("set KICAD_GEOMETRY_TEST_CLI for native KiCad parity tests")
    expected_version = os.environ.get("KICAD_GEOMETRY_TEST_VERSION", SUPPORTED_KICAD_VERSION)
    if expected_version not in SUPPORTED_KICAD_VERSIONS:
        raise ValueError(f"unsupported native geometry test version: {expected_version}")
    cli = Path(cli_value).expanduser()
    if not cli.is_file():
        raise FileNotFoundError("KICAD_GEOMETRY_TEST_CLI does not point to a file")
    version = subprocess.run((str(cli), "version"), capture_output=True, text=True, check=False)
    if version.returncode != 0 or version.stdout.strip() != expected_version:
        pytest.fail(
            f"native geometry test requires KiCad {expected_version}; "
            f"reported {version.stdout.strip()!r}"
        )
    return cli, expected_version


@pytest.fixture
def hosted_reference_root(tmp_path: Path) -> Path:
    """Provide a disposable public-template checkout to focused hosted tests."""
    return copy_reference_checkout(tmp_path / "repository")


# Keep the area catalog explicit. Adding a lint test module here also includes
# it in the portable design_lint selection derived below.
_LINT_AREA_MODULES = {
    "schematic_lint": frozenset(
        {
            "tests/test_schematic_geometry_text.py",
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
            "tests/test_component_power_ratings.py",
            "tests/test_component_voltage_ratings.py",
            "tests/test_component_rating_native_fixture_lane.py",
            "tests/test_component_peer_power_fixture_lane.py",
            "tests/test_peer_power_assignment_symbol_groups.py",
            "tests/test_peer_power_assignment_part_id_groups.py",
            "tests/test_peer_power_assignment_cli_mcp.py",
            "tests/test_peer_power_assignment_native.py",
            "tests/test_control_inputs.py",
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
            "tests/test_ci_hosted_digital_peers.py",
            "tests/test_led_output_heuristics.py",
            "tests/test_led_rail_native_fixture_lane.py",
            "tests/test_open_drain_bias_fixture_lane.py",
            "tests/test_open_drain_heuristics.py",
            "tests/test_ci_hosted_control_inputs.py",
            "tests/test_rc_filters.py",
            "tests/test_regulator_feedback.py",
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
            "tests/test_connector_contact_ratings.py",
            "tests/test_component_rating_native_fixture_lane.py",
            "tests/test_connector_inventory_coverage.py",
            "tests/test_connector_supply_peer_coverage.py",
            "tests/test_connector_return_role_coverage.py",
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
            "tests/test_ci_hosted_digital_peers.py",
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
            "tests/test_usb_peer_reference_coverage.py",
            "tests/test_usb_peer_reference_paths.py",
            "tests/test_usb_peer_reference_maps.py",
            "tests/test_usb_peer_reference_boundaries.py",
        }
    ),
    "interface_lint": frozenset(
        {
            "tests/test_control_inputs.py",
            "tests/test_external_protection_contract.py",
            "tests/test_external_protection_review.py",
            "tests/test_design_lint_i2c_parity.py",
            "tests/test_design_lint_mcp_parity_mapped_custom_passive.py",
            "tests/test_design_lint_determinism_interfaces.py",
            "tests/test_design_lint_serial_parity.py",
            "tests/test_design_lint_mcp_parity_i2c.py",
            "tests/test_design_lint_mcp_parity_peer_pins.py",
            "tests/test_design_lint_mcp_parity_serial.py",
            "tests/test_design_lint_mcp_parity_spi.py",
            "tests/test_design_lint_mcp_parity_stm32.py",
            "tests/test_design_lint_mcp_parity_usb_can.py",
            "tests/test_design_lint_mcp_parity_usb_data.py",
            "tests/test_can_native_fixture_lanes.py",
            "tests/test_digital_peer_spi_voltage_fixture_lane.py",
            "tests/test_digital_peer_serial_voltage_fixture_lane.py",
            "tests/test_digital_peer_serial_reference_fixture_lane.py",
            "tests/test_ci_hosted_digital_peers.py",
            "tests/test_digital_peer_voltages.py",
            "tests/test_i2c_address_coverage.py",
            "tests/test_i2c_address_collisions.py",
            "tests/test_i2c_address_straps.py",
            "tests/test_i2c_address_contract.py",
            "tests/test_i2c_pullup_heuristic_coverage.py",
            "tests/test_i2c_pullup_native_fixture_lane.py",
            "tests/test_i2c_pullup_tolerance.py",
            "tests/test_open_drain_bias_fixture_lane.py",
            "tests/test_open_drain_heuristics.py",
            "tests/test_serial_participants.py",
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
            "tests/test_usb_data_path_native_fixture_lane.py",
            "tests/test_hosted_usb_requirements.py",
            "tests/test_usb_peer_reference_coverage.py",
            "tests/test_usb_peer_reference_paths.py",
            "tests/test_usb_peer_reference_maps.py",
            "tests/test_usb_peer_reference_boundaries.py",
        }
    ),
    "power_lint": frozenset(
        {
            "tests/test_component_power_ratings.py",
            "tests/test_component_rating_native_fixture_lane.py",
            "tests/test_component_peer_power_fixture_lane.py",
            "tests/test_peer_power_assignment_symbol_groups.py",
            "tests/test_peer_power_assignment_part_id_groups.py",
            "tests/test_peer_power_assignment_cli_mcp.py",
            "tests/test_peer_power_assignment_native.py",
            "tests/test_ci_hosted_digital_peers.py",
            "tests/test_net_dc_reference_native_fixture_lane.py",
            "tests/test_design_lint_determinism_interfaces.py",
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
        }
    ),
    "pcb_lint": frozenset(
        {
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
            "tests/test_connector_return_distribution.py",
            "tests/test_connector_return_fixture_lane.py",
            "tests/test_ci_hosted_pcb_fixture_schedule.py",
            "tests/test_ci_hosted_digital_peers.py",
            "tests/test_native_connector_return_lint.py",
            "tests/test_design_lint_determinism_pcb_protection.py",
            "tests/test_pcb_decoupling_native_fixture_lane.py",
            "tests/test_pcb_decoupling_return_vias.py",
            "tests/test_pcb_protection_path_native_fixture_lane.py",
            "tests/test_design_lint_mcp_parity_connector_returns.py",
            "tests/test_design_lint_mcp_parity_serial.py",
            "tests/test_pcb_reference_plane_lint.py",
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
            "tests/test_serial_peer_reference_review.py",
            "tests/test_serial_peer_reference_coverage.py",
            "tests/test_serial_peer_reference_maps.py",
            "tests/test_serial_peer_reference_boundaries.py",
            "tests/test_serial_reference_bond_native_fixture_lane.py",
            "tests/test_usb_peer_reference_coverage.py",
            "tests/test_usb_peer_reference_paths.py",
            "tests/test_usb_peer_reference_maps.py",
            "tests/test_usb_peer_reference_boundaries.py",
        }
    ),
    "parity_lint": frozenset(
        {
            "tests/test_design_lint_i2c_parity.py",
            "tests/test_design_lint_serial_parity.py",
            "tests/test_electrical_parity.py",
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

_NATIVE_KICAD_MODULES = frozenset(
    {
        "tests/test_component_rating_native_fixture_lane.py",
        "tests/test_can_native_fixture_lanes.py",
        "tests/test_empty_netlist_evidence_native_fixture_lane.py",
        "tests/test_i2c_pullup_native_fixture_lane.py",
        "tests/test_native_connector_return_lint.py",
        "tests/test_pcb_access_native_fixture_lane.py",
        "tests/test_power_path_native_fixture_lane.py",
        "tests/test_pcb_keepouts_native.py",
        "tests/test_pcb_signal_path_native.py",
    }
)

_SLOW_MODULES = frozenset(
    {
        "tests/test_design_lint_determinism.py",
        "tests/test_electrical_parity.py",
        "tests/test_package_ci.py",
        "tests/test_can_native_fixture_lanes.py",
        "tests/test_empty_netlist_evidence_native_fixture_lane.py",
        "tests/test_i2c_pullup_native_fixture_lane.py",
        "tests/test_component_rating_native_fixture_lane.py",
        "tests/test_pcb_access_native_fixture_lane.py",
        "tests/test_power_path_native_fixture_lane.py",
    }
)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Tag lint and exact-native tests so pytest can select them by scope or cost."""
    for item in items:
        path = item.path.relative_to(_ROOT).as_posix()
        if path in _DESIGN_LINT_MODULES:
            item.add_marker(pytest.mark.design_lint)
        for marker, modules in _LINT_AREA_MODULES.items():
            if path in modules:
                item.add_marker(getattr(pytest.mark, marker))
        if path in _NATIVE_KICAD_MODULES:
            item.add_marker(pytest.mark.native_kicad)
        if path in _SLOW_MODULES:
            item.add_marker(pytest.mark.slow)
