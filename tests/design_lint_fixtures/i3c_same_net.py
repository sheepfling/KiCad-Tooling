"""Synthetic I3C signal-pair assignments for same-net review tests."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def i3c_same_net_netlist(
    *,
    sda_function: str = "I3C1_SDA",
    scl_function: str = "I3C1_SCL",
    shared_net: str = "I3C_SHARED",
    dnp: bool = False,
) -> NetlistContract:
    """Build a fitted or DNP two-pin I3C controller fixture."""
    return NetlistContract(
        components={
            "U1": ComponentContract(value="Synthetic I3C controller", footprint="Synthetic:QFN")
        },
        nets={shared_net: ("U1.1", "U1.2")},
        component_symbols={"U1": "Synthetic:I3C_Controller"},
        pin_functions={"U1.1": sda_function, "U1.2": scl_function},
        component_pin_numbers={"U1": ("1", "2")},
        dnp_components=("U1",) if dnp else (),
    )


def i3c_distinct_lines_netlist() -> NetlistContract:
    """Build a valid distinct-line I3C control."""
    return i3c_same_net_netlist().model_copy(
        update={"nets": {"I3C_SDA": ("U1.1",), "I3C_SCL": ("U1.2",)}}
    )
