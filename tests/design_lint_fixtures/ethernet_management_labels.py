"""Small typed-netlist fixtures for Ethernet MDC/MDIO label review."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def ethernet_management_netlist(
    *,
    reference: str = "U1",
    functions: tuple[str, str] = ("MDC", "MDIO"),
    labels: tuple[str, str] = ("ETH_MDC", "ETH_MDIO"),
    open_functions: tuple[str, ...] = (),
    dnp: bool = False,
) -> NetlistContract:
    is_connector = reference.upper().startswith("J")
    pin_numbers = ("1", "2") if is_connector else ("5", "6")
    pins = tuple(f"{reference}.{number}" for number in pin_numbers)
    nets: dict[str, list[str]] = {}
    for label, pin, function in zip(labels, pins, functions, strict=True):
        if function not in open_functions:
            nets.setdefault(label, []).append(pin)
    return NetlistContract(
        components={
            reference: ComponentContract(
                value="Synthetic Ethernet management connector"
                if is_connector
                else "Synthetic Ethernet PHY",
                footprint="",
            )
        },
        nets={label: tuple(net_pins) for label, net_pins in nets.items()},
        dnp_components=(reference,) if dnp else (),
        component_symbols={
            reference: "Connector:Conn_01x02" if is_connector else "Synthetic:EthernetPhy"
        },
        pin_functions=dict(zip(pins, functions, strict=True)),
        component_pin_numbers={reference: pin_numbers},
    )
