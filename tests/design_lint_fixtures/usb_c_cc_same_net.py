"""Synthetic connector assignments for USB-C CC1/CC2 same-net review."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def usb_c_cc_same_net_netlist(
    *,
    shared: bool = True,
    cc1_function: str = "CC1",
    cc2_function: str = "CC2",
    dnp: bool = False,
    reference: str = "J1",
    symbol: str = "Connector:USB_C_Port",
    inventory: tuple[str, ...] = ("1", "2"),
) -> NetlistContract:
    """Return a fitted connector with either shared or separate CC nets."""
    first_pin = f"{reference}.1"
    second_pin = f"{reference}.2"
    if shared:
        nets = {"CC_SHARED": (first_pin, second_pin)}
    else:
        nets = {"CC1_BUS": (first_pin,), "CC2_BUS": (second_pin,)}
    return NetlistContract(
        components={
            reference: ComponentContract(
                value="Synthetic USB-C receptacle", footprint="Synthetic:USB_C"
            )
        },
        nets=nets,
        component_symbols={reference: symbol},
        pin_functions={first_pin: cc1_function, second_pin: cc2_function},
        component_pin_numbers={reference: inventory},
        dnp_components=(reference,) if dnp else (),
    )
