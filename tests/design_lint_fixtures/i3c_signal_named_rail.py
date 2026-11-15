"""Synthetic I3C signals assigned to named rails."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def i3c_signal_named_rail_netlist(
    *,
    reference: str = "U1",
    sda_function: str = "I3C1_SDA",
    scl_function: str = "I3C1_SCL",
    sda_net: str = "GND",
    scl_net: str = "+3V3",
    dnp: bool = False,
) -> NetlistContract:
    """Build a two-line synthetic I3C endpoint and explicit boundary variants."""
    is_connector = reference.casefold().startswith("j")
    pin1, pin2 = f"{reference}.1", f"{reference}.2"
    return NetlistContract(
        components={
            reference: ComponentContract(
                value=("Synthetic I3C connector" if is_connector else "Synthetic I3C controller"),
                footprint=("Synthetic:CONN_01X02" if is_connector else "Synthetic:QFN"),
            )
        },
        nets={net: (pin,) for net, pin in ((sda_net, pin1), (scl_net, pin2)) if net is not None},
        component_symbols={
            reference: (
                "Connector_Generic:Conn_01x02" if is_connector else "Synthetic:I3C_Controller"
            )
        },
        pin_functions={pin1: sda_function, pin2: scl_function},
        component_pin_numbers={reference: ("1", "2")},
        dnp_components=(reference,) if dnp else (),
    )
