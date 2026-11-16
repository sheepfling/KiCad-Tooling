"""Synthetic USB netlist builders for multi-stage resistor-path checks."""

from __future__ import annotations

from kicad_tooling.hwrepo.netlist_contract_models import NetlistContract
from tests.usb_peer_reference_support import usb_peer_series_netlist


def two_stage_usb_series_netlist() -> NetlistContract:
    """Return a complete USB 2.0 endpoint pair with two passive resistors per line."""
    base = usb_peer_series_netlist()
    components = dict(base.components)
    components.update(
        {
            "R3": components["R1"].model_copy(update={"value": "33R"}),
            "R4": components["R2"].model_copy(update={"value": "33R"}),
        }
    )
    symbols = {**base.component_symbols, "R3": "Device:R", "R4": "Device:R"}
    pin_numbers = {**base.component_pin_numbers, "R3": ("1", "2"), "R4": ("1", "2")}
    nets = {
        **{
            name: pins
            for name, pins in base.nets.items()
            if name not in {"USB_DP_PHY", "USB_DM_PHY"}
        },
        "USB_DP": ("J1.1", "R1.1"),
        "USB_DP_MID": ("R1.2", "R3.1"),
        "USB_DP_PHY": ("R3.2", "U1.1"),
        "USB_DM": ("J1.2", "R2.1"),
        "USB_DM_MID": ("R2.2", "R4.1"),
        "USB_DM_PHY": ("R4.2", "U1.2"),
    }
    pin_types = {
        **base.pin_electrical_types,
        **{
            f"R{reference}.{number}": "passive" for reference in ("3", "4") for number in ("1", "2")
        },
    }
    pin_functions = {
        **base.pin_functions,
        **{f"R{reference}.{number}": "~" for reference in ("3", "4") for number in ("1", "2")},
    }
    return base.model_copy(
        update={
            "components": components,
            "component_symbols": symbols,
            "component_pin_numbers": pin_numbers,
            "nets": nets,
            "pin_electrical_types": pin_types,
            "pin_functions": pin_functions,
        }
    )
