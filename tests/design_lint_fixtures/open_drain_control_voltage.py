"""Synthetic netlists for open-collector control pull-up voltage review."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def open_drain_control_voltage_netlist(
    *,
    pullup_rail: str = "+5V",
    driver_rail: str = "+3V3",
    receiver_rail: str = "+3V3",
    driver_type: str = "open_collector",
    receiver_function: str = "RESET_N",
    receiver_type: str = "input",
    resistor_dnp: bool = False,
    extra_pullup_rail: str | None = None,
    missing_pin_type: str | None = None,
    signal_net: str = "RESET_SIGNAL",
) -> NetlistContract:
    """Build one bounded open-collector control link and visible pull-up."""
    net_pins: dict[str, list[str]] = {}
    for net, pins in (
        (signal_net, ("U1.1", "U2.1", "R1.1")),
        (driver_rail, ("U1.2",)),
        (receiver_rail, ("U2.2",)),
        ("GND", ("U1.3", "U2.3")),
        (pullup_rail, ("R1.2",)),
    ):
        net_pins.setdefault(net, []).extend(pins)
    if extra_pullup_rail is not None:
        net_pins.setdefault(extra_pullup_rail, []).append("R2.2")
        net_pins[signal_net].append("R2.1")
    nets = {net: tuple(pins) for net, pins in net_pins.items()}

    pin_types = {
        "U1.1": driver_type,
        "U1.2": "power_in",
        "U1.3": "power_in",
        "U2.1": receiver_type,
        "U2.2": "power_in",
        "U2.3": "power_in",
        "R1.1": "passive",
        "R1.2": "passive",
    }
    pin_functions = {
        "U1.1": "GPIO0",
        "U1.2": "VDD",
        "U1.3": "GND",
        "U2.1": receiver_function,
        "U2.2": "VDD",
        "U2.3": "GND",
    }
    component_pin_numbers = {
        "U1": ("1", "2", "3"),
        "U2": ("1", "2", "3"),
        "R1": ("1", "2"),
    }
    components = {
        "U1": ComponentContract(value="Synthetic MCU", footprint="Package:MCU"),
        "U2": ComponentContract(value="Synthetic receiver", footprint="Package:IC"),
        "R1": ComponentContract(value="10k", footprint="Package:R_0603"),
    }
    component_symbols = {"U1": "Synthetic:MCU", "U2": "Synthetic:Receiver", "R1": "Device:R"}
    if extra_pullup_rail is not None:
        pin_types.update({"R2.1": "passive", "R2.2": "passive"})
        component_pin_numbers["R2"] = ("1", "2")
        components["R2"] = ComponentContract(value="10k", footprint="Package:R_0603")
        component_symbols["R2"] = "Device:R"
    if missing_pin_type is not None:
        pin_types.pop(missing_pin_type, None)

    return NetlistContract(
        components=components,
        nets=nets,
        component_symbols=component_symbols,
        component_pin_numbers=component_pin_numbers,
        pin_functions=pin_functions,
        pin_electrical_types=pin_types,
        dnp_components=("R1",) if resistor_dnp else (),
    )
