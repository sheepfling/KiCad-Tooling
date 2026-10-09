"""Apply explicit pytest groups for focused design-lint and cost-aware runs."""

from __future__ import annotations

from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]

_DESIGN_LINT_MODULES = frozenset(
    {
        "tests/test_component_power_ratings.py",
        "tests/test_component_voltage_ratings.py",
        "tests/test_connector_contact_ratings.py",
        "tests/test_connector_coverage.py",
        "tests/test_connector_part_id_peers.py",
        "tests/test_connector_peer_pin_coverage.py",
        "tests/test_connector_peer_scope.py",
        "tests/test_connector_return_distribution.py",
        "tests/test_control_inputs.py",
        "tests/test_crystal_networks.py",
        "tests/test_design_lint.py",
        "tests/test_design_lint_catalog.py",
        "tests/test_design_lint_determinism.py",
        "tests/test_design_lint_i2c_parity.py",
        "tests/test_digital_peer_voltage_fixture_lane.py",
        "tests/test_digital_peer_voltages.py",
        "tests/test_electrical.py",
        "tests/test_electrical_parity.py",
        "tests/test_external_protection.py",
        "tests/test_i2c_addressing.py",
        "tests/test_i2c_pullup_heuristic_coverage.py",
        "tests/test_i2c_pullup_tolerance.py",
        "tests/test_led_output_heuristics.py",
        "tests/test_mcp_parity.py",
        "tests/test_native_connector_return_lint.py",
        "tests/test_open_drain_heuristics.py",
        "tests/test_pcb_decoupling.py",
        "tests/test_pcb_drc_coverage.py",
        "tests/test_pcb_keepouts.py",
        "tests/test_pcb_keepouts_native.py",
        "tests/test_pcb_protection_path.py",
        "tests/test_pcb_reference_plane_lint.py",
        "tests/test_pcb_reference_planes.py",
        "tests/test_pcb_return_paths.py",
        "tests/test_pcb_rf_antenna.py",
        "tests/test_pcb_rf_antenna_mcp_parity.py",
        "tests/test_pcb_signal_path_coverage.py",
        "tests/test_pcb_signal_path_native.py",
        "tests/test_pcb_switching_loops.py",
        "tests/test_pcb_track_width.py",
        "tests/test_peer_power_output.py",
        "tests/test_peer_power_pin_assignment.py",
        "tests/test_power_path_fixture_lane.py",
        "tests/test_power_paths.py",
        "tests/test_power_pin_paths.py",
        "tests/test_power_sequences.py",
        "tests/test_rc_filters.py",
        "tests/test_regulator_feedback.py",
        "tests/test_return_net_lint.py",
        "tests/test_serial_participants.py",
        "tests/test_serial_peer_reference_review.py",
        "tests/test_spi_participants.py",
        "tests/test_stm32_pin_map.py",
        "tests/test_two_pin_crystals.py",
        "tests/test_two_pin_diodes.py",
        "tests/test_two_pin_ferrites.py",
        "tests/test_two_pin_fuses.py",
        "tests/test_two_pin_passives.py",
        "tests/test_two_pin_switches.py",
        "tests/test_usb_c_ports.py",
        "tests/test_usb_data_paths.py",
        "tests/test_usb_peer_reference_review.py",
    }
)

_NATIVE_KICAD_MODULES = frozenset(
    {
        "tests/test_native_connector_return_lint.py",
        "tests/test_pcb_keepouts_native.py",
        "tests/test_pcb_signal_path_native.py",
    }
)

_SLOW_MODULES = frozenset(
    {
        "tests/test_design_lint_determinism.py",
        "tests/test_electrical_parity.py",
        "tests/test_mcp_parity.py",
        "tests/test_package_ci.py",
    }
)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Tag lint and exact-native tests so pytest can select them by scope or cost."""
    for item in items:
        path = item.path.relative_to(_ROOT).as_posix()
        native_class = "::Native" in item.nodeid
        if path in _DESIGN_LINT_MODULES or (path == "tests/test_ci_hosted.py" and native_class):
            item.add_marker(pytest.mark.design_lint)
        if path in _NATIVE_KICAD_MODULES or native_class:
            item.add_marker(pytest.mark.native_kicad)
        if path in _SLOW_MODULES or native_class:
            item.add_marker(pytest.mark.slow)
