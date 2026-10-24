"""Keep protocol lint implementations small and theme-owned."""

from __future__ import annotations

import pytest

from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.architecture,
]

BUS_ANALYSIS_MODULES = (
    "bus_signal_roles.py",
    "i3c_signal_named_rail.py",
    "i2c_unconnected_pins.py",
    "can_unconnected_direction_pins.py",
    "bus_signal_pairs.py",
    "can_line_polarity.py",
    "bus_ethernet_pair_labels.py",
    "rs485_data_label_mismatch.py",
    "can_tx_rx_label_mismatch.py",
    "can_tx_rx_same_net.py",
    "design_lint_rs485_candidates.py",
    "rs485_data_functions.py",
    "rs485_signal_named_rail.py",
    "rs485_same_net.py",
    "rs485_unconnected_data_pins.py",
    "design_lint_interfaces_usb_data_polarity.py",
    "usb_unconnected_data.py",
    "spi_unconnected_data_pins.py",
    "serial_unconnected_pins.py",
    "i2c_signal_label.py",
    "i2c_same_net.py",
    "serial_same_net.py",
    "serial_tx_rx_label_mismatch.py",
    "serial_signal_named_rail.py",
    "named_rail_pin_evidence.py",
    "serial_tx_output_sharing.py",
    "spi_data_label.py",
    "spi_clock_select_label_mismatch.py",
    "spi_signal_named_rail.py",
    "can_signal_named_rail.py",
    "bus_ethernet_signal_named_rail.py",
    "bus_ethernet_management_named_rail.py",
    "spi_same_net.py",
    "spi_clock_data_same_net.py",
    "spi_control_same_net.py",
    "spi_role_assignments.py",
    "spi_shared_chip_select.py",
    "spi_shared_data_outputs.py",
    "resistor_paths.py",
    "resistor_array_paths.py",
    "peer_reference_assignments.py",
    "i2c_pullup_contract_paths.py",
    "i2c_pullup_contract.py",
    "i2c_pullup_capacitance.py",
    "i2c_pullup_voltage_coverage.py",
    "i2c_pullup_heuristics.py",
    "can_termination_contract.py",
    "can_termination_heuristics.py",
    "can_peer_heuristics.py",
    "usb_c_vbus.py",
    "usb_c_contract.py",
    "spi_bias_heuristics.py",
    "spi_contract.py",
)


def test_bus_protocol_implementation_modules_stay_below_review_limit() -> None:
    modules = [HWREPO / name for name in BUS_ANALYSIS_MODULES]
    module_sizes = {path.name: line_count(path) for path in modules}
    oversized = {
        name: lines for name, lines in module_sizes.items() if lines >= IMPLEMENTATION_MAX_LINES
    }

    assert not oversized, (
        "Split bus-protocol modules at the 500-line review threshold; "
        f"oversized modules: {oversized}"
    )
