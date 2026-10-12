"""Typed native-netlist contracts for named component power-pin fixtures."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def named_component_supply_pin_cases() -> dict[str, NetlistContract]:
    """Return an open VDD fault and a fully assigned power-pin control."""
    component = ComponentContract(
        value="Synthetic named component", footprint="Synthetic:Component"
    )
    shared = {
        "components": {"U1": component},
        "component_symbols": {"U1": "Lint:PowerRoleComponent"},
        "component_pin_numbers": {"U1": ("1", "2")},
        "pin_functions": {"U1.1": "VDD", "U1.2": "GND"},
    }
    return {
        "unconnected-named-component-supply-fault": NetlistContract(
            **shared,
            nets={"GND": ("U1.2",)},
        ),
        "unconnected-named-component-power-control": NetlistContract(
            **shared,
            nets={"+3V3": ("U1.1",), "GND": ("U1.2",)},
        ),
    }
