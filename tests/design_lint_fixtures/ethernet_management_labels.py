"""Small typed-netlist fixtures for Ethernet MDC/MDIO label review."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def ethernet_management_netlist(
    *,
    functions: tuple[str, str] = ("MDC", "MDIO"),
    labels: tuple[str, str] = ("ETH_MDC", "ETH_MDIO"),
    dnp: bool = False,
) -> NetlistContract:
    pins = ("U1.5", "U1.6")
    nets: dict[str, list[str]] = {}
    for label, pin in zip(labels, pins, strict=True):
        nets.setdefault(label, []).append(pin)
    return NetlistContract(
        components={"U1": ComponentContract(value="Synthetic Ethernet PHY", footprint="")},
        nets={label: tuple(net_pins) for label, net_pins in nets.items()},
        dnp_components=("U1",) if dnp else (),
        component_symbols={"U1": "Synthetic:EthernetPhy"},
        pin_functions=dict(zip(pins, functions, strict=True)),
        component_pin_numbers={"U1": ("5", "6")},
    )
