"""Synthetic native-netlist cases for enable-control return-label review."""

from __future__ import annotations

from kicad_tooling.hwrepo.netlist_contract_models import ComponentContract, NetlistContract


def enable_control_netlist(
    net: str = "GND",
    *,
    function: str = "EN",
    electrical_type: str = "input",
    dnp: bool = False,
    assigned: bool = True,
    ambiguous: bool = False,
) -> NetlistContract:
    """Build one fitted three-pin IC with controlled EN pin evidence."""
    nets: dict[str, tuple[str, ...]] = {
        "+3V3": ("U1.1",),
        "GND": ("U1.2",),
    }
    if assigned:
        nets[net] = (*nets.get(net, ()), "U1.3")
    if ambiguous:
        nets["ALTERNATE"] = (*nets.get("ALTERNATE", ()), "U1.3")
    return NetlistContract(
        components={"U1": ComponentContract(value="Synthetic IC", footprint="Synthetic:IC")},
        nets=nets,
        dnp_components=("U1",) if dnp else (),
        component_symbols={"U1": "Synthetic:EnableControl"},
        component_pin_numbers={"U1": ("1", "2", "3")},
        pin_functions={"U1.1": "VDD", "U1.2": "GND", "U1.3": function},
        pin_electrical_types={
            "U1.1": "power_in",
            "U1.2": "power_in",
            "U1.3": electrical_type,
        },
    )
