"""Typed native-netlist contracts for named component power-pin fixtures."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def named_component_supply_pin_cases() -> dict[str, NetlistContract]:
    """Return an open VDD fault and a fully assigned power-pin control."""
    return {
        "unconnected-named-component-supply-fault": _named_component_power_pins(
            nets={"GND": ("U1.2",)},
        ),
        "unconnected-named-component-power-control": _named_component_power_pins(
            nets={"+3V3": ("U1.1",), "GND": ("U1.2",)},
        ),
    }


def named_component_return_pin_cases() -> dict[str, NetlistContract]:
    """Return an open GND fault and a fully assigned power-pin control."""
    return {
        "unconnected-named-component-return-fault": _named_component_power_pins(
            nets={"+3V3": ("U1.1",)},
        ),
        "unconnected-named-component-power-control": _named_component_power_pins(
            nets={"+3V3": ("U1.1",), "GND": ("U1.2",)},
        ),
    }


def _named_component_power_pins(*, nets: dict[str, tuple[str, ...]]) -> NetlistContract:
    """Build native-shaped evidence for one synthetic named-pin component."""
    return NetlistContract(
        components={
            "U1": ComponentContract(
                value="Synthetic named component", footprint="Synthetic:Component"
            )
        },
        nets=nets,
        component_symbols={"U1": "Lint:PowerRoleComponent"},
        component_pin_numbers={"U1": ("1", "2")},
        pin_functions={"U1.1": "VDD", "U1.2": "GND"},
    )
