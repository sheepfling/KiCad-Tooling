"""Minimal native-shaped evidence for Ethernet data-pair open-pin lint."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def ethernet_data_unconnected_netlist(
    *, open_pins: tuple[str, ...] = (), dnp: bool = False
) -> NetlistContract:
    """Build a complete four-pin Ethernet PHY inventory with selected opens."""
    functions = {"U1.1": "TDP", "U1.2": "TDN", "U1.3": "RDP", "U1.4": "RDN"}
    net_pins = {
        "ETH_TX_P": ("U1.1",),
        "ETH_TX_N": ("U1.2",),
        "ETH_RX_P": ("U1.3",),
        "ETH_RX_N": ("U1.4",),
    }
    return NetlistContract(
        components={"U1": ComponentContract(value="Synthetic Ethernet PHY", footprint="")},
        nets={
            name: tuple(pin for pin in pins if pin not in open_pins)
            for name, pins in net_pins.items()
        },
        dnp_components=("U1",) if dnp else (),
        component_symbols={"U1": "Synthetic:EthernetPhy"},
        pin_functions=functions,
        component_pin_numbers={"U1": ("1", "2", "3", "4")},
    )
