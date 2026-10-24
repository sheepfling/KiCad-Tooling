"""Synthetic CC-controller assignments for named-rail review."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def usb_c_cc_named_rail_netlist(
    *,
    cc1_net: str = "GND",
    cc2_net: str = "+3V3",
    cc1_function: str = "CC1",
    cc2_function: str = "CC2",
    dnp: bool = False,
) -> NetlistContract:
    """Build a fitted synthetic CC controller or one explicit boundary case."""
    return NetlistContract(
        components={
            "U1": ComponentContract(value="Synthetic USB-C controller", footprint="Synthetic:QFN")
        },
        nets={cc1_net: ("U1.1",), cc2_net: ("U1.2",)},
        component_symbols={"U1": "Synthetic:USB_C_Controller"},
        pin_functions={"U1.1": cc1_function, "U1.2": cc2_function},
        component_pin_numbers={"U1": ("1", "2")},
        dnp_components=("U1",) if dnp else (),
    )
