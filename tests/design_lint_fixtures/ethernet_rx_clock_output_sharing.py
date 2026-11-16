"""Synthetic Ethernet PHY receive-clock netlists for lint regressions."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def ethernet_rx_clock_output_netlist(
    *,
    shared: bool = True,
    references: tuple[str, ...] = ("U1", "U2"),
    clock_functions: tuple[str, ...] | None = None,
    clock_type: str = "passive",
    dnp_references: tuple[str, ...] = (),
) -> NetlistContract:
    """Build fitted and fully inventoried PHYs with shared or isolated RX clocks."""
    functions = clock_functions or tuple("RXC" for _ in references)
    nets: dict[str, tuple[str, ...]] = {}
    pin_functions: dict[str, str] = {}
    pin_types: dict[str, str] = {}
    inventory: dict[str, tuple[str, ...]] = {}
    if shared and len(references) >= 2:
        nets["MII_RX_CLK_SHARED"] = tuple(f"{reference}.1" for reference in references)
    for index, reference in enumerate(references):
        clock_pin = f"{reference}.1"
        data_pin = f"{reference}.2"
        pin_functions[clock_pin] = functions[index]
        pin_functions[data_pin] = "RXD0"
        pin_types[clock_pin] = clock_type
        pin_types[data_pin] = "passive"
        inventory[reference] = ("1", "2")
        if not shared:
            nets[f"PHY{index + 1}_RX_CLK"] = (clock_pin,)
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
