"""Synthetic candidates for protocol open-pin catalog reachability."""

from __future__ import annotations

from kicad_tooling.hwrepo.design_lint import candidates
from tests.design_lint_fixtures.can_unconnected_direction_pins import (
    can_unconnected_direction_netlist,
)
from tests.design_lint_fixtures.i2c_unconnected_pins import i2c_unconnected_netlist
from tests.design_lint_fixtures.rs485_ab_same_net import rs485_ab_same_net_netlist
from tests.design_lint_fixtures.rs485_unconnected_data_pins import (
    rs485_unconnected_data_netlist,
)
from tests.design_lint_fixtures.serial_unconnected_pins import serial_unconnected_netlist
from tests.design_lint_fixtures.spi_unconnected_clock_pin import (
    spi_unconnected_clock_netlist,
)
from tests.design_lint_fixtures.spi_unconnected_data_pins import (
    spi_unconnected_data_netlist,
)
from tests.design_lint_fixtures.usb_c_superspeed_lanes import (
    usb_c_superspeed_lane_fault_netlist,
)
from tests.design_lint_fixtures.usb_data_same_net import usb_data_same_net_netlist
from tests.design_lint_fixtures.usb_unconnected_data import usb_unconnected_data_netlist


def unconnected_protocol_candidate_rule_ids() -> set[str]:
    """Reach each selected open-pin review rule from bounded synthetic cases."""
    cases = (
        can_unconnected_direction_netlist(),
        i2c_unconnected_netlist(),
        rs485_ab_same_net_netlist(),
        rs485_unconnected_data_netlist(),
        serial_unconnected_netlist(),
        spi_unconnected_clock_netlist(open_pins=("U1.1",)),
        spi_unconnected_data_netlist(),
        usb_c_superspeed_lane_fault_netlist(),
        usb_data_same_net_netlist(),
        usb_unconnected_data_netlist(),
    )
    return {item.rule_id for source in cases for item in candidates(source)}
