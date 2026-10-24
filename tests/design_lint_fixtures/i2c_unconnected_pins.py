"""Synthetic I2C pin assignments for partial-channel lint regressions."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def i2c_unconnected_netlist(
    *,
    open_pins: tuple[str, ...] = ("U1.1",),
    dnp_components: tuple[str, ...] = (),
    functions: dict[str, str] | None = None,
) -> NetlistContract:
    """Build one two-pin I2C component with configurable assignment evidence."""
    pin_functions = functions or {"U1.1": "SDA", "U1.2": "I2C_SCL"}
    open_keys = {pin.casefold() for pin in open_pins}
    source_nets = {
        "I2C_DATA": ("U1.1",),
        "I2C_CLOCK": ("U1.2",),
    }
    nets = {
        net: pins
        for net, pins in source_nets.items()
        if any(pin.casefold() not in open_keys for pin in pins)
    }
    nets = {
        net: tuple(pin for pin in pins if pin.casefold() not in open_keys)
        for net, pins in nets.items()
    }
    nets = {net: pins for net, pins in nets.items() if pins}
    return NetlistContract(
        components={"U1": ComponentContract(value="Synthetic I2C peer", footprint="Synthetic:QFN")},
        nets=nets,
        unconnected_nets={"unconnected": tuple(sorted(open_pins))},
        dnp_components=dnp_components,
        component_symbols={"U1": "Synthetic:I2cPeer"},
        pin_functions=pin_functions,
        component_pin_numbers={"U1": ("1", "2")},
    )
