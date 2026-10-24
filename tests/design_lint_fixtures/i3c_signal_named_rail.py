"""Synthetic I3C signals assigned to named rails."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def i3c_signal_named_rail_netlist(
    *,
    sda_function: str = "I3C1_SDA",
    scl_function: str = "I3C1_SCL",
    sda_net: str = "GND",
    scl_net: str = "+3V3",
    dnp: bool = False,
) -> NetlistContract:
    """Build a two-line synthetic I3C IC and explicit boundary variants."""
    return NetlistContract(
        components={
            "U1": ComponentContract(value="Synthetic I3C controller", footprint="Synthetic:QFN")
        },
        nets={sda_net: ("U1.1",), scl_net: ("U1.2",)},
        component_symbols={"U1": "Synthetic:I3C_Controller"},
        pin_functions={"U1.1": sda_function, "U1.2": scl_function},
        component_pin_numbers={"U1": ("1", "2")},
        dnp_components=("U1",) if dnp else (),
    )
