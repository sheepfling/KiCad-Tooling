"""Synthetic protocol-peer cases for catalog reachability coverage."""

from __future__ import annotations

from kicad_tooling.hwrepo.design_lint import candidates
from tests.design_lint_fixtures import (
    can_netlist,
    complementary_usb_netlist,
    control_input_pins,
    i2c_netlist,
    i2c_netlist_with_parallel_sda,
    i2c_netlist_with_pullup_rails,
    serial_peer_voltage_netlist,
    spi_active_low_select_netlist,
    spi_peer_voltage_netlist,
    unconnected_protocol_pins,
)
from tests.design_lint_fixtures.can_rx_output_sharing import can_rx_output_netlist
from tests.design_lint_fixtures.can_signal_named_rail import can_signal_on_named_rail_netlist
from tests.design_lint_fixtures.can_tx_output_sharing import can_tx_output_netlist
from tests.design_lint_fixtures.can_tx_rx_same_net import can_tx_rx_same_net_netlist
from tests.design_lint_fixtures.connector_numeric_peer_open import (
    numeric_open_connector_part_id_aliases,
)
from tests.design_lint_fixtures.connector_reviewed_peer_distinct_signals_catalog import (
    reviewed_peer_distinct_signal_rule_ids,
)
from tests.design_lint_fixtures.connector_reviewed_peer_power_catalog import (
    reviewed_peer_power_rule_ids,
)
from tests.design_lint_fixtures.connector_reviewed_peer_signal_catalog import (
    reviewed_peer_signal_assignment_rule_ids,
)
from tests.design_lint_fixtures.connector_reviewed_peer_signal_domains_catalog import (
    reviewed_peer_signal_domain_rule_ids,
)
from tests.design_lint_fixtures.ethernet_signal_named_rail import (
    ethernet_signal_on_named_rail_netlist,
)
from tests.design_lint_fixtures.i2c_signal_label import i2c_signal_label_netlist
from tests.design_lint_fixtures.i2c_signal_named_rail import i2c_signal_on_named_rail_netlist
from tests.design_lint_fixtures.i2s_data_output_sharing import i2s_data_output_netlist
from tests.design_lint_fixtures.rs485_data_label_mismatch import rs485_data_label_netlist
from tests.design_lint_fixtures.rs485_data_same_net import rs485_data_same_net_netlist
from tests.design_lint_fixtures.rs485_line_label_mismatch import rs485_line_label_mismatch_netlist
from tests.design_lint_fixtures.rs485_signal_named_rail import rs485_signal_named_rail_netlist
from tests.design_lint_fixtures.serial_signal_named_rail import serial_signal_on_named_rail_netlist
from tests.design_lint_fixtures.serial_tx_rx_label_mismatch import serial_tx_rx_label_netlist
from tests.design_lint_fixtures.spi_clock_control_same_net import (
    spi_clock_chip_select_same_net_netlist,
    spi_clock_control_same_net_netlist,
)
from tests.design_lint_fixtures.spi_clock_select_label_mismatch import (
    spi_clock_select_label_netlist,
)
from tests.design_lint_fixtures.spi_data_label import spi_data_label_netlist
from tests.design_lint_fixtures.spi_data_same_net import spi_data_same_net_netlist
from tests.design_lint_fixtures.spi_shared_chip_select import spi_shared_chip_select_netlist
from tests.design_lint_fixtures.spi_shared_data_outputs import spi_shared_data_output_netlist
from tests.design_lint_fixtures.spi_signal_named_rail import spi_signal_on_named_rail_netlist
from tests.design_lint_fixtures.thermal_pad_catalog_reachability import thermal_pad_catalog_rule_ids
from tests.design_lint_fixtures.usb_data_pair_crossing import usb_data_pair_crossing_netlist
from tests.design_lint_fixtures.usb_signal_named_rail import usb_signal_on_named_rail_netlist
from tests.serial_participant_support import same_net_serial_netlist, serial_tx_output_netlist
from tests.test_component_same_voltage_power_input_domains import (
    same_voltage_power_input_split_rule_ids,
)
from tests.test_connector_footprint_same_voltage_power_input import (
    same_voltage_connector_power_input_rule_ids,
)
from tests.test_regulator_required_passives import catalog_reachable_rule_ids


def protocol_peer_candidate_rule_ids() -> set[str]:
    """Reach protocol and control-input candidate rules from synthetic netlists."""
    from tests.can_peer_reference_support import can_peer_reference_netlist
    from tests.design_lint_fixtures.can_generic_connector_pair import (
        can_connector_return_netlist,
        generic_can_connector_pair_netlist,
    )
    from tests.design_lint_fixtures.ethernet_generic_connector import (
        generic_ethernet_connector_netlist,
    )
    from tests.design_lint_fixtures.ethernet_management_generic_connector import (
        generic_ethernet_management_connector_netlist,
    )
    from tests.design_lint_fixtures.i2c_connector_return import two_pin_i2c_connector_netlist
    from tests.design_lint_fixtures.i2c_generic_connector_pair import (
        generic_i2c_connector_pair_netlist,
    )
    from tests.design_lint_fixtures.i3c_generic_connector_pair import (
        generic_i3c_connector_pair_netlist,
    )
    from tests.design_lint_fixtures.rs485_generic_connector_pair import (
        generic_rs485_connector_pair_netlist,
    )
    from tests.design_lint_fixtures.serial_connector_return import (
        two_pin_uart_connector_netlist,
    )
    from tests.design_lint_fixtures.serial_generic_connector_pair import (
        generic_serial_connector_pair_netlist,
    )
    from tests.design_lint_fixtures.spi_generic_connector_triad import (
        generic_spi_connector_triad_netlist,
    )
    from tests.design_lint_fixtures.swd_generic_connector_pair import (
        generic_swd_connector_netlist,
    )
    from tests.design_lint_fixtures.usb_c_generic_connector_cc_pair import (
        generic_usb_c_connector_cc_pair_netlist,
    )
    from tests.design_lint_fixtures.usb_generic_connector_pair import (
        generic_usb_connector_pair_netlist,
    )
    from tests.design_lint_fixtures.usb_superspeed_generic_connector import (
        generic_usb_superspeed_connector_pair_netlist,
    )
    from tests.i2c_peer_reference_support import i2c_peer_netlist
    from tests.serial_peer_reference_support import serial_reference_netlist
    from tests.spi_peer_reference_support import spi_peer_netlist
    from tests.test_spi_participants import spi_netlist
    from tests.usb_peer_reference_support import usb_peer_series_netlist

    cases = (
        control_input_pins(),
        control_input_pins(connected=True, visible_bias=False),
        unconnected_protocol_pins(),
        spi_netlist(),
        generic_spi_connector_triad_netlist(),
        spi_peer_voltage_netlist(),
        serial_peer_voltage_netlist(),
        generic_serial_connector_pair_netlist(),
        two_pin_uart_connector_netlist(),
        generic_rs485_connector_pair_netlist(),
        serial_reference_netlist(),
        can_netlist(),
        ethernet_signal_on_named_rail_netlist(),
        can_tx_rx_same_net_netlist(),
        can_signal_on_named_rail_netlist(),
        can_tx_rx_same_net_netlist(shared=False).model_copy(
            update={"nets": {"CAN1_RX": ("U1.1",), "CAN1_TX": ("U1.2",)}}
        ),
        can_tx_output_netlist(),
        can_rx_output_netlist(),
        i2s_data_output_netlist(),
        can_netlist("121R").model_copy(
            update={
                "nets": {
                    "CAN_HIGH": ("U1.2", "R1.1"),
                    "CAN_LOW": ("U1.1", "R1.2"),
                }
            }
        ),
        can_peer_reference_netlist(),
        generic_can_connector_pair_netlist(),
        can_connector_return_netlist(),
        generic_ethernet_connector_netlist(),
        generic_ethernet_management_connector_netlist(),
        generic_swd_connector_netlist(),
        generic_i2c_connector_pair_netlist(),
        generic_i3c_connector_pair_netlist(),
        two_pin_i2c_connector_netlist(),
        i2c_netlist(),
        i2c_netlist_with_parallel_sda(),
        i2c_netlist_with_pullup_rails(("+3V3", "+5V"), ("+3V3",)),
        i2c_signal_label_netlist(reversed_labels=True),
        i2c_signal_on_named_rail_netlist(),
        same_net_serial_netlist(),
        serial_tx_rx_label_netlist(),
        serial_signal_on_named_rail_netlist(),
        rs485_data_label_netlist(),
        rs485_line_label_mismatch_netlist(),
        rs485_data_same_net_netlist(),
        rs485_signal_named_rail_netlist(),
        serial_tx_output_netlist(),
        i2c_peer_netlist(),
        spi_peer_netlist(),
        spi_active_low_select_netlist(),
        spi_data_label_netlist(reversed_labels=True),
        spi_shared_chip_select_netlist(),
        spi_shared_data_output_netlist(),
        spi_data_same_net_netlist(),
        spi_clock_control_same_net_netlist(),
        spi_clock_chip_select_same_net_netlist(),
        spi_clock_select_label_netlist(),
        spi_signal_on_named_rail_netlist(),
        complementary_usb_netlist(negative_net=None),
        complementary_usb_netlist(),
        complementary_usb_netlist(positive_net="USB_DM", negative_net="USB_DP"),
        usb_signal_on_named_rail_netlist(),
        usb_data_pair_crossing_netlist(),
        generic_usb_connector_pair_netlist(),
        generic_usb_c_connector_cc_pair_netlist(),
        generic_usb_superspeed_connector_pair_netlist(),
        usb_peer_series_netlist(
            positive_resistor_value="22R",
            negative_resistor_value="33R",
        ),
    )
    return (
        {item.rule_id for source in cases for item in candidates(source)}
        | catalog_reachable_rule_ids()
        | {item.rule_id for item in candidates(numeric_open_connector_part_id_aliases())}
        | same_voltage_power_input_split_rule_ids()
        | same_voltage_connector_power_input_rule_ids()
        | reviewed_peer_power_rule_ids()
        | reviewed_peer_signal_assignment_rule_ids()
        | reviewed_peer_signal_domain_rule_ids()
        | reviewed_peer_distinct_signal_rule_ids()
        | thermal_pad_catalog_rule_ids()
    )
