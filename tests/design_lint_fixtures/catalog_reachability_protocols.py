"""Protocol-specific synthetic cases for catalog reachability coverage."""

from __future__ import annotations

from kicad_tooling.hwrepo.design_lint import candidates
from kicad_tooling.hwrepo.rs485_peer_reference_scan import scan_rs485_peer_references
from kicad_tooling.hwrepo.serial_participants import SerialPeerRosterContext
from kicad_tooling.hwrepo.usb_c_ports import UsbCPortRosterContext
from tests.design_lint_fixtures.can_line_named_rail import can_line_named_rail_netlist
from tests.design_lint_fixtures.catalog_reachability import (
    usb_c_vbus_and_connector_return_review_rule_ids,
)
from tests.design_lint_fixtures.gpio_control_voltage import gpio_control_voltage_netlist
from tests.design_lint_fixtures.i3c_same_net import i3c_same_net_netlist
from tests.design_lint_fixtures.i3c_signal_named_rail import i3c_signal_named_rail_netlist
from tests.design_lint_fixtures.open_drain_control_voltage import open_drain_control_voltage_netlist
from tests.design_lint_fixtures.rs485_line_named_rail import rs485_line_named_rail_netlist
from tests.design_lint_fixtures.usb_c_cc_endpoint_pairing import usb_c_cc_endpoint_pairing_netlist
from tests.design_lint_fixtures.usb_c_cc_named_rail import usb_c_cc_named_rail_netlist
from tests.design_lint_fixtures.usb_c_cc_same_net import usb_c_cc_same_net_netlist
from tests.design_lint_fixtures.usb_c_sbu_named_rail import usb_c_sbu_named_rail_netlist
from tests.design_lint_fixtures.usb_c_sbu_same_net import (
    usb_c_cc_controller_same_net_netlist,
    usb_c_sbu_same_net_netlist,
)
from tests.design_lint_fixtures.usb_c_superspeed_lanes import usb_c_superspeed_lane_netlist
from tests.design_lint_fixtures.usb_data_pair_resistive_bridge import (
    usb_data_pair_bridge_netlist,
)
from tests.rs485_peer_reference_support import rs485_peer_reference_fixture
from tests.serial_participant_support import serial_netlist
from tests.test_open_drain_heuristics import signal_netlist
from tests.test_signal_divider_contract import _report as signal_divider_report
from tests.test_usb_c_ports import usb_c_netlist


def protocol_rule_ids() -> set[str]:
    """Return rules emitted by focused serial, USB, I3C, and control cases."""
    emitted = {
        item.rule_id
        for item in candidates(
            usb_c_netlist(),
            usb_c_port_roster=UsbCPortRosterContext(state="not_configured"),
        )
    }
    emitted.update(item.rule_id for item in candidates(signal_netlist()))
    emitted.update(item.rule_id for item in candidates(signal_netlist(output_type="open_emitter")))
    emitted.update(
        item.rule_id
        for item in candidates(
            serial_netlist(), serial_peer_roster=SerialPeerRosterContext(state="not_configured")
        )
    )
    _, rs485_context, rs485_source = rs485_peer_reference_fixture(
        reference_nets={"U1": "GND_A", "U2": "GND_B", "U3": "GND_A"}
    )
    rs485_scan = scan_rs485_peer_references(rs485_context, rs485_source)
    emitted.update(
        item.rule_id for item in candidates(rs485_source, rs485_peer_reference_scan=rs485_scan)
    )
    emitted.update(item.rule_id for item in candidates(rs485_line_named_rail_netlist()))
    emitted.update(item.rule_id for item in candidates(can_line_named_rail_netlist()))
    emitted.update(item.rule_id for item in candidates(usb_c_cc_named_rail_netlist()))
    emitted.update(usb_c_vbus_and_connector_return_review_rule_ids())
    emitted.update(item.rule_id for item in candidates(usb_c_cc_same_net_netlist()))
    emitted.update(
        item.rule_id for item in candidates(usb_c_superspeed_lane_netlist(swap_tx_lane_labels=True))
    )
    emitted.update(item.rule_id for item in candidates(usb_c_sbu_named_rail_netlist()))
    emitted.update(
        item.rule_id
        for item in candidates(usb_c_sbu_named_rail_netlist(sbu1_net=None, sbu2_net="SBU2_BUS"))
    )
    emitted.update(item.rule_id for item in candidates(usb_c_sbu_same_net_netlist()))
    emitted.update(item.rule_id for item in candidates(usb_c_cc_controller_same_net_netlist()))
    emitted.update(item.rule_id for item in candidates(usb_c_cc_endpoint_pairing_netlist()))
    emitted.update(item.rule_id for item in candidates(usb_data_pair_bridge_netlist()))
    emitted.update(item.rule_id for item in candidates(i3c_signal_named_rail_netlist()))
    i3c_source = i3c_same_net_netlist()
    emitted.update(item.rule_id for item in candidates(i3c_source))
    i3c_open_sda = i3c_source.model_copy(update={"nets": {"I3C_SCL": ("U1.2",)}})
    emitted.update(item.rule_id for item in candidates(i3c_open_sda))
    emitted.update(item.rule_id for item in candidates(gpio_control_voltage_netlist()))
    emitted.update(item.rule_id for item in candidates(open_drain_control_voltage_netlist()))
    emitted.update(
        item.rule_id for item in signal_divider_report(fault="top-resistor-value").findings
    )
    return emitted
