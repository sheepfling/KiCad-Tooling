"""Synthetic SBU-controller assignments for named-rail review."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def usb_c_sbu_named_rail_netlist(
    *,
    sbu1_net: str | None = "GND",
    sbu2_net: str | None = "+3V3",
    sbu1_function: str = "SBU1",
    sbu2_function: str = "SBU2",
    dnp: bool = False,
) -> NetlistContract:
    """Build a fitted synthetic SBU controller or one explicit boundary case."""
    return NetlistContract(
        components={
            "U1": ComponentContract(value="Synthetic USB-C controller", footprint="Synthetic:QFN")
        },
        nets={
            net: (pin,) for net, pin in ((sbu1_net, "U1.1"), (sbu2_net, "U1.2")) if net is not None
        },
        component_symbols={"U1": "Synthetic:USB_C_Controller"},
        pin_functions={"U1.1": sbu1_function, "U1.2": sbu2_function},
        component_pin_numbers={"U1": ("1", "2")},
        dnp_components=("U1",) if dnp else (),
    )
