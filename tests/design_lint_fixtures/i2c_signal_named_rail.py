"""Synthetic I2C signal assignments for named-rail review checks."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import NetlistContract

from .i2c_signal_label import i2c_signal_label_netlist


def i2c_signal_on_named_rail_netlist(
    *, rail_name: str = "GND", pin: str = "U1.1"
) -> NetlistContract:
    """Move one explicit SDA/SCL pin from its bus net to a named-rail label."""
    source = i2c_signal_label_netlist()
    remaining_nets = {
        name: tuple(member for member in pins if member.casefold() != pin.casefold())
        for name, pins in source.nets.items()
    }
    nets = {name: pins for name, pins in remaining_nets.items() if pins}
    existing = nets.get(rail_name, ())
    nets[rail_name] = tuple(sorted((*existing, pin), key=lambda item: (item.casefold(), item)))
    return source.model_copy(update={"nets": nets})


def i2c_connector_signal_on_named_rail_netlist(
    *, rail_name: str = "GND", pin: str = "J1.1"
) -> NetlistContract:
    """Create a two-pin connector with one explicit I2C function on a named rail."""
    functions = {"J1.1": "SDA", "J1.2": "SCL"}
    if pin not in functions:
        raise ValueError(f"Unsupported synthetic I2C connector pin: {pin!r}")
    other_pin = next(item for item in functions if item != pin)
    other_role = functions[other_pin]
    source = i2c_signal_label_netlist()
    return source.model_copy(
        update={
            "components": {
                "J1": source.components["U1"].model_copy(
                    update={"value": "Synthetic I2C connector", "footprint": "Synthetic:Conn_01x02"}
                )
            },
            "nets": {rail_name: (pin,), f"I2C_{other_role}": (other_pin,)},
            "component_symbols": {"J1": "Connector_Generic:Conn_01x02"},
            "pin_functions": functions,
            "component_pin_numbers": {"J1": ("1", "2")},
        }
    )
