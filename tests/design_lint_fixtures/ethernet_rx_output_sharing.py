"""Synthetic Ethernet PHY netlists for receive-data output-sharing review."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def ethernet_rx_output_netlist(
    *,
    shared: bool = True,
    references: tuple[str, ...] = ("U1", "U2"),
    receiver_functions: tuple[str, ...] | None = None,
    receiver_type: str = "passive",
    dnp_references: tuple[str, ...] = (),
) -> NetlistContract:
    """Build fitted, fully inventoried PHYs with shared or isolated RX data pins."""
    functions = receiver_functions or tuple("RXD0" for _ in references)
    nets: dict[str, tuple[str, ...]] = {}
    pin_functions: dict[str, str] = {}
    pin_types: dict[str, str] = {}
    inventory: dict[str, tuple[str, ...]] = {}
    if shared and len(references) >= 2:
        nets["ETH_RXD_SHARED"] = tuple(f"{reference}.1" for reference in references)
    for index, reference in enumerate(references):
        rx_pin = f"{reference}.1"
        tx_pin = f"{reference}.2"
        pin_functions[rx_pin] = functions[index]
        pin_functions[tx_pin] = "TXD0"
        pin_types[rx_pin] = receiver_type
        pin_types[tx_pin] = "passive"
        inventory[reference] = ("1", "2")
        if not shared:
            nets[f"PHY{index + 1}_RXD"] = (rx_pin,)
        nets[f"PHY{index + 1}_TXD"] = (tx_pin,)
    return NetlistContract(
        components={
            reference: ComponentContract(value="Ethernet PHY module", footprint="")
            for reference in references
        },
        nets=nets,
        component_symbols={reference: "Synthetic:Ethernet_PHY" for reference in references},
        pin_functions=pin_functions,
        pin_electrical_types=pin_types,
        component_pin_numbers=inventory,
        dnp_components=dnp_references,
    )
