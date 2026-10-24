"""Keep protocol lint tags connected to their exact-native fault/control cases."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint_catalog import rule_catalog

pytestmark = [pytest.mark.design_lint, pytest.mark.catalog_lint, pytest.mark.architecture]

_PROTOCOL_NATIVE_CASES = (
    pytest.param(
        "bus.i2c_peer_reference_review",
        "KICAD_RUN_NATIVE_I2C_PEER_REFERENCE_FIXTURES",
        "tests.test_i2c_peer_reference_native_fixture_lane."
        "test_native_i2c_peer_reference_fault_and_control_on_supported_images",
        id="i2c-peer-reference",
    ),
    pytest.param(
        "bus.spi_peer_reference_review",
        "KICAD_RUN_NATIVE_SPI_PEER_REFERENCE_FIXTURES",
        "tests.test_spi_peer_reference_native_fixture_lane."
        "test_native_spi_peer_reference_fault_and_control_on_supported_images",
        id="spi-peer-reference",
    ),
    pytest.param(
        "bus.can_peer_reference_review",
        "KICAD_RUN_NATIVE_CAN_PEER_REFERENCE_FIXTURES",
        "tests.test_can_native_fixture_lanes.test_native_can_peer_reference_fault_and_control",
        id="can-peer-reference",
    ),
    pytest.param(
        "bus.can_peer_assignment_divergence",
        "KICAD_RUN_NATIVE_CAN_PEER_FIXTURES",
        "tests.test_can_native_fixture_lanes.test_native_can_peer_assignment_fault_and_control",
        id="can-peer-assignment",
    ),
    pytest.param(
        "bus.can_excess_termination",
        "KICAD_RUN_NATIVE_CAN_TERMINATION_FIXTURES",
        "tests.test_can_native_fixture_lanes.test_native_can_excess_termination_fault_and_control",
        id="can-excess-termination",
    ),
    pytest.param(
        "bus.spi_clock_control_data_same_net",
        "KICAD_RUN_NATIVE_SPI_CLOCK_CONTROL_SAME_NET_FIXTURES",
        "tests.test_spi_clock_control_same_net_native_fixture_lane."
        "test_native_spi_clock_control_same_net_fault_and_control_repeat",
        id="spi-clock-control-same-net",
    ),
    pytest.param(
        "bus.i2c_unconnected_pin",
        "KICAD_RUN_NATIVE_I2C_UNCONNECTED_PIN_FIXTURES",
        "tests.test_i2c_unconnected_pins_native_fixture_lane."
        "test_native_open_i2c_pin_fault_and_connected_control",
        id="i2c-unconnected-pin",
    ),
    pytest.param(
        "bus.can_unconnected_direction_pin",
        "KICAD_RUN_NATIVE_CAN_UNCONNECTED_DIRECTION_PIN_FIXTURES",
        "tests.test_can_unconnected_direction_pins_native_fixture_lane."
        "test_native_open_can_direction_pin_fault_and_connected_control",
        id="can-unconnected-direction-pin",
    ),
    pytest.param(
        "bus.ethernet_data_label_mismatch",
        "KICAD_RUN_NATIVE_ETHERNET_DATA_LABEL_FIXTURES",
        "tests.test_ethernet_data_label_native_fixture_lane."
        "test_native_ethernet_label_fault_and_control_repeat",
        id="ethernet-data-label-mismatch",
    ),
    pytest.param(
        "bus.ethernet_management_label_mismatch",
        "KICAD_RUN_NATIVE_ETHERNET_MANAGEMENT_LABEL_FIXTURES",
        "tests.test_ethernet_management_label_native_fixture_lane."
        "test_native_ethernet_management_label_fault_and_control_repeat",
        id="ethernet-management-label-mismatch",
    ),
    pytest.param(
        "bus.spi_unconnected_data_pin",
        "KICAD_RUN_NATIVE_SPI_UNCONNECTED_DATA_FIXTURES",
        "tests.test_spi_unconnected_data_pins_native_fixture_lane."
        "test_native_open_spi_data_pin_fault_and_connected_control",
        id="spi-unconnected-data-pin",
    ),
    pytest.param(
        "bus.spi_clock_chip_select_same_net",
        "KICAD_RUN_NATIVE_SPI_CLOCK_CONTROL_SAME_NET_FIXTURES",
        "tests.test_spi_clock_control_same_net_native_fixture_lane."
        "test_native_spi_clock_control_same_net_fault_and_control_repeat",
        id="spi-clock-chip-select-same-net",
    ),
    pytest.param(
        "bus.can_tx_rx_same_net",
        "KICAD_RUN_NATIVE_CAN_TX_RX_SAME_NET_FIXTURES",
        "tests.test_can_tx_rx_same_net_native_fixture_lane."
        "test_native_can_tx_rx_same_net_fault_and_control_repeat",
        id="can-tx-rx-same-net",
    ),
    pytest.param(
        "bus.can_tx_outputs_share_net",
        "KICAD_RUN_NATIVE_CAN_TX_OUTPUT_SHARING_FIXTURES",
        "tests.test_can_tx_output_sharing_native_fixture_lane."
        "test_native_can_tx_output_sharing_fault_and_control_repeat",
        id="can-tx-output-sharing",
    ),
    pytest.param(
        "bus.can_tx_rx_label_mismatch",
        "KICAD_RUN_NATIVE_CAN_TX_RX_LABEL_MISMATCH_FIXTURES",
        "tests.test_can_tx_rx_label_mismatch_native_fixture_lane."
        "test_native_can_tx_rx_label_fault_and_control_repeat",
        id="can-tx-rx-label-mismatch",
    ),
    pytest.param(
        "bus.spi_clock_select_label_mismatch",
        "KICAD_RUN_NATIVE_SPI_CLOCK_SELECT_LABEL_FIXTURES",
        "tests.test_spi_clock_select_label_mismatch_native_fixture_lane."
        "test_native_spi_clock_select_label_fault_and_control_repeat",
        id="spi-clock-select-label-mismatch",
    ),
    pytest.param(
        "bus.spi_signal_on_named_rail",
        "KICAD_RUN_NATIVE_SPI_SIGNAL_NAMED_RAIL_FIXTURES",
        "tests.test_spi_signal_named_rail_native_fixture_lane."
        "test_native_spi_signal_named_rail_fault_and_control_repeat",
        id="spi-signal-named-rail",
    ),
    pytest.param(
        "bus.serial_signal_on_named_rail",
        "KICAD_RUN_NATIVE_SERIAL_TX_RX_LABEL_MISMATCH_FIXTURES",
        "tests.test_serial_tx_rx_label_mismatch_native_fixture_lane."
        "test_native_serial_tx_rx_label_fault_and_control_repeat",
        id="serial-signal-named-rail",
    ),
    pytest.param(
        "bus.serial_tx_rx_label_mismatch",
        "KICAD_RUN_NATIVE_SERIAL_TX_RX_LABEL_MISMATCH_FIXTURES",
        "tests.test_serial_tx_rx_label_mismatch_native_fixture_lane."
        "test_native_serial_tx_rx_label_fault_and_control_repeat",
        id="serial-tx-rx-label-mismatch",
    ),
    pytest.param(
        "bus.rs485_data_direction_label_mismatch",
        "KICAD_RUN_NATIVE_RS485_DATA_LABEL_MISMATCH_FIXTURES",
        "tests.test_rs485_data_direction_label_mismatch_native_fixture_lane."
        "test_native_rs485_data_direction_fault_and_control_repeat",
        id="rs485-data-direction-label-mismatch",
    ),
    pytest.param(
        "bus.rs485_data_input_output_same_net",
        "KICAD_RUN_NATIVE_RS485_DATA_SAME_NET_FIXTURES",
        "tests.test_rs485_data_input_output_same_net_native_fixture_lane."
        "test_native_rs485_same_net_fault_and_control_repeat",
        id="rs485-data-same-net",
    ),
    pytest.param(
        "bus.rs485_unconnected_data_pin",
        "KICAD_RUN_NATIVE_RS485_UNCONNECTED_DATA_PIN_FIXTURES",
        "tests.test_rs485_unconnected_data_pins_native_fixture_lane."
        "test_native_open_rs485_data_pin_fault_and_connected_control",
        id="rs485-unconnected-data-pin",
    ),
)


@pytest.mark.parametrize(("rule_id", "native_fixture", "native_test"), _PROTOCOL_NATIVE_CASES)
def test_protocol_rule_tags_select_native_fault_control_cases(
    rule_id: str, native_fixture: str, native_test: str
) -> None:
    rule = next(entry for entry in rule_catalog().rules if entry.rule_id == rule_id)

    assert native_fixture in rule.required_native_fixtures
    assert native_test in rule.fault_fixtures
    assert native_test in rule.valid_control_fixtures
