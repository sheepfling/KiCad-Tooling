"""Synthetic MII transmit-clock sharing netlists for lint regressions."""

from __future__ import annotations

from kicad_tooling.hwrepo.netlist_contract_models import ComponentContract, NetlistContract


def ethernet_mii_tx_clock_output_netlist(
    *,
    shared: bool = True,
    references: tuple[str, ...] = ("U1", "U2"),
    functions: tuple[str, ...] | None = None,
    net_name: str = "MII_TX_CLK_SHARED",
    pin_type: str = "passive",
    dnp_references: tuple[str, ...] = (),
) -> NetlistContract:
    """Build explicit Ethernet PHY identities with shared or separate TX_CLK pins."""
    selected_functions = functions or tuple("TX_CLK" for _ in references)
    nets: dict[str, tuple[str, ...]] = {}
    pin_functions: dict[str, str] = {}
    pin_types: dict[str, str] = {}
    inventory: dict[str, tuple[str, ...]] = {}
    if shared and len(references) >= 2:
        nets[net_name] = tuple(f"{reference}.1" for reference in references)
    for index, reference in enumerate(references):
        clock_pin = f"{reference}.1"
        pin_functions[clock_pin] = selected_functions[index]
        pin_types[clock_pin] = pin_type
        inventory[reference] = ("1",)
        if not shared:
            nets[f"PHY{index + 1}_TX_CLK"] = (clock_pin,)
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
