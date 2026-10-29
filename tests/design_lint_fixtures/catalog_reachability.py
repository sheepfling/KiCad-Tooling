"""Synthetic cases for design-lint catalog reachability checks."""

from __future__ import annotations

from pathlib import Path

from kicad_tooling.hwrepo.connector_coverage import evaluate as evaluate_connector_coverage
from kicad_tooling.hwrepo.design_lint import candidates
from kicad_tooling.hwrepo.schematic_geometry import scan_wire_ends_on_pin_lines
from tests.connector_footprint_peer_support import (
    named_passive_contact_divergence_netlist,
    named_passive_contact_open_netlist,
    named_power_output_all_open_netlist,
    named_signal_all_open_netlist,
    named_signal_mode_dependent_open_netlist,
    peer_metadata_divergence_netlist,
)
from tests.design_lint_fixtures import (
    can_netlist,
    complementary_usb_netlist,
    control_input_pins,
    i2c_netlist,
    i2c_netlist_with_parallel_sda,
    i2c_netlist_with_pullup_rails,
    observed,
    schematic_geometry_fixtures,
    serial_peer_voltage_netlist,
    spi_active_low_select_netlist,
    spi_peer_voltage_netlist,
    unconnected_protocol_pins,
)
from tests.design_lint_fixtures.bjt_base_bias import bjt_base_bias_netlist
from tests.design_lint_fixtures.bjt_base_drive import bjt_base_drive_netlist
from tests.design_lint_fixtures.bjt_collector_emitter_same_net import (
    bjt_base_collector_netlist,
    bjt_base_emitter_netlist,
    bjt_collector_emitter_netlist,
)
from tests.design_lint_fixtures.bjt_terminal_order import bjt_terminal_order_netlist
from tests.design_lint_fixtures.can_signal_named_rail import can_signal_on_named_rail_netlist
from tests.design_lint_fixtures.can_tx_output_sharing import can_tx_output_netlist
from tests.design_lint_fixtures.can_tx_rx_same_net import can_tx_rx_same_net_netlist
from tests.design_lint_fixtures.connector_coverage import (
    connector_supply_role_catalog,
    connector_supply_role_netlist,
    connector_supply_role_reviews,
    inventory_review,
)
from tests.design_lint_fixtures.diode_rail_orientation import netlist as diode_rail_netlist
from tests.design_lint_fixtures.ethernet_data_labels import ethernet_data_label_netlist
from tests.design_lint_fixtures.ethernet_management_labels import ethernet_management_netlist
from tests.design_lint_fixtures.ethernet_signal_named_rail import (
    ethernet_signal_on_named_rail_netlist,
)
from tests.design_lint_fixtures.i2c_signal_label import i2c_signal_label_netlist
from tests.design_lint_fixtures.i2c_signal_named_rail import i2c_signal_on_named_rail_netlist
from tests.design_lint_fixtures.mosfet_drain_source_same_net import mosfet_drain_source_netlist
from tests.design_lint_fixtures.mosfet_gate_direct_drive import netlist as mosfet_gate_drive_netlist
from tests.design_lint_fixtures.mosfet_terminal_order import mosfet_terminal_order_netlist
from tests.design_lint_fixtures.polarized_capacitor import netlist as polarized_capacitor_netlist
from tests.design_lint_fixtures.rs485_data_label_mismatch import rs485_data_label_netlist
from tests.design_lint_fixtures.rs485_data_same_net import rs485_data_same_net_netlist
from tests.design_lint_fixtures.rs485_signal_named_rail import rs485_signal_named_rail_netlist
from tests.design_lint_fixtures.serial_endpoint_role_collision import (
    serial_endpoint_role_netlist,
)
from tests.design_lint_fixtures.serial_signal_named_rail import (
    serial_signal_on_named_rail_netlist,
)
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
from tests.design_lint_fixtures.usb_data_pair_crossing import usb_data_pair_crossing_netlist
from tests.design_lint_fixtures.usb_signal_named_rail import usb_signal_on_named_rail_netlist
from tests.serial_participant_support import (
    same_net_serial_netlist,
    serial_tx_output_netlist,
)
from tests.test_connector_mapped_interface_signal_unassigned import _coverage, _netlist
from tests.test_connector_stateful_contacts import _map as _stateful_contact_map
from tests.test_connector_stateful_contacts import _observed as _stateful_contact_netlist
from tests.test_oscillator_output_paths import (
    oscillator_output_netlist,
    oscillator_output_path_map,
)

TESTS = Path(__file__).resolve().parents[1]


def catalog_reachability_rule_ids() -> set[str]:
    cases = (
        (
            (TESTS / "fixtures/design_lint/near-miss-pin-line.kicad_sch").read_bytes(),
            "tests/fixtures/design_lint/near-miss-pin-line.kicad_sch",
            frozenset({"R1.1"}),
        ),
        (
            (TESTS / "fixtures/design_lint/pin-on-wire-middle-no-junction.kicad_sch").read_bytes(),
            "tests/fixtures/design_lint/pin-on-wire-middle-no-junction.kicad_sch",
            frozenset({"R1.1"}),
        ),
        (
            (TESTS / "fixtures/design_lint/wire-end-near-pin-tip.kicad_sch").read_bytes(),
            "tests/fixtures/design_lint/wire-end-near-pin-tip.kicad_sch",
            frozenset({"R1.1"}),
        ),
        (
            (TESTS / "fixtures/design_lint/label-near-wire-endpoint.kicad_sch").read_bytes(),
            "tests/fixtures/design_lint/label-near-wire-endpoint.kicad_sch",
            frozenset(),
        ),
        (
            (TESTS / "fixtures/design_lint/unmarked-orthogonal-crossing.kicad_sch").read_bytes(),
            "tests/fixtures/design_lint/unmarked-orthogonal-crossing.kicad_sch",
            frozenset(),
        ),
        (
            (TESTS / "fixtures/design_lint/t-junction/fault-no-junction.kicad_sch").read_bytes(),
            "tests/fixtures/design_lint/t-junction/fault-no-junction.kicad_sch",
            frozenset({"R1.2"}),
        ),
        (
            schematic_geometry_fixtures.free_text_anchor_fixture((25.4, 25.4), (25.4, 25.4)),
            "synthetic/free-text-anchor.kicad_sch",
            frozenset(),
        ),
        (
            schematic_geometry_fixtures.free_text_objects_fixture(
                "LONG_LABEL_ALPHA", (25.4, 25.4), "LONG_LABEL_BETA", (29.0, 25.4)
            ),
            "synthetic/free-text-overlap.kicad_sch",
            frozenset(),
        ),
        (
            schematic_geometry_fixtures.free_text_wire_fixture(
                "WIRE CROSSING FAULT", (88.9, 71.12)
            ),
            "synthetic/free-text-wire.kicad_sch",
            frozenset(),
        ),
        (
            schematic_geometry_fixtures.free_text_symbol_body_fixture(),
            "synthetic/free-text-symbol-body.kicad_sch",
            frozenset(),
        ),
        (
            schematic_geometry_fixtures.symbol_body_wire_fixture(),
            "synthetic/symbol-body-wire.kicad_sch",
            frozenset(),
        ),
    )
    result: set[str] = set()
    result.update(item.rule_id for item in candidates(serial_endpoint_role_netlist()))
    for source_bytes, source_path, unconnected_pins in cases:
        coverage = scan_wire_ends_on_pin_lines(
            source_bytes,
            source_path=source_path,
            kicad_version="10.0.6",
            unconnected_pins=unconnected_pins,
        )
        result.update(item.rule_id for item in candidates(observed(), schematic_geometry=coverage))
    result.update(
        item.rule_id
        for item in candidates(
            oscillator_output_netlist(resistor_value="1k"),
            oscillator_output_path_map=oscillator_output_path_map(),
        )
    )
    for source in (
        named_signal_all_open_netlist(),
        named_power_output_all_open_netlist(),
        named_signal_mode_dependent_open_netlist(),
        named_passive_contact_open_netlist(),
        named_passive_contact_divergence_netlist(),
    ):
        result.update(item.rule_id for item in candidates(source))
    result.update(item.rule_id for item in candidates(peer_metadata_divergence_netlist()))
    result.update(
        item.rule_id
        for item in candidates(
            peer_metadata_divergence_netlist(target_assignments=("UART_RX_NET", None))
        )
    )
    result.update(item.rule_id for item in candidates(polarized_capacitor_netlist()))
    result.update(item.rule_id for item in candidates(diode_rail_netlist()))
    result.update(item.rule_id for item in candidates(mosfet_terminal_order_netlist()))
    result.update(item.rule_id for item in candidates(bjt_terminal_order_netlist()))
    result.update(item.rule_id for item in candidates(bjt_collector_emitter_netlist()))
    result.update(item.rule_id for item in candidates(bjt_base_emitter_netlist()))
    result.update(item.rule_id for item in candidates(bjt_base_collector_netlist()))
    result.update(item.rule_id for item in candidates(bjt_base_drive_netlist()))
    result.update(item.rule_id for item in candidates(bjt_base_bias_netlist()))
    supply_domain_netlist = connector_supply_role_netlist(common_supply=True)
    supply_domain_catalog = connector_supply_role_catalog(serial_voltage_domain="serial-vbus")
    supply_domain_coverage = evaluate_connector_coverage(
        supply_domain_netlist,
        tuple(sorted(supply_domain_catalog)),
        connector_supply_role_reviews(),
        interfaces=supply_domain_catalog,
        interface_catalog_path="catalog/interfaces.json",
        interface_catalog_sha256="d" * 64,
        inventory_review=inventory_review(),
    )
    result.update(
        item.rule_id
        for item in candidates(
            supply_domain_netlist,
            connector_coverage=supply_domain_coverage,
        )
    )
    result.update(item.rule_id for item in candidates(mosfet_gate_drive_netlist()))
    result.update(item.rule_id for item in candidates(mosfet_drain_source_netlist()))
    result.update(
        item.rule_id
        for item in candidates(
            _stateful_contact_netlist(tip_pair_same_net=True),
            connector_stateful_contact_map=_stateful_contact_map(),
        )
    )
    mapped_signal_source = _netlist()
    mapped_signal_coverage = _coverage(mapped_signal_source)
    result.update(
        item.rule_id
        for item in candidates(mapped_signal_source, connector_coverage=mapped_signal_coverage)
    )
    mapped_shield_source = _netlist()
    result.update(
        item.rule_id
        for item in candidates(
            mapped_shield_source,
            connector_coverage=_coverage(mapped_shield_source, target_role="shield"),
        )
    )
    mapped_power_source = _netlist()
    result.update(
        item.rule_id
        for item in candidates(
            mapped_power_source,
            connector_coverage=_coverage(mapped_power_source, target_role="return"),
        )
    )
    result.update(
        item.rule_id
        for item in candidates(
            ethernet_data_label_netlist(
                functions=("TDP", "TDN", "RDP", "RDN"),
                labels=("ETH_RX_P", "ETH_RX_N", "ETH_TX_P", "ETH_TX_N"),
            )
        )
    )
    result.update(item.rule_id for item in candidates(ethernet_management_netlist()))
    result.update(
        item.rule_id for item in candidates(ethernet_management_netlist(open_functions=("MDC",)))
    )
    result.update(
        item.rule_id for item in candidates(ethernet_management_netlist(labels=("GND", "ETH_MDIO")))
    )
    result.update(
        item.rule_id
        for item in candidates(ethernet_management_netlist(labels=("ETH_MDIO", "ETH_MDC")))
    )
    return result


def protocol_peer_candidate_rule_ids() -> set[str]:
    """Reach protocol and control-input candidate rules from synthetic netlists."""
    from tests.can_peer_reference_support import can_peer_reference_netlist
    from tests.i2c_peer_reference_support import i2c_peer_netlist
    from tests.serial_peer_reference_support import serial_reference_netlist
    from tests.spi_peer_reference_support import spi_peer_netlist
    from tests.test_spi_participants import spi_netlist

    cases = (
        control_input_pins(),
        control_input_pins(connected=True, visible_bias=False),
        unconnected_protocol_pins(),
        spi_netlist(),
        spi_peer_voltage_netlist(),
        serial_peer_voltage_netlist(),
        serial_reference_netlist(),
        can_netlist(),
        ethernet_signal_on_named_rail_netlist(),
        can_tx_rx_same_net_netlist(),
        can_signal_on_named_rail_netlist(),
        can_tx_rx_same_net_netlist(shared=False).model_copy(
            update={"nets": {"CAN1_RX": ("U1.1",), "CAN1_TX": ("U1.2",)}}
        ),
        can_tx_output_netlist(),
        can_netlist("121R").model_copy(
            update={
                "nets": {
                    "CAN_HIGH": ("U1.2", "R1.1"),
                    "CAN_LOW": ("U1.1", "R1.2"),
                }
            }
        ),
        can_peer_reference_netlist(),
        i2c_netlist(),
        i2c_netlist_with_parallel_sda(),
        i2c_netlist_with_pullup_rails(("+3V3", "+5V"), ("+3V3",)),
        i2c_signal_label_netlist(reversed_labels=True),
        i2c_signal_on_named_rail_netlist(),
        same_net_serial_netlist(),
        serial_tx_rx_label_netlist(),
        serial_signal_on_named_rail_netlist(),
        rs485_data_label_netlist(),
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
    )
    return {item.rule_id for source in cases for item in candidates(source)}
