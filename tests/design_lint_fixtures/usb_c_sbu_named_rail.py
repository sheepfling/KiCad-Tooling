"""Synthetic USB-C SBU assignments for named-rail review."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def usb_c_sbu_named_rail_netlist(
    *,
    reference: str = "U1",
    sbu1_net: str | None = "GND",
    sbu2_net: str | None = "+3V3",
    sbu1_function: str = "SBU1",
    sbu2_function: str = "SBU2",
    dnp: bool = False,
) -> NetlistContract:
    """Build a fitted synthetic endpoint or one explicit boundary case."""
    is_connector = reference.casefold().startswith("j")
    pin1, pin2 = f"{reference}.1", f"{reference}.2"
    return NetlistContract(
        components={
            reference: ComponentContract(
                value=(
                    "Synthetic USB-C receptacle" if is_connector else "Synthetic USB-C controller"
                ),
                footprint="Synthetic:CONN_01X02" if is_connector else "Synthetic:QFN",
            )
        },
        nets={net: (pin,) for net, pin in ((sbu1_net, pin1), (sbu2_net, pin2)) if net is not None},
        component_symbols={
            reference: "Connector:Conn_01x02" if is_connector else "Synthetic:USB_C_Controller"
        },
        pin_functions={pin1: sbu1_function, pin2: sbu2_function},
        component_pin_numbers={reference: ("1", "2")},
        dnp_components=(reference,) if dnp else (),
    )
