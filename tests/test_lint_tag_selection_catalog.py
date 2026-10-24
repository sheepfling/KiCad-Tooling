"""Keep rule-scoped prerelease tags tied to native fixture declarations."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.lint_gate_scope import (
    active_design_lint_rule_ids,
    configured_native_fixtures,
    parse_tag_message,
    required_native_fixtures_by_rule,
)


@pytest.mark.parametrize(
    ("rule_id", "native_fixture"),
    (
        ("power.mapped_sequence_dependency_mismatch", "KICAD_RUN_NATIVE_POWER_SEQUENCE_FIXTURES"),
        (
            "component.two_pin_led_same_net",
            "KICAD_RUN_NATIVE_TWO_PIN_COMPONENT_FIXTURES",
        ),
        (
            "component.two_pin_buzzer_same_net",
            "KICAD_RUN_NATIVE_TWO_PIN_COMPONENT_FIXTURES",
        ),
        (
            "component.two_pin_speaker_same_net",
            "KICAD_RUN_NATIVE_TWO_PIN_COMPONENT_FIXTURES",
        ),
        (
            "component.two_pin_battery_same_net",
            "KICAD_RUN_NATIVE_TWO_PIN_COMPONENT_FIXTURES",
        ),
        (
            "component.two_pin_motor_same_net",
            "KICAD_RUN_NATIVE_TWO_PIN_COMPONENT_FIXTURES",
        ),
        (
            "component.two_pin_solar_cell_same_net",
            "KICAD_RUN_NATIVE_TWO_PIN_COMPONENT_FIXTURES",
        ),
        (
            "component.two_pin_thermocouple_same_net",
            "KICAD_RUN_NATIVE_TWO_PIN_COMPONENT_FIXTURES",
        ),
        (
            "component.transformer_winding_same_net",
            "KICAD_RUN_NATIVE_TRANSFORMER_WINDING_FIXTURES",
        ),
        (
            "component.transformer_winding_groups_share_net",
            "KICAD_RUN_NATIVE_TRANSFORMER_WINDING_FIXTURES",
        ),
        ("component.generic_peer_pin_mixed_open", "KICAD_RUN_NATIVE_COMPONENT_PEER_PIN_FIXTURES"),
        (
            "component.repeated_signal_pin_assignment_divergence",
            "KICAD_RUN_NATIVE_COMPONENT_REPEATED_SIGNAL_PIN_FIXTURES",
        ),
        (
            "component.repeated_signal_pin_unassigned",
            "KICAD_RUN_NATIVE_COMPONENT_REPEATED_SIGNAL_PIN_UNASSIGNED_FIXTURES",
        ),
        ("component.peer_signal_input_unconnected", "KICAD_RUN_NATIVE_COMPONENT_PEER_PIN_FIXTURES"),
        (
            "component.peer_signal_output_unconnected",
            "KICAD_RUN_NATIVE_COMPONENT_PEER_PIN_FIXTURES",
        ),
        ("connector.repeated_pin_function", "KICAD_RUN_NATIVE_DB9_RETURN_CONTRACT_FIXTURES"),
        (
            "connector.repeated_pin_function",
            "KICAD_RUN_NATIVE_MIXED_INTERFACE_RETURN_FIXTURES",
        ),
        ("component.peer_power_output_unconnected", "KICAD_RUN_NATIVE_COMPONENT_PEER_PIN_FIXTURES"),
        (
            "component.peer_bidirectional_pin_unconnected",
            "KICAD_RUN_NATIVE_COMPONENT_PEER_PIN_FIXTURES",
        ),
        ("bus.i2c_missing_pullup", "KICAD_RUN_NATIVE_I2C_PULLUP_FIXTURES"),
        (
            "bus.usb_data_polarity_label_mismatch",
            "KICAD_RUN_NATIVE_USB_DATA_POLARITY_FIXTURES",
        ),
        (
            "bus.usb_signal_on_named_rail",
            "KICAD_RUN_NATIVE_USB_SIGNAL_NAMED_RAIL_FIXTURES",
        ),
        (
            "bus.usb_peer_data_pair_crossed",
            "KICAD_RUN_NATIVE_USB_DATA_POLARITY_FIXTURES",
        ),
        (
            "bus.usb_unconnected_data_pin",
            "KICAD_RUN_NATIVE_USB_DATA_POLARITY_FIXTURES",
        ),
        (
            "bus.i2c_unconnected_pin",
            "KICAD_RUN_NATIVE_I2C_UNCONNECTED_PIN_FIXTURES",
        ),
        (
            "bus.serial_unconnected_pin",
            "KICAD_RUN_NATIVE_SERIAL_UNCONNECTED_PIN_FIXTURES",
        ),
        (
            "bus.can_unconnected_direction_pin",
            "KICAD_RUN_NATIVE_CAN_UNCONNECTED_DIRECTION_PIN_FIXTURES",
        ),
        (
            "bus.spi_unconnected_data_pin",
            "KICAD_RUN_NATIVE_SPI_UNCONNECTED_DATA_FIXTURES",
        ),
        (
            "bus.spi_unmapped_participant",
            "KICAD_RUN_NATIVE_DIGITAL_PEER_FIXTURES",
        ),
        (
            "bus.can_line_polarity_label_mismatch",
            "KICAD_RUN_NATIVE_CAN_LINE_POLARITY_FIXTURES",
        ),
        (
            "bus.ethernet_data_label_mismatch",
            "KICAD_RUN_NATIVE_ETHERNET_DATA_LABEL_FIXTURES",
        ),
        (
            "bus.ethernet_signal_on_named_rail",
            "KICAD_RUN_NATIVE_ETHERNET_SIGNAL_NAMED_RAIL_FIXTURES",
        ),
        (
            "bus.ethernet_management_signal_on_named_rail",
            "KICAD_RUN_NATIVE_ETHERNET_MANAGEMENT_NAMED_RAIL_FIXTURES",
        ),
        (
            "bus.ethernet_management_label_mismatch",
            "KICAD_RUN_NATIVE_ETHERNET_MANAGEMENT_LABEL_FIXTURES",
        ),
        (
            "bus.i2c_signal_label_role_mismatch",
            "KICAD_RUN_NATIVE_I2C_SIGNAL_LABEL_FIXTURES",
        ),
        (
            "bus.i2c_sda_scl_same_net",
            "KICAD_RUN_NATIVE_I2C_SDA_SCL_SAME_NET_FIXTURES",
        ),
        (
            "bus.serial_tx_rx_same_net",
            "KICAD_RUN_NATIVE_SERIAL_TX_RX_SAME_NET_FIXTURES",
        ),
        (
            "bus.serial_signal_on_named_rail",
            "KICAD_RUN_NATIVE_SERIAL_TX_RX_LABEL_MISMATCH_FIXTURES",
        ),
        (
            "bus.serial_tx_rx_label_mismatch",
            "KICAD_RUN_NATIVE_SERIAL_TX_RX_LABEL_MISMATCH_FIXTURES",
        ),
        (
            "bus.rs485_data_direction_label_mismatch",
            "KICAD_RUN_NATIVE_RS485_DATA_LABEL_MISMATCH_FIXTURES",
        ),
        (
            "bus.rs485_data_input_output_same_net",
            "KICAD_RUN_NATIVE_RS485_DATA_SAME_NET_FIXTURES",
        ),
        (
            "bus.rs485_signal_on_named_rail",
            "KICAD_RUN_NATIVE_RS485_SIGNAL_NAMED_RAIL_FIXTURES",
        ),
        (
            "bus.rs485_unconnected_data_pin",
            "KICAD_RUN_NATIVE_RS485_UNCONNECTED_DATA_PIN_FIXTURES",
        ),
        (
            "bus.serial_tx_outputs_share_net",
            "KICAD_RUN_NATIVE_SERIAL_TX_OUTPUT_SHARING_FIXTURES",
        ),
        (
            "bus.spi_data_polarity_label_mismatch",
            "KICAD_RUN_NATIVE_SPI_DATA_POLARITY_FIXTURES",
        ),
        (
            "bus.spi_clock_select_label_mismatch",
            "KICAD_RUN_NATIVE_SPI_CLOCK_SELECT_LABEL_FIXTURES",
        ),
        (
            "bus.spi_signal_on_named_rail",
            "KICAD_RUN_NATIVE_SPI_SIGNAL_NAMED_RAIL_FIXTURES",
        ),
        (
            "bus.can_signal_on_named_rail",
            "KICAD_RUN_NATIVE_CAN_SIGNAL_NAMED_RAIL_FIXTURES",
        ),
        (
            "bus.spi_chip_select_inputs_share_net",
            "KICAD_RUN_NATIVE_SPI_SHARED_CHIP_SELECT_FIXTURES",
        ),
        (
            "bus.spi_data_outputs_share_net",
            "KICAD_RUN_NATIVE_SPI_SHARED_DATA_OUTPUT_FIXTURES",
        ),
        (
            "bus.spi_data_input_output_same_net",
            "KICAD_RUN_NATIVE_SPI_DATA_SAME_NET_FIXTURES",
        ),
        (
            "bus.spi_clock_control_data_same_net",
            "KICAD_RUN_NATIVE_SPI_CLOCK_CONTROL_SAME_NET_FIXTURES",
        ),
        (
            "bus.spi_clock_chip_select_same_net",
            "KICAD_RUN_NATIVE_SPI_CLOCK_CONTROL_SAME_NET_FIXTURES",
        ),
        (
            "bus.can_tx_rx_same_net",
            "KICAD_RUN_NATIVE_CAN_TX_RX_SAME_NET_FIXTURES",
        ),
        (
            "bus.can_tx_outputs_share_net",
            "KICAD_RUN_NATIVE_CAN_TX_OUTPUT_SHARING_FIXTURES",
        ),
        (
            "bus.can_tx_rx_label_mismatch",
            "KICAD_RUN_NATIVE_CAN_TX_RX_LABEL_MISMATCH_FIXTURES",
        ),
        (
            "bus.complementary_pair_assignment",
            "KICAD_RUN_NATIVE_COMPLEMENTARY_PAIR_FIXTURES",
        ),
        (
            "power.ic_decoupling_below_project_minimum",
            "KICAD_RUN_NATIVE_IC_RAIL_CAPACITOR_FIXTURES",
        ),
        (
            "component.diode_anode_below_cathode_on_named_rails",
            "KICAD_RUN_NATIVE_COMPONENT_RATING_FIXTURES",
        ),
        (
            "component.mosfet_terminal_order_on_named_rails",
            "KICAD_RUN_NATIVE_COMPONENT_RATING_FIXTURES",
        ),
        ("component.mosfet_gate_direct_drive", "KICAD_RUN_NATIVE_COMPONENT_RATING_FIXTURES"),
        (
            "component.mosfet_drain_source_same_net",
            "KICAD_RUN_NATIVE_COMPONENT_RATING_FIXTURES",
        ),
        (
            "component.mosfet_gate_source_same_net",
            "KICAD_RUN_NATIVE_COMPONENT_RATING_FIXTURES",
        ),
        (
            "component.mosfet_gate_drain_same_net",
            "KICAD_RUN_NATIVE_COMPONENT_RATING_FIXTURES",
        ),
        (
            "component.bjt_terminal_order_on_named_rails",
            "KICAD_RUN_NATIVE_COMPONENT_TERMINAL_ORDER_FIXTURES",
        ),
        (
            "component.bjt_collector_emitter_same_net",
            "KICAD_RUN_NATIVE_COMPONENT_TERMINAL_ORDER_FIXTURES",
        ),
        (
            "component.bjt_base_emitter_same_net",
            "KICAD_RUN_NATIVE_COMPONENT_TERMINAL_ORDER_FIXTURES",
        ),
        (
            "component.bjt_base_collector_same_net",
            "KICAD_RUN_NATIVE_COMPONENT_TERMINAL_ORDER_FIXTURES",
        ),
        ("component.bjt_base_direct_drive", "KICAD_RUN_NATIVE_COMPONENT_BASE_DRIVE_FIXTURES"),
        (
            "component.bjt_base_without_visible_emitter_bias",
            "KICAD_RUN_NATIVE_COMPONENT_BASE_DRIVE_FIXTURES",
        ),
        ("power.regulator_feedback_mismatch", "KICAD_RUN_NATIVE_REGULATOR_FEEDBACK_FIXTURES"),
    ),
)
def test_lint_tag_selects_rule_and_all_its_configured_native_fixtures(
    rule_id: str,
    native_fixture: str,
) -> None:
    repository = Path(__file__).resolve().parents[1]
    fixtures = configured_native_fixtures(repository)
    rule_ids = active_design_lint_rule_ids()
    required_by_rule = required_native_fixtures_by_rule()
    assert rule_id in rule_ids
    assert native_fixture in fixtures
    required_fixtures = required_by_rule[rule_id]
    assert native_fixture in required_fixtures
    assert set(required_fixtures) <= fixtures
    native_fixture_lines = "".join(f"Native-Fixture: {item}\n" for item in required_fixtures)

    scope = parse_tag_message(
        f"Focused deterministic lint gate\n\nLint-Rule: {rule_id}\n{native_fixture_lines}",
        fixtures,
        rule_ids,
        required_by_rule,
    )

    assert scope.area is None
    assert scope.rule_id == rule_id
    assert scope.pytest_markexpr == (
        f'design_lint and (design_lint_rule(rule_id="{rule_id}") or rule_gate_integrity)'
    )
    assert scope.native_fixtures == required_fixtures
