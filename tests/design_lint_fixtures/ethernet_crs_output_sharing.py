"""Synthetic DP83848-style MII CRS netlists for lint regressions."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def ethernet_mii_crs_output_netlist(
    *,
    shared: bool = True,
    references: tuple[str, ...] = ("U1", "U2"),
    crs_functions: tuple[str, ...] | None = None,
    crs_net_name: str = "MII_CRS_SHARED",
    crs_type: str = "passive",
    dnp_references: tuple[str, ...] = (),
) -> NetlistContract:
    """Build identified PHYs with shared or separated carrier-sense outputs."""
    functions = crs_functions or tuple("CRS" for _ in references)
    nets: dict[str, tuple[str, ...]] = {}
    pin_functions: dict[str, str] = {}
    pin_types: dict[str, str] = {}
    inventory: dict[str, tuple[str, ...]] = {}
    if shared and len(references) >= 2:
        nets[crs_net_name] = tuple(f"{reference}.1" for reference in references)
    for index, reference in enumerate(references):
        crs_pin = f"{reference}.1"
        data_pin = f"{reference}.2"
        pin_functions[crs_pin] = functions[index]
        pin_functions[data_pin] = "RXD0"
        pin_types[crs_pin] = crs_type
        pin_types[data_pin] = "passive"
        inventory[reference] = ("1", "2")
        if not shared:
            nets[f"PHY{index + 1}_CRS"] = (crs_pin,)
        nets[f"PHY{index + 1}_RXD0"] = (data_pin,)
    return NetlistContract(
        components={
            reference: ComponentContract(value="DP83848 Ethernet PHY", footprint="")
            for reference in references
        },
        nets=nets,
        component_symbols={reference: "Synthetic:Ethernet_PHY" for reference in references},
        pin_functions=pin_functions,
        pin_electrical_types=pin_types,
        component_pin_numbers=inventory,
        dnp_components=dnp_references,
    )
