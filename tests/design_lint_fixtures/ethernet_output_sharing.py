"""Synthetic Ethernet PHY output-sharing netlists for lint regressions."""

from __future__ import annotations

from kicad_tooling.hwrepo.netlist_contract_models import ComponentContract, NetlistContract


def ethernet_phy_output_sharing_netlist(
    *,
    default_function: str,
    pin_number: str,
    shared: bool = True,
    references: tuple[str, ...] = ("U1", "U2"),
    functions: tuple[str, ...] | None = None,
    net_name: str,
    pin_type: str = "passive",
    dnp_references: tuple[str, ...] = (),
) -> NetlistContract:
    """Build explicit PHY identities with one shared or separate output role."""
    selected_functions = functions or tuple(default_function for _ in references)
    nets: dict[str, tuple[str, ...]] = {}
    pin_functions: dict[str, str] = {}
    pin_types: dict[str, str] = {}
    inventory: dict[str, tuple[str, ...]] = {}
    if shared and len(references) >= 2:
        nets[net_name] = tuple(f"{reference}.{pin_number}" for reference in references)
    for index, reference in enumerate(references):
        pin = f"{reference}.{pin_number}"
        pin_functions[pin] = selected_functions[index]
        pin_types[pin] = pin_type
        inventory[reference] = (pin_number,)
        if not shared:
            nets[f"PHY{index + 1}_{default_function}"] = (pin,)
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
