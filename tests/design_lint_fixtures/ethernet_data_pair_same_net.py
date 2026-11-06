"""Tooling-owned typed-netlist cases for Ethernet differential pair lint."""

from __future__ import annotations

from collections.abc import Mapping

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract

PIN_FUNCTIONS = {
    "U1.1": "TDP",
    "U1.2": "TDN",
    "U1.3": "RDP",
    "U1.4": "RDN",
    "U1.5": "MDC",
    "U1.6": "MDIO",
}
PIN_TYPES = {
    "U1.1": "output",
    "U1.2": "output",
    "U1.3": "input",
    "U1.4": "input",
    "U1.5": "input",
    "U1.6": "bidirectional",
}


def ethernet_data_pair_same_net_netlist(
    *,
    shared_direction: str | None = "RX",
    dnp: bool = False,
    open_pin: str | None = None,
    ambiguous_pin: str | None = None,
    reference: str = "U1",
    functions: Mapping[str, str] | None = None,
    electrical_types: Mapping[str, str] | None = None,
    complete_inventory: bool = True,
) -> NetlistContract:
    """Build a complete fitted PHY inventory with one optional differential short."""
    pin_functions = {pin: name.replace("U1", reference, 1) for pin, name in PIN_FUNCTIONS.items()}
    if functions is not None:
        pin_functions.update(functions)
    pin_types = {pin.replace("U1", reference, 1): value for pin, value in PIN_TYPES.items()}
    if electrical_types is not None:
        pin_types.update(electrical_types)

    nets: dict[str, list[str]] = {}
    for pin, function in pin_functions.items():
        identity = function.casefold().replace("_", "")
        if identity in {"tdp", "td+"}:
            net = "ETH_TX_SHARED" if shared_direction == "TX" else "ETH_TX_P"
        elif identity in {"tdn", "td-"}:
            net = "ETH_TX_SHARED" if shared_direction == "TX" else "ETH_TX_N"
        elif identity in {"rdp", "rd+"}:
            net = "ETH_RX_SHARED" if shared_direction == "RX" else "ETH_RX_P"
        elif identity in {"rdn", "rd-"}:
            net = "ETH_RX_SHARED" if shared_direction == "RX" else "ETH_RX_N"
        elif identity == "mdc":
            net = "ETH_MDC"
        elif identity == "mdio":
            net = "ETH_MDIO"
        else:
            net = f"AUX_{pin.rsplit('.', 1)[-1]}"
        if pin != open_pin:
            nets.setdefault(net, []).append(pin)
            if pin == ambiguous_pin:
                nets.setdefault("OTHER_NET", []).append(pin)

    inventory = tuple(str(index) for index in range(1, 7))
    if not complete_inventory:
        inventory = inventory[:-1]
    return NetlistContract(
        components={reference: ComponentContract(value="Synthetic Ethernet PHY", footprint="")},
        nets={net: tuple(pins) for net, pins in nets.items()},
        dnp_components=(reference,) if dnp else (),
        component_symbols={reference: "Synthetic:EthernetPhy"},
        pin_functions=pin_functions,
        pin_electrical_types=pin_types,
        component_pin_numbers={reference: inventory},
    )
