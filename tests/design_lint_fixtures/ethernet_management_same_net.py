"""Compact typed-netlist fixtures for Ethernet MDC/MDIO same-net review."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def ethernet_management_same_net_netlist(
    *,
    shared: bool = True,
    dnp: bool = False,
    open_pin: str | None = None,
    ambiguous_pin: str | None = None,
    functions: tuple[str, str] = ("MDC", "MDIO"),
    reference: str = "U1",
    pin_numbers: tuple[str, ...] = ("5", "6"),
    pin_types: tuple[str, str] = ("input", "bidirectional"),
) -> NetlistContract:
    clock_pin = f"{reference}.{pin_numbers[0]}"
    data_pin = f"{reference}.{pin_numbers[1]}"
    clock_net, data_net = (
        ("MII_MANAGEMENT", "MII_MANAGEMENT")
        if shared
        else (
            "MII_CLOCK",
            "MII_DATA",
        )
    )
    nets: dict[str, list[str]] = {}
    for pin, net in ((clock_pin, clock_net), (data_pin, data_net)):
        if pin == open_pin:
            continue
        nets.setdefault(net, []).append(pin)
        if pin == ambiguous_pin:
            nets.setdefault("OTHER_NET", []).append(pin)

    return NetlistContract(
        components={reference: ComponentContract(value="Synthetic Ethernet PHY", footprint="")},
        nets={net: tuple(pins) for net, pins in nets.items()},
        dnp_components=(reference,) if dnp else (),
        component_symbols={reference: "Synthetic:EthernetPhy"},
        pin_functions={
            clock_pin: functions[0],
            data_pin: functions[1],
        },
        pin_electrical_types={
            clock_pin: pin_types[0],
            data_pin: pin_types[1],
        },
        component_pin_numbers={reference: pin_numbers},
    )
