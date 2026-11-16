"""Synthetic Ethernet PHY RX status netlists for lint regressions."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def ethernet_rx_status_output_netlist(
    *,
    shared: bool = True,
    references: tuple[str, ...] = ("U1", "U2"),
    status_functions: tuple[str, ...] | None = None,
    status_type: str = "passive",
    dnp_references: tuple[str, ...] = (),
) -> NetlistContract:
    """Build identified PHYs with shared or isolated RXDV/RXER status pins."""
    functions = status_functions or tuple("RXDV" for _ in references)
    nets: dict[str, tuple[str, ...]] = {}
    pin_functions: dict[str, str] = {}
    pin_types: dict[str, str] = {}
    inventory: dict[str, tuple[str, ...]] = {}
    if shared and len(references) >= 2:
        nets["MII_RX_DV_SHARED"] = tuple(f"{reference}.1" for reference in references)
    for index, reference in enumerate(references):
        status_pin = f"{reference}.1"
        data_pin = f"{reference}.2"
        pin_functions[status_pin] = functions[index]
        pin_functions[data_pin] = "RXD0"
        pin_types[status_pin] = status_type
        pin_types[data_pin] = "passive"
        inventory[reference] = ("1", "2")
        if not shared:
            nets[f"PHY{index + 1}_RX_STATUS"] = (status_pin,)
        nets[f"PHY{index + 1}_RXD0"] = (data_pin,)
    return NetlistContract(
        components={
            reference: ComponentContract(value="LAN8720 Ethernet PHY", footprint="")
            for reference in references
        },
        nets=nets,
        component_symbols={reference: "Synthetic:Ethernet_PHY" for reference in references},
        pin_functions=pin_functions,
        pin_electrical_types=pin_types,
        component_pin_numbers=inventory,
        dnp_components=dnp_references,
    )
