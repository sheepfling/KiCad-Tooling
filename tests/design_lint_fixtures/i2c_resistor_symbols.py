"""Synthetic I2C cases for exact resistor-symbol recognition."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract

from .buses import i2c_netlist


def i2c_netlist_with_device_r_symbol(
    *,
    reference: str = "X1",
    symbol: str = "Device:R",
    value: str = "4.7k",
    line: Literal["SDA", "SCL"] = "SDA",
    rail: str = "+3V3",
    base_pullups: tuple[str, ...] = ("SCL",),
    base_resistance: str = "4.7k",
    pin_numbers: Sequence[str] | None = ("1", "2"),
    extra_pin: bool = False,
    dnp: tuple[str, ...] = (),
) -> NetlistContract:
    """Build an I2C bus with one exact-symbol resistor under a non-R reference."""
    source = i2c_netlist(pullups=base_pullups, resistance=base_resistance)
    bus_net = f"{line}_BUS"
    components = dict(source.components)
    components[reference] = ComponentContract(value=value, footprint="")
    nets = dict(source.nets)
    nets[bus_net] = (*nets[bus_net], f"{reference}.1")
    nets[rail] = (*nets.get(rail, ()), f"{reference}.2")
    if extra_pin:
        nets["AUX_UNCONNECTED_ROLE"] = (f"{reference}.3",)
    component_symbols = {**source.component_symbols, reference: symbol}
    component_pin_numbers = dict(source.component_pin_numbers)
    if pin_numbers is not None:
        component_pin_numbers[reference] = tuple(pin_numbers)
    dnp_components = tuple(sorted({*source.dnp_components, *dnp}))
    return source.model_copy(
        update={
            "components": components,
            "nets": nets,
            "component_symbols": component_symbols,
            "component_pin_numbers": component_pin_numbers,
            "dnp_components": dnp_components,
        }
    )
