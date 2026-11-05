"""Synthetic netlists for direct GPIO-to-control voltage-label review."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def gpio_control_voltage_netlist(
    *,
    output_rail: str = "+5V",
    input_rail: str = "+3V3",
    output_function: str = "GPIO0",
    input_function: str = "EN",
    output_type: str = "output",
    input_type: str = "input",
    dnp: tuple[str, ...] = (),
    missing_pin_type: str | None = None,
    extra_input_supply: bool = False,
    signal_net: str = "CONTROL_SIGNAL",
) -> NetlistContract:
    """Build one bounded control link with optional unsupported-case changes."""
    nets = {
        signal_net: ("U1.1", "U2.1"),
        output_rail: ("U1.2",),
        input_rail: ("U2.2",),
        "GND": ("U1.3", "U2.3"),
    }
    pin_types = {
        "U1.1": output_type,
        "U1.2": "power_in",
        "U1.3": "power_in",
        "U2.1": input_type,
        "U2.2": "power_in",
        "U2.3": "power_in",
    }
    pin_functions = {
        "U1.1": output_function,
        "U1.2": "VDD",
        "U1.3": "GND",
        "U2.1": input_function,
        "U2.2": "VDD",
        "U2.3": "GND",
    }
    if extra_input_supply:
        nets["+1V8"] = ("U2.4",)
        pin_types["U2.4"] = "power_in"
        pin_functions["U2.4"] = "VDDIO"
    if missing_pin_type is not None:
        pin_types.pop(missing_pin_type, None)
    return NetlistContract(
        components={
            "U1": ComponentContract(value="Synthetic MCU", footprint="Package:MCU"),
            "U2": ComponentContract(value="Synthetic regulator", footprint="Package:LDO"),
        },
        nets=nets,
        component_symbols={"U1": "Synthetic:MCU", "U2": "Synthetic:Regulator"},
        component_pin_numbers={
            "U1": ("1", "2", "3"),
            "U2": ("1", "2", "3", "4") if extra_input_supply else ("1", "2", "3"),
        },
        pin_functions=pin_functions,
        pin_electrical_types=pin_types,
        dnp_components=dnp,
    )
