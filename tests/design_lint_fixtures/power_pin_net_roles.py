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
