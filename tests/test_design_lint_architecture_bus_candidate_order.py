"""Pin the stable order of protocol candidate dispatch."""

from __future__ import annotations

import ast

import pytest

from tests.lint_architecture_support import (
    FACADE_MAX_LINES,
    HWREPO,
    IMPLEMENTATION_MAX_LINES,
    line_count,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint, pytest.mark.architecture]


def test_bus_candidate_coordinator_delegates_by_theme_in_stable_order() -> None:
    coordinator = HWREPO / "design_lint_bus_candidates.py"
    modules = (
        "design_lint_i2c_candidates.py",
        "design_lint_i2c_bus_candidates.py",
        "design_lint_i2c_pullup_candidates.py",
        "design_lint_spi_candidates.py",
        "design_lint_spi_bus_candidates.py",
        "design_lint_spi_generic_connector_candidates.py",
        "design_lint_serial_bus_candidates.py",
        "design_lint_serial_generic_connector_candidates.py",
        "design_lint_unconnected_interface_candidates.py",
        "design_lint_can_candidates.py",
        "design_lint_rs485_candidates.py",
        "design_lint_signal_pair_candidates.py",
        "design_lint_interfaces_usb_data_polarity.py",
        "usb_data_pair_resistive_bridge.py",
        "design_lint_two_wire_signal_candidates.py",
        "design_lint_bus_named_rail_candidates.py",
        "design_lint_serial_signal_candidates.py",
        "design_lint_spi_signal_candidates.py",
        "design_lint_bus_named_rail_candidates.py",
        "jtag_data_same_net.py",
        "jtag_clock_mode_same_net.py",
        "jtag_signal_inventory.py",
    )

    assert line_count(coordinator) < IMPLEMENTATION_MAX_LINES
    assert all((HWREPO / name).is_file() for name in modules)
    grouped_candidates = tuple(
        HWREPO / name
        for name in (
            "design_lint_two_wire_signal_candidates.py",
            "design_lint_serial_signal_candidates.py",
            "design_lint_spi_signal_candidates.py",
        )
    )
    assert all(line_count(path) < FACADE_MAX_LINES for path in grouped_candidates)

    tree = ast.parse(coordinator.read_text(encoding="utf-8"), filename=coordinator.name)
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "bus_candidates"
    )
    calls = sorted(
        (node.lineno, node.func.id)
        for node in ast.walk(function)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    )
    candidate_constructions = [
        node
        for node in ast.walk(function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "Candidate"
    ]

    assert [name for _, name in calls] == [
        "i2c_protocol_bus_candidates",
        "i3c_protocol_bus_candidates",
        "i2s_clock_data_same_net_candidates",
        "i2s_data_output_sharing_candidates",
        "i2s_clock_frame_same_net_candidates",
        "two_wire_signal_candidates",
        "serial_protocol_bus_candidates",
        "spi_protocol_bus_candidates",
        "unconnected_interface_candidates",
        "can_candidates",
        "rs485_candidates",
        "ethernet_data_label_mismatch_candidates",
        "ethernet_management_label_mismatch_candidates",
        "ethernet_management_same_net_candidates",
        "ethernet_crs_dv_output_sharing_candidates",
        "ethernet_crs_output_sharing_candidates",
        "ethernet_rx_output_sharing_candidates",
        "ethernet_rx_clock_output_sharing_candidates",
        "ethernet_rx_status_output_sharing_candidates",
        "ethernet_tx_clock_output_sharing_candidates",
        "ethernet_mii_collision_output_sharing_candidates",
        "ethernet_unconnected_pin_candidates",
        "ethernet_generic_connector_pair_review_candidates",
        "ethernet_management_generic_connector_pair_review_candidates",
        "swd_generic_connector_pair_review_candidates",
        "swdio_swclk_same_net_candidates",
        "jtag_generic_connector_pair_review_candidates",
        "jtag_tdo_outputs_share_net_candidates",
        "jtag_tdi_tdo_same_net_candidates",
        "jtag_tck_tms_same_net_candidates",
        "bus_named_rail_candidates",
        "complementary_signal_candidates",
        "usb_data_polarity_label_candidates",
        "usb_c_superspeed_lane_label_mismatch_candidates",
        "usb_data_same_net_candidates",
        "usb_data_pair_resistive_bridge_candidates",
        "usb_c_same_net_candidates",
        "crossed_usb_c_cc_endpoint_candidates",
        "usb_c_sbu_same_net_candidates",
        "named_differential_pair_candidates",
        "i2c_address_theme_candidates",
    ]
    assert not candidate_constructions, "Bus dispatch should not construct lint findings."

    named_rail_tree = ast.parse(
        (HWREPO / "design_lint_bus_named_rail_candidates.py").read_text(encoding="utf-8")
    )
    named_rail_function = next(
        node
        for node in named_rail_tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "bus_named_rail_candidates"
    )
    named_rail_calls = sorted(
        (node.lineno, node.func.id)
        for node in ast.walk(named_rail_function)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    )
    assert [name for _, name in named_rail_calls] == [
        "ethernet_management_signal_on_named_rail_candidates",
        "ethernet_signal_on_named_rail_candidates",
        "usb_signal_on_named_rail_candidates",
        "usb_c_cc_signal_on_named_rail_candidates",
        "usb_c_sbu_signal_on_named_rail_candidates",
        "i2s_signal_on_named_rail_candidates",
        "jtag_signal_on_named_rail_candidates",
        "swd_signal_on_named_rail_candidates",
    ]
