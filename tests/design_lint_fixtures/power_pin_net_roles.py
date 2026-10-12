"""Small synthetic netlists for named power-pin and net-role checks."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def positive_supply_on_return_netlist() -> NetlistContract:
    """One fitted named VDD pin is assigned to a GND net."""
    return NetlistContract(
        components={"U1": ComponentContract(value="Synthetic IC", footprint="Synthetic:IC")},
        nets={"GND": ("U1.1", "U1.2")},
        component_symbols={"U1": "Synthetic:Logic"},
        component_pin_numbers={"U1": ("1", "2")},
        pin_functions={"U1.1": "VDD", "U1.2": "GND"},
        pin_electrical_types={"U1.1": "passive", "U1.2": "passive"},
    )


def supply_pin_on_rail_netlist(
    rail: str,
    *,
    function: str = "VDD",
    dnp: bool = False,
    assigned: bool = True,
    ambiguous: bool = False,
) -> NetlistContract:
    """Build a two-pin synthetic supply component with controlled pin metadata."""
    nets: dict[str, tuple[str, ...]] = {"GND": ("U1.2",)}
    if assigned:
        nets[rail] = ("U1.1",)
    if ambiguous:
        nets["ALTERNATE_RAIL"] = (*nets.get("ALTERNATE_RAIL", ()), "U1.1")
    return NetlistContract(
        components={"U1": ComponentContract(value="Synthetic IC", footprint="Synthetic:IC")},
        nets=nets,
        dnp_components=("U1",) if dnp else (),
        component_symbols={"U1": "Synthetic:Logic"},
        component_pin_numbers={"U1": ("1", "2")},
        pin_functions={"U1.1": function, "U1.2": "GND"},
        pin_electrical_types={"U1.1": "passive", "U1.2": "passive"},
    )
