"""Synthetic USB data pairs with a series resistor on only one line."""

from __future__ import annotations

from typing import Literal

from kicad_tooling.hwrepo.netlist_contract_models import NetlistContract
from kicad_tooling.hwrepo.usb_data_path_models import (
    UsbDataPathLineRequirement,
    UsbDataPathMap,
)
from tests.usb_peer_reference_support import usb_peer_series_netlist, usb_series_data_map

UsbLine = Literal["D+", "D-"]


def asymmetric_series_netlist(
    series_line: UsbLine = "D+",
    *,
    dnp_resistor: bool = False,
) -> NetlistContract:
    """Return an exact direct/resistor pair with all native fields inventoried."""
    source = usb_peer_series_netlist()
    series_resistor_reference = "R1" if series_line == "D+" else "R2"
    direct_resistor_reference = "R2" if series_line == "D+" else "R1"
    direct_line = "D-" if series_line == "D+" else "D+"
    direct_endpoint_net = "USB_DM" if direct_line == "D-" else "USB_DP"
    phy_endpoint_net = "USB_DM_PHY" if direct_line == "D-" else "USB_DP_PHY"
    direct_pins = ("J1.2", "U1.2") if direct_line == "D-" else ("J1.1", "U1.1")
    components = dict(source.components)
    symbols = dict(source.component_symbols)
    pin_numbers = dict(source.component_pin_numbers)
    pin_types = dict(source.pin_electrical_types)
    pin_functions = dict(source.pin_functions)
    for mapping in (components, symbols, pin_numbers):
        mapping.pop(direct_resistor_reference)
    for mapping in (pin_types, pin_functions):
        for pin in (f"{direct_resistor_reference}.1", f"{direct_resistor_reference}.2"):
            mapping.pop(pin)
    nets = dict(source.nets)
    nets.pop(direct_endpoint_net)
    nets.pop(phy_endpoint_net)
    nets[direct_endpoint_net] = direct_pins
    dnp = tuple(source.dnp_components)
    if dnp_resistor:
        dnp = (*dnp, series_resistor_reference)
    return source.model_copy(
        update={
            "components": components,
            "component_symbols": symbols,
            "component_pin_numbers": pin_numbers,
            "pin_electrical_types": pin_types,
            "pin_functions": pin_functions,
            "nets": nets,
            "dnp_components": dnp,
        }
    )


def asymmetric_series_data_map(series_line: UsbLine = "D+") -> UsbDataPathMap:
    """Return a reviewed endpoint map that explicitly approves the asymmetry."""
    base = usb_series_data_map()
    interface = base.interfaces[0]
    direct = UsbDataPathLineRequirement(
        line="D-" if series_line == "D+" else "D+",
        connector_pin="J1.2" if series_line == "D+" else "J1.1",
        phy_pin="U1.2" if series_line == "D+" else "U1.1",
        connector_net="USB_DM" if series_line == "D+" else "USB_DP",
        phy_net="USB_DM" if series_line == "D+" else "USB_DP",
        topology="direct",
    )
    updated = interface.model_copy(
        update={"negative" if series_line == "D+" else "positive": direct}
    )
    return base.model_copy(update={"interfaces": (updated,)})
