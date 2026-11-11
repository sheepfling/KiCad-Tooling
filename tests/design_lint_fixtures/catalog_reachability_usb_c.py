"""Synthetic catalog reachability for the USB-C VBUS review rule."""

from __future__ import annotations

import tests.test_connector_return_signal_net as connector_return_signal_net
from kicad_tooling.hwrepo.design_lint import candidates
from tests.usb_c_vbus_capacitance_support import usb_c_vbus_netlist


def usb_c_vbus_and_connector_return_review_rule_ids() -> set[str]:
    """Reach the USB-C capacitor prompt and connector return review."""
    from kicad_tooling.hwrepo.usb_c_ports import UsbCPortRosterContext

    usb_c = candidates(
        usb_c_vbus_netlist(),
        usb_c_port_roster=UsbCPortRosterContext(state="not_configured"),
    )
    connector_return = connector_return_signal_net._report(
        connector_return_signal_net._source()
    ).findings
    return {item.rule_id for item in (*usb_c, *connector_return)}
