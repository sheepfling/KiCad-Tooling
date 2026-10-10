"""Synthetic design-lint inputs for focused regression suites."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import (
    ComponentContract,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
)


def i2c_netlist(
    pullups: tuple[str, ...] = (), resistance: str = "4.7k", rail: str = "+3V3"
) -> NetlistContract:
    nets: dict[str, tuple[str, ...]] = {
        "SDA_BUS": ("U1.1",),
        "SCL_BUS": ("U1.2",),
    }
    components: dict[str, ComponentContract] = {}
    for line, number in (("SDA", 1), ("SCL", 2)):
        if line not in pullups:
            continue
        reference = f"R{number}"
        components[reference] = ComponentContract(value=resistance, footprint="")
        bus_net = "SDA_BUS" if line == "SDA" else "SCL_BUS"
        nets[bus_net] = (*nets[bus_net], f"{reference}.1")
        nets.setdefault(rail, ())
        nets[rail] = (*nets[rail], f"{reference}.2")
    return NetlistContract(
        components=components,
        nets=nets,
        component_symbols={"U1": "Synthetic:I2cTarget"},
        pin_functions={"U1.1": "SDA", "U1.2": "I2C_SCL"},
    )


def i2c_netlist_with_parallel_sda(
    resistance: str = "1k", parallel_resistance: str | None = None
) -> NetlistContract:
    source = i2c_netlist(pullups=("SDA", "SCL"), resistance=resistance)
    components = dict(source.components)
    components["R3"] = ComponentContract(
        value=parallel_resistance or resistance,
        footprint="",
    )
    nets = dict(source.nets)
    nets["SDA_BUS"] = (*nets["SDA_BUS"], "R3.1")
    nets["+3V3"] = (*nets["+3V3"], "R3.2")
    return source.model_copy(update={"components": components, "nets": nets})


def i2c_netlist_with_pullup_rails(
    sda_rails: tuple[str, ...] = ("+3V3",),
    scl_rails: tuple[str, ...] = ("+3V3",),
) -> NetlistContract:
    components: dict[str, ComponentContract] = {}
    nets: dict[str, tuple[str, ...]] = {
        "SDA_BUS": ("U1.1",),
        "SCL_BUS": ("U1.2",),
    }
    number = 1
    for line, bus_net, rails in (
        ("SDA", "SDA_BUS", sda_rails),
        ("SCL", "SCL_BUS", scl_rails),
    ):
        for rail in rails:
            reference = f"R{number}"
            number += 1
            components[reference] = ComponentContract(value="4.7k", footprint="")
            nets[bus_net] = (*nets[bus_net], f"{reference}.1")
            nets[rail] = (*nets.get(rail, ()), f"{reference}.2")
    return NetlistContract(
        components=components,
        nets=nets,
        component_symbols={"U1": "Synthetic:I2cTarget"},
        pin_functions={"U1.1": "SDA", "U1.2": "I2C_SCL"},
    )


def i2c_netlist_with_series_sda(
    first_resistance: str = "2.2k",
    second_resistance: str = "2.2k",
    *,
    base_pullups: tuple[str, ...] = ("SCL",),
    base_resistance: str = "4.7k",
    branched_junction: bool = False,
) -> NetlistContract:
    source = i2c_netlist(pullups=base_pullups, resistance=base_resistance)
    components = dict(source.components)
    components.update(
        {
            "R3": ComponentContract(value=first_resistance, footprint=""),
            "R4": ComponentContract(value=second_resistance, footprint=""),
        }
    )
    nets = dict(source.nets)
    nets["SDA_BUS"] = (*nets["SDA_BUS"], "R3.1")
    nets["PULLUP_MID"] = ("R3.2", "R4.1")
    nets["+3V3"] = (*nets.get("+3V3", ()), "R4.2")
    component_symbols = dict(source.component_symbols)
    pin_functions = dict(source.pin_functions)
    if branched_junction:
        nets["PULLUP_MID"] = (*nets["PULLUP_MID"], "U2.1")
        component_symbols["U2"] = "Synthetic:BranchLoad"
        pin_functions["U2.1"] = "GPIO"
    return source.model_copy(
        update={
            "components": components,
            "nets": nets,
            "component_symbols": component_symbols,
            "pin_functions": pin_functions,
        }
    )


def can_netlist(termination: str | None = None) -> NetlistContract:
    components = {
        "U1": ComponentContract(value="CAN transceiver", footprint=""),
    }
    nets: dict[str, tuple[str, ...]] = {
        "CAN_HIGH": ("U1.1",),
        "CAN_LOW": ("U1.2",),
    }
    symbols = {"U1": "Synthetic:CanTransceiver"}
    pin_functions = {"U1.1": "CANH", "U1.2": "CAN_L"}
    if termination is not None:
        components["R1"] = ComponentContract(value=termination, footprint="")
        symbols["R1"] = "Device:R"
        pin_functions.update({"R1.1": "1", "R1.2": "2"})
        nets["CAN_HIGH"] = (*nets["CAN_HIGH"], "R1.1")
        nets["CAN_LOW"] = (*nets["CAN_LOW"], "R1.2")
    return NetlistContract(
        components=components,
        nets=nets,
        component_symbols=symbols,
        pin_functions=pin_functions,
    )


def can_peer_netlist(
    *, divergent_peer: bool = False, separate_buses: bool = False
) -> NetlistContract:
    participants = {
        "U1": ("NET_A", "NET_B"),
        "U2": ("NET_A", "NET_B"),
    }
    if separate_buses:
        participants.update(
            {
                "U3": ("NET_C", "NET_D"),
                "U4": ("NET_C", "NET_D"),
            }
        )
    else:
        participants["U3"] = (
            "NET_A",
            "NET_C" if divergent_peer else "NET_B",
        )

    components = {
        reference: ComponentContract(value="Synthetic CAN transceiver", footprint="Synthetic:SOIC")
        for reference in participants
    }
    component_symbols = {reference: "Synthetic:CanTransceiver" for reference in participants}
    pin_functions = {
        pin: function
        for reference in participants
        for pin, function in ((f"{reference}.1", "CANH"), (f"{reference}.2", "CAN_L"))
    }
    nets: dict[str, list[str]] = {}
    for reference, (high_net, low_net) in participants.items():
        nets.setdefault(high_net, []).append(f"{reference}.1")
        nets.setdefault(low_net, []).append(f"{reference}.2")

    distinct_pairs = tuple(sorted(set(participants.values())))
    for index, (high_net, low_net) in enumerate(distinct_pairs, start=1):
        reference = f"R{index}"
        components[reference] = ComponentContract(value="120R", footprint="Synthetic:0603")
        component_symbols[reference] = "Device:R"
        nets.setdefault(high_net, []).append(f"{reference}.1")
        nets.setdefault(low_net, []).append(f"{reference}.2")

    return NetlistContract(
        components=components,
        nets={net: tuple(pins) for net, pins in nets.items()},
        component_symbols=component_symbols,
        pin_functions=pin_functions,
        component_pin_numbers={
            **{reference: ("1", "2") for reference in participants},
            **{f"R{index}": ("1", "2") for index in range(1, len(distinct_pairs) + 1)},
        },
    )


def spi_active_low_select_netlist(
    *,
    resistor_values: tuple[str, ...] = (),
    resistor_dnp: tuple[str, ...] = (),
    device_dnp: bool = False,
    select_function: str = "CS_N",
    select_electrical_type: str = "input",
    resistor_rail: str = "+3V3",
) -> NetlistContract:
    """Build a synthetic SPI peripheral and optional fitted pull-up chain."""
    components = {
        "U1": ComponentContract(value="Synthetic controller", footprint=""),
        "U2": ComponentContract(value="Synthetic peripheral", footprint=""),
    }
    nets: dict[str, tuple[str, ...]] = {
        "SPI_CS_N": ("U2.1",),
        "SPI_CLOCK": ("U1.2", "U2.2"),
        "+3V3": ("U1.1",),
        "GND": ("U1.3",),
    }
    pin_functions = {
        "U1.1": "VDD",
        "U1.2": "GPIO",
        "U1.3": "GND",
        "U2.1": select_function,
        "U2.2": "SCK",
        "U2.3": "MOSI",
    }
    component_symbols = {
        "U1": "Synthetic:SpiController",
        "U2": "Synthetic:SpiPeripheral",
    }
    pin_electrical_types = {
        "U2.1": select_electrical_type,
    }
    component_pin_numbers = {
        "U1": ("1", "2", "3"),
        "U2": ("1", "2", "3"),
    }
    if resistor_values:
        for index, value in enumerate(resistor_values, start=1):
            reference = f"R{index}"
            previous_net = "SPI_CS_N" if index == 1 else f"PULLUP_MID_{index - 1}"
            next_net = resistor_rail if index == len(resistor_values) else f"PULLUP_MID_{index}"
            components[reference] = ComponentContract(value=value, footprint="")
            component_symbols[reference] = "Device:R"
            component_pin_numbers[reference] = ("1", "2")
            pin_functions[f"{reference}.1"] = "1"
            pin_functions[f"{reference}.2"] = "2"
            nets[previous_net] = (*nets.get(previous_net, ()), f"{reference}.1")
            nets[next_net] = (*nets.get(next_net, ()), f"{reference}.2")
    return NetlistContract(
        components=components,
        nets=nets,
        dnp_components=(*resistor_dnp, "U2") if device_dnp else resistor_dnp,
        component_symbols=component_symbols,
        pin_functions=pin_functions,
        pin_electrical_types=pin_electrical_types,
        component_pin_numbers=component_pin_numbers,
    )


def complementary_usb_netlist(
    positive_net: str | None = "USB_DP", negative_net: str | None = "USB_DM"
) -> NetlistContract:
    nets: dict[str, tuple[str, ...]] = {}
    if positive_net is not None:
        nets[positive_net] = (*nets.get(positive_net, ()), "J1.1")
    if negative_net is not None:
        nets[negative_net] = (*nets.get(negative_net, ()), "J1.2")
    return NetlistContract(
        components={},
        nets=nets,
        component_symbols={"J1": "Synthetic:UsbPort"},
        pin_functions={"J1.1": "USB_D+", "J1.2": "D−"},
    )


def unconnected_protocol_pins() -> NetlistContract:
    return NetlistContract(
        components={
            "U1": ComponentContract(value="I2C target", footprint=""),
            "U2": ComponentContract(value="SPI peripheral", footprint=""),
        },
        nets={},
        component_symbols={
            "U1": "Synthetic:I2cTarget",
            "U2": "Synthetic:SpiPeripheral",
            "J1": "Synthetic:UsbCReceptacle",
        },
        pin_functions={
            "U1.1": "SDA",
            "U1.2": "I2C_SCL",
            "U2.1": "CS_N",
            "J1.1": "CC1",
            "J1.2": "CC2",
        },
    )


def policy_without_i2c_map_prompt() -> DesignLintPolicy:
    return DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id="bus.i2c_unmapped_responder",
                mode="off",
                reason="This test isolates the separate I2C pull-up or pin-assignment rule",
            ),
        )
    )
