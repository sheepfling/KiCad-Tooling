"""Typed native-netlist contracts for named component power-pin fixtures."""

from __future__ import annotations

from collections.abc import Mapping

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
    """Return missing, split, and common component-return fixture contracts."""
    return {
        "unconnected-named-component-return-fault": _named_component_power_pins(
            nets={"+3V3": ("U1.1",)},
        ),
        "unconnected-named-component-power-control": _named_component_power_pins(
            nets={"+3V3": ("U1.1",), "GND": ("U1.2",)},
        ),
        "split-named-component-return-fault": _mapped_component_returns(split=True),
        "common-named-component-return-control": _mapped_component_returns(split=False),
    }


def _named_component_power_pins(*, nets: Mapping[str, tuple[str, ...]]) -> NetlistContract:
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


def _mapped_component_returns(*, split: bool) -> NetlistContract:
    """Build exact mapped GND/AGND pins with split and common return controls."""
    return NetlistContract(
        components={
            "U1": ComponentContract(
                value="Synthetic return component", footprint="Synthetic:Component"
            )
        },
        nets=(
            {"RETURN_A": ("U1.1",), "RETURN_B": ("U1.2",)}
            if split
            else {"RETURN": ("U1.1", "U1.2")}
        ),
        component_symbols={"U1": "Lint:MultiReturnComponent"},
        component_pin_numbers={"U1": ("1", "2")},
        pin_functions={"U1.1": "GND", "U1.2": "AGND"},
    )
