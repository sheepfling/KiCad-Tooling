"""Synthetic CC-controller assignments for named-rail review."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def usb_c_cc_named_rail_netlist(
    *,
    cc1_net: str = "GND",
    cc2_net: str = "+3V3",
    cc1_function: str = "CC1",
    cc2_function: str = "CC2",
    reference: str = "U1",
    dnp: bool = False,
) -> NetlistContract:
    """Build a fitted synthetic CC controller or one explicit boundary case."""
    is_connector = reference.upper().startswith("J")
    return NetlistContract(
        components={
            reference: ComponentContract(
                value="Synthetic USB-C connector" if is_connector else "Synthetic USB-C controller",
                footprint="Synthetic:USB-C" if is_connector else "Synthetic:QFN",
            )
        },
        nets={cc1_net: (f"{reference}.1",), cc2_net: (f"{reference}.2",)},
        component_symbols={
            reference: "Connector:USB_C_Receptacle"
            if is_connector
            else "Synthetic:USB_C_Controller"
        },
        pin_functions={f"{reference}.1": cc1_function, f"{reference}.2": cc2_function},
        component_pin_numbers={reference: ("1", "2")},
        dnp_components=(reference,) if dnp else (),
    )
