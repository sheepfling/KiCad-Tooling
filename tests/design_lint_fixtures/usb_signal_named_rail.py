"""Synthetic USB signal assignments for named-rail review."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def usb_signal_on_named_rail_netlist(
    *, function: str = "USB_DP", rail_name: str = "GND", pin: str = "U1.1"
) -> NetlistContract:
    """Assign one IC or connector USB data function to a rail-like label."""
    reference, separator, number = pin.rpartition(".")
    if not separator or number not in {"1", "2"} or reference.upper() not in {"U1", "J1"}:
        raise ValueError(f"Unsupported synthetic USB pin: {pin}")

    first_pin = f"{reference}.1"
    second_pin = f"{reference}.2"
    pin_functions = {first_pin: "USB_DP", second_pin: "USB_DM"}
    signal_net_by_pin = {first_pin: "USB_DP_NET", second_pin: "USB_DM_NET"}
    nets = {signal_net_by_pin[other]: (other,) for other in signal_net_by_pin if other != pin}
    nets[rail_name] = (pin,)
    pin_functions[pin] = function
    is_connector = reference.upper().startswith("J")
    return NetlistContract(
        components={
            reference: ComponentContract(
                value="Synthetic USB connector" if is_connector else "Synthetic USB controller",
                footprint="Synthetic:USB-A" if is_connector else "Synthetic:QFN",
            )
        },
        nets=nets,
        component_symbols={
            reference: "Connector:USB_A" if is_connector else "Synthetic:USB_Controller"
        },
        pin_functions=pin_functions,
        component_pin_numbers={reference: ("1", "2")},
    )
