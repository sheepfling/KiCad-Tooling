"""Synthetic USB signal assignments for named-rail review."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def usb_signal_on_named_rail_netlist(
    *, function: str = "USB_DP", rail_name: str = "GND", pin: str = "U1.1"
) -> NetlistContract:
    """Assign one USB2 or SuperSpeed pin function to a rail-like label."""
    pin_functions = {"U1.1": "USB_DP", "U1.2": "USB_DM"}
    if pin not in pin_functions:
        raise ValueError(f"Unsupported synthetic USB pin: {pin}")

    signal_net_by_pin = {"U1.1": "USB_DP_NET", "U1.2": "USB_DM_NET"}
    nets = {
        signal_net: (member_pin,)
        for member_pin, signal_net in signal_net_by_pin.items()
        if member_pin != pin
    }
    nets[rail_name] = (pin,)
    pin_functions[pin] = function
    return NetlistContract(
        components={
            "U1": ComponentContract(value="Synthetic USB controller", footprint="Synthetic:QFN")
        },
        nets=nets,
        component_symbols={"U1": "Synthetic:USB_Controller"},
        pin_functions=pin_functions,
        component_pin_numbers={"U1": ("1", "2")},
    )
