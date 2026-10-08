"""Synthetic design-lint regressions and exact project-owned decisions."""

from __future__ import annotations

import hashlib
import unittest
from pathlib import Path

from pydantic import ValidationError

from kicad_tooling.hwrepo.control_inputs import control_input_bias_heuristic_coverage
from kicad_tooling.hwrepo.design_lint import (
    DigitalPeerVoltageLintContext,
    candidates,
    evaluate,
    fingerprint,
    text_report,
)
from kicad_tooling.hwrepo.models import (
    ComplementaryPinFunctionAlias,
    ComplementaryPinFunctionAliasMap,
    ComponentContract,
    ConnectorCoverageEntry,
    ConnectorCoverageReport,
    ContractCoachReport,
    DesignLintFinding,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintReport,
    DesignLintRuleOverride,
    DigitalLogicInputLimits,
    DigitalLogicOutputLimits,
    DigitalPeerPinRequirement,
    DigitalPeerVoltageAnalysis,
    DigitalPeerVoltageLink,
    NetlistContract,
    PcbDifferentialPairRuleMap,
    PcbDifferentialPairRuleRequirement,
    PcbDrcMinMaxRequirement,
)
from kicad_tooling.hwrepo.schematic_geometry import scan_wire_ends_on_pin_lines
from tests.test_control_inputs import control_netlist, control_requirement
from tests.test_schematic_geometry import (
    free_text_anchor_fixture,
    free_text_objects_fixture,
    free_text_symbol_body_fixture,
    free_text_wire_fixture,
    symbol_body_wire_fixture,
)


def observed(power_j3_connected: bool = False) -> NetlistContract:
    nets: dict[str, tuple[str, ...]] = {
        "+5V": ("J1.1", "J2.1"),
        "GND1": ("J1.7",),
        "GND2": ("J2.7",),
    }
    if power_j3_connected:
        nets["+12V"] = ("J3.1",)
    return NetlistContract(
        components={},
        nets=nets,
        component_symbols={
            "J1": "Synthetic:Port",
            "J2": "Synthetic:Port",
            "J3": "Synthetic:PowerOnlyPort",
        },
        component_pin_numbers={
            "J1": ("1", "7"),
            "J2": ("1", "7"),
            "J3": ("1",),
        },
        pin_functions={
            "J1.1": "PWR",
            "J2.1": "PWR",
            "J3.1": "PWR",
            "J1.7": "GND",
            "J2.7": "GND",
        },
    )


def connector_capacitor_only_netlist(
    *,
    dnp: tuple[str, ...] = (),
    extra_signal_pin: bool = False,
) -> NetlistContract:
    """Build a synthetic connector/capacitor net and bounded controls."""
    components = {"C1": ComponentContract(value="100n", footprint="")}
    component_symbols = {
        "J1": "Connector_Generic:Conn_01x02",
        "C1": "Device:C",
    }
    component_pin_numbers = {"J1": ("1", "2"), "C1": ("1", "2")}
    nets: dict[str, tuple[str, ...]] = {
        "ANALOG_IN": ("J1.1", "C1.1"),
        "GND": ("J1.2", "C1.2"),
    }
    if extra_signal_pin:
        components["U1"] = ComponentContract(value="Synthetic output", footprint="")
        component_symbols["U1"] = "Synthetic:SignalDriver"
        component_pin_numbers["U1"] = ("1",)
        nets["ANALOG_IN"] = (*nets["ANALOG_IN"], "U1.1")
    return NetlistContract(
        components=components,
        nets=nets,
        dnp_components=dnp,
        component_symbols=component_symbols,
        component_pin_numbers=component_pin_numbers,
    )


def cross_symbol_returns(common: bool = False, serial_connected: bool = True) -> NetlistContract:
    if common:
        nets = {"GND": ("J1.4", "J2.7"), "SHIELD": ("J3.5",)}
    else:
        nets = {"USB_RETURN": ("J1.4",), "SHIELD": ("J3.5",)}
        if serial_connected:
            nets["SERIAL_RETURN"] = ("J2.7",)
    return NetlistContract(
        components={},
        nets=nets,
        component_symbols={
            "J1": "Synthetic:USB-C",
            "J2": "Synthetic:DB9",
            "J3": "Synthetic:ShieldedPort",
        },
        pin_functions={"J1.4": "GND", "J2.7": "RTN", "J3.5": "SHIELD"},
    )


def four_db9_return_domains(common: bool = False) -> NetlistContract:
    """Create a synthetic four-port DB9 return pattern with numeric pin functions."""
    return_pins = tuple(f"J{reference}.{pin}" for reference in range(1, 5) for pin in (7, 9))
    if common:
        nets = {"0V PWM": return_pins}
    else:
        nets = {
            f"0V PWM {reference}": (f"J{reference}.7", f"J{reference}.9")
            for reference in range(1, 5)
        }
    return NetlistContract(
        components={},
        nets=nets,
        component_symbols={f"J{reference}": "Synthetic:DB9" for reference in range(1, 5)},
        component_pin_numbers={f"J{reference}": ("7", "9") for reference in range(1, 5)},
        pin_functions={pin: pin.rsplit(".", 1)[1] for pin in return_pins},
    )


def cross_symbol_power(
    common: bool = False,
    serial_connected: bool = True,
    usb_function: str = "PWR",
    serial_function: str = "POWER",
) -> NetlistContract:
    if common:
        nets = {"COMMON_SUPPLY": ("J1.1", "J2.1")}
    else:
        nets = {"USB_SUPPLY": ("J1.1",)}
        if serial_connected:
            nets["SERIAL_SUPPLY"] = ("J2.1",)
    return NetlistContract(
        components={},
        nets=nets,
        component_symbols={"J1": "Synthetic:USB-C", "J2": "Synthetic:DB9"},
        pin_functions={"J1.1": usb_function, "J2.1": serial_function},
    )


def three_port_power_pin_drift(common: bool = False) -> NetlistContract:
    """Create sibling generic power contacts with a missing third assignment."""
    if common:
        nets = {"+5V": ("J1.1", "J2.1", "J3.1")}
    else:
        nets = {"+5V_1": ("J1.1",), "5V-2": ("J2.1",)}
    return NetlistContract(
        components={},
        nets=nets,
        component_symbols={
            f"J{reference}": "Synthetic:PeripheralPort" for reference in range(1, 4)
        },
        component_pin_numbers={f"J{reference}": ("1",) for reference in range(1, 4)},
        pin_functions={f"J{reference}.1": "1" for reference in range(1, 4)},
    )


def standard_connector_identity_peers(
    *, common_return: bool = False, supply_connected: bool = False, dnp: tuple[str, ...] = ()
) -> NetlistContract:
    """Use a standard connector symbol with a nonstandard U reference."""
    return_nets = ("J1.1", "U7.1") if common_return else ("J1.1",)
    nets: dict[str, tuple[str, ...]] = {"RETURN_A": ("J1.1",)}
    if common_return:
        nets = {"GND": return_nets}
    else:
        nets["RETURN_B"] = ("U7.1",)
    nets["+5V"] = ("J1.2", "U7.2") if supply_connected else ("J1.2",)
    return NetlistContract(
        components={
            "J1": ComponentContract(value="Port A", footprint="Synthetic:Port"),
            "U7": ComponentContract(value="Port B", footprint="Synthetic:Port"),
        },
        nets=nets,
        dnp_components=dnp,
        component_symbols={
            "J1": "Connector_Generic:Conn_01x03",
            "U7": "Connector_Generic:Conn_01x03",
        },
        component_pin_numbers={"J1": ("1", "2", "3"), "U7": ("1", "2", "3")},
        pin_functions={
            "J1.1": "GND",
            "U7.1": "GND",
            "J1.2": "VBUS",
            "U7.2": "VBUS",
        },
        pin_electrical_types={"J1.2": "power_in", "U7.2": "power_in"},
    )


def custom_reviewed_connector_peers() -> NetlistContract:
    """Use custom symbol IDs and nonstandard references for authored classification."""
    return NetlistContract(
        components={
            "A1": ComponentContract(value="Port A", footprint="Synthetic:Port"),
            "A2": ComponentContract(value="Port B", footprint="Synthetic:Port"),
        },
        nets={"RETURN_A": ("A1.1",), "RETURN_B": ("A2.1",)},
        component_symbols={"A1": "Custom:InterfacePort", "A2": "Custom:InterfacePort"},
        component_pin_numbers={"A1": ("1",), "A2": ("1",)},
        pin_functions={"A1.1": "GND", "A2.1": "GND"},
    )


def peer_connector_pin_assignments(
    pin_two_nets: tuple[str | None, ...] = ("RETURN", "RETURN", None),
    dnp: tuple[str, ...] = (),
) -> NetlistContract:
    """Create exact-symbol peers with pin inventory but missing pin-role metadata."""
    references = tuple(f"J{index}" for index in range(1, len(pin_two_nets) + 1))
    nets: dict[str, tuple[str, ...]] = {
        "COMMON": tuple(f"{reference}.1" for reference in references)
    }
    for reference, net in zip(references, pin_two_nets, strict=True):
        if net is not None:
            nets[net] = (*nets.get(net, ()), f"{reference}.2")
    return NetlistContract(
        components={},
        nets=nets,
        dnp_components=dnp,
        component_symbols={reference: "Synthetic:PeripheralPort" for reference in references},
        component_pin_numbers={reference: ("1", "2") for reference in references},
    )


def led_rail_bridge_netlist(
    *,
    series_resistor: bool = False,
    parallel_resistor: bool = False,
    dnp: tuple[str, ...] = (),
    symbol: str = "Device:LED",
    pin_numbers: tuple[str, ...] = ("1", "2"),
    positive_net: str = "+3V3",
    return_net: str = "GND",
    pin_functions: dict[str, str] | None = None,
) -> NetlistContract:
    components = {"D1": ComponentContract(value="LED", footprint="Synthetic:LED")}
    symbols = {"D1": symbol}
    nets: dict[str, tuple[str, ...]]
    component_pin_numbers = {"D1": pin_numbers}
    if series_resistor:
        components["R1"] = ComponentContract(value="1k", footprint="Synthetic:R")
        symbols["R1"] = "Device:R"
        component_pin_numbers["R1"] = ("1", "2")
        nets = {
            positive_net: ("R1.1",),
            "LED_A": ("D1.1", "R1.2"),
            return_net: ("D1.2",),
        }
    elif parallel_resistor:
        components["R1"] = ComponentContract(value="1k", footprint="Synthetic:R")
        symbols["R1"] = "Device:R"
        component_pin_numbers["R1"] = ("1", "2")
        nets = {
            positive_net: ("D1.1", "R1.1"),
            return_net: ("D1.2", "R1.2"),
        }
    else:
        nets = {positive_net: ("D1.1",), return_net: ("D1.2",)}
    return NetlistContract(
        components=components,
        nets=nets,
        dnp_components=dnp,
        component_symbols=symbols,
        pin_functions=pin_functions or {},
        component_pin_numbers=component_pin_numbers,
    )


def multiconductor_connector(
    return_connected: bool = False, with_shield: bool = False, return_named: bool = True
) -> NetlistContract:
    nets = {
        "DATA_A": ("J1.1",),
        "DATA_B": ("J1.2",),
        "SUPPLY": ("J1.3",),
    }
    pin_functions = {
        "J1.1": "DATA_A",
        "J1.2": "DATA_B",
        "J1.3": "PWR",
        "J1.4": "GND",
    }
    if not return_named:
        pin_functions.pop("J1.4")
    if return_connected:
        nets["GND"] = ("J1.4",)
    if with_shield:
        nets["SHIELD"] = ("J1.5",)
        pin_functions["J1.5"] = "SHIELD"
    return NetlistContract(
        components={},
        nets=nets,
        component_symbols={"J1": "Synthetic:MulticonductorPort"},
        pin_functions=pin_functions,
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


def unconnected_component_power_pins(connected: bool = False) -> NetlistContract:
    nets: dict[str, tuple[str, ...]] = {"DATA": ("U1.3",)}
    if connected:
        nets.update({"+3V3": ("U1.1",), "GND": ("U1.2",)})
    return NetlistContract(
        components={"U1": ComponentContract(value="Logic IC", footprint="")},
        nets=nets,
        component_symbols={"U1": "Synthetic:Logic"},
        pin_functions={"U1.1": "VDD", "U1.2": "GND", "U1.3": "DATA"},
    )


def ic_power_decoupling_fixture(
    *,
    rail: str = "+3V3",
    power_function: str = "VDD",
    electrical_type: str = "power_in",
    capacitor_net: str | None = None,
    capacitor_reference_net: str | None = "GND",
    dnp_capacitor: bool = False,
    dnp_ic: bool = False,
    reference: str = "U1",
) -> NetlistContract:
    power_pin = f"{reference}.1"
    ground_pin = f"{reference}.2"
    nets: dict[str, tuple[str, ...]] = {rail: (power_pin,), "GND": (ground_pin,)}
    components = {reference: ComponentContract(value="Synthetic IC", footprint="")}
    component_symbols = {
        reference: "Synthetic:PowerPort"
        if reference.startswith(("J", "P", "X", "CN"))
        else "Synthetic:Logic"
    }
    pin_functions = {power_pin: power_function, ground_pin: "GND"}
    pin_electrical_types = {power_pin: electrical_type}
    dnp_components: list[str] = [reference] if dnp_ic else []
    if capacitor_net is not None:
        components["C1"] = ComponentContract(value="100n", footprint="")
        component_symbols["C1"] = "Device:C"
        nets[capacitor_net] = (*nets.get(capacitor_net, ()), "C1.1")
        if capacitor_reference_net is not None:
            nets[capacitor_reference_net] = (*nets.get(capacitor_reference_net, ()), "C1.2")
        if dnp_capacitor:
            dnp_components.append("C1")
    return NetlistContract(
        components=components,
        nets=nets,
        dnp_components=tuple(dnp_components),
        component_symbols=component_symbols,
        pin_functions=pin_functions,
        pin_electrical_types=pin_electrical_types,
    )


def repeated_component_supply_pins(
    *,
    split: bool = True,
    second_function: str = "VDD",
    second_pin_assigned: bool = True,
    dnp: bool = False,
) -> NetlistContract:
    nets: dict[str, tuple[str, ...]] = {"+3V3": ("U1.1",)}
    if split and second_pin_assigned:
        nets["+1V8"] = ("U1.2",)
    elif second_pin_assigned:
        nets["+3V3"] = ("U1.1", "U1.2")
    return NetlistContract(
        components={"U1": ComponentContract(value="Synthetic logic", footprint="")},
        nets=nets,
        dnp_components=("U1",) if dnp else (),
        component_symbols={"U1": "Synthetic:MultiSupplyLogic"},
        pin_functions={"U1.1": "VDD", "U1.2": second_function},
    )


def peer_component_power_pins(
    *,
    split_return: bool = True,
    split_supply: bool = True,
    dnp: tuple[str, ...] = (),
) -> NetlistContract:
    """Create exact-symbol component peers with optional return/supply splits."""
    if split_supply:
        supply_nets = {"+3V3": ("U1.1",), "+5V": ("U2.1",)}
    else:
        supply_nets = {"+3V3": ("U1.1", "U2.1")}
    if split_return:
        return_nets = {"GND": ("U1.2",), "AGND": ("U2.2",)}
    else:
        return_nets = {"GND": ("U1.2", "U2.2")}
    return NetlistContract(
        components={
            "U1": ComponentContract(value="Synthetic logic", footprint=""),
            "U2": ComponentContract(value="Synthetic logic", footprint=""),
        },
        nets={**supply_nets, **return_nets},
        dnp_components=dnp,
        component_symbols={
            "U1": "Synthetic:PowerPeer",
            "U2": "Synthetic:PowerPeer",
        },
        pin_functions={
            "U1.1": "VDD",
            "U2.1": "VDD",
            "U1.2": "GND",
            "U2.2": "GND",
        },
        component_pin_numbers={"U1": ("1", "2"), "U2": ("1", "2")},
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


def control_input_pins(
    *, connected: bool = False, dnp: bool = False, visible_bias: bool = True
) -> NetlistContract:
    nets = (
        {
            "RESET_LINE": ("U1.1", "U1.8", "U1.10", "U1.13"),
            "ENABLE_LINE": ("U1.2",),
            "ENABLE_A": ("U1.11",),
            "BOOT_STRAP": ("U1.3", "U1.9", "U1.12"),
        }
        if connected
        else {
            "unconnected-(U1-~{RESET}-Pad1)": ("U1.1",),
            "unconnected-(U1-EN-Pad2)": ("U1.2",),
            "unconnected-(U1-BOOT0-Pad3)": ("U1.3",),
            "unconnected-(U1-RST#-Pad8)": ("U1.8",),
            "unconnected-(U1-BOOT_A-Pad9)": ("U1.9",),
            "unconnected-(U1-IOEXP_RST_N-Pad10)": ("U1.10",),
            "unconnected-(U1-JTAG_EN-Pad11)": ("U1.11",),
            "unconnected-(U1-nRPIBOOT-Pad12)": ("U1.12",),
            "unconnected-(U1-PERST-Pad13)": ("U1.13",),
        }
    )
    components = {"U1": ComponentContract(value="Synthetic controller", footprint="")}
    component_symbols = {"U1": "Synthetic:Controller"}
    component_pin_numbers = {
        "U1": ("1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13")
    }
    if connected and visible_bias:
        nets = dict(nets)
        for index, signal_net in enumerate(
            ("RESET_LINE", "ENABLE_LINE", "ENABLE_A", "BOOT_STRAP"), start=1
        ):
            reference = f"R{index}"
            nets[signal_net] = (*nets[signal_net], f"{reference}.1")
            nets["+3V3"] = (*nets.get("+3V3", ()), f"{reference}.2")
            components[reference] = ComponentContract(value="10k", footprint="Device:R")
            component_symbols[reference] = "Device:R"
            component_pin_numbers[reference] = ("1", "2")
    return NetlistContract(
        components=components,
        nets=nets,
        dnp_components=("U1",) if dnp else (),
        component_symbols=component_symbols,
        pin_functions={
            "U1.1": "~{RESET}",
            "U1.2": "EN",
            "U1.3": "BOOT0",
            "U1.4": "GPIO",
            "U1.5": "RESET",
            "U1.6": "BOOT1",
            "U1.7": "RST",
            "U1.8": "RST#",
            "U1.9": "BOOT_A",
            "U1.10": "IOEXP_RST_N",
            "U1.11": "JTAG_EN",
            "U1.12": "nRPIBOOT",
            "U1.13": "PERST",
        },
        pin_electrical_types={
            "U1.1": "input",
            "U1.2": "input",
            "U1.3": "input_low",
            "U1.4": "input",
            "U1.5": "passive",
            "U1.7": "output",
            "U1.8": "input",
            "U1.9": "input_low",
            "U1.10": "input",
            "U1.11": "input",
            "U1.12": "input",
            "U1.13": "input",
        },
        component_pin_numbers=component_pin_numbers,
    )


def with_control_resistor(
    netlist: NetlistContract,
    *,
    signal_net: str,
    rail_net: str,
    reference: str = "R1",
    value: str = "10k",
) -> NetlistContract:
    nets = dict(netlist.nets)
    nets[signal_net] = (*nets.get(signal_net, ()), f"{reference}.1")
    nets[rail_net] = (*nets.get(rail_net, ()), f"{reference}.2")
    components = dict(netlist.components)
    components[reference] = ComponentContract(value=value, footprint="Device:R")
    component_symbols = dict(netlist.component_symbols)
    component_symbols[reference] = "Device:R"
    component_pin_numbers = dict(netlist.component_pin_numbers)
    component_pin_numbers[reference] = ("1", "2")
    return netlist.model_copy(
        update={
            "nets": nets,
            "components": components,
            "component_symbols": component_symbols,
            "component_pin_numbers": component_pin_numbers,
        }
    )


def coach(netlist: NetlistContract, netlist_sha256: str = "a" * 64) -> ContractCoachReport:
    return ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-ports",
        observed=netlist,
        netlist_sha256=netlist_sha256,
    )


def spi_peer_voltage_netlist(
    *,
    output_rail: str = "+5V",
    input_rail: str = "+3V3",
    input_extra_supply: bool = False,
    unconnected_input_supply: bool = False,
    missing_pin_types: bool = False,
    signal_function: str = "MOSI",
    all_signal_function: str | None = None,
    output_type: str = "output",
    input_type: str = "input",
    dnp: tuple[str, ...] = (),
    level_shifted: bool = False,
) -> NetlistContract:
    """Build synthetic SPI endpoints and direct-peer boundary controls."""
    components = {
        "U1": ComponentContract(value="Synthetic controller", footprint="Package:Controller"),
        "U2": ComponentContract(value="Synthetic peripheral", footprint="Package:Peripheral"),
    }
    component_pin_numbers = {
        "U1": ("1", "2", "8", "9"),
        "U2": ("1", "2", "8", *(("10",) if input_extra_supply else ()), "9"),
    }
    pin_functions = {
        "U1.1": all_signal_function or "SCK",
        "U1.2": all_signal_function or signal_function,
        "U1.8": "VDD",
        "U1.9": "GND",
        "U2.1": all_signal_function or "SCK",
        "U2.2": all_signal_function or signal_function,
        "U2.8": "VDD",
        "U2.9": "GND",
    }
    pin_electrical_types = {
        "U1.1": output_type,
        "U1.2": output_type,
        "U1.8": "power_in",
        "U1.9": "power_in",
        "U2.1": input_type,
        "U2.2": input_type,
        "U2.8": "power_in",
        "U2.9": "power_in",
    }
    if level_shifted:
        components["U3"] = ComponentContract(
            value="Synthetic dual-supply translator", footprint="Package:Translator"
        )
        component_symbols = {
            "U1": "Synthetic:Controller",
            "U2": "Synthetic:Peripheral",
            "U3": "Synthetic:LevelTranslator",
        }
        component_pin_numbers["U3"] = ("1", "2", "3", "4", "5", "6", "7")
        pin_functions.update(
            {
                "U3.1": "A_SCK",
                "U3.2": "B_SCK",
                "U3.3": "A_MOSI",
                "U3.4": "B_MOSI",
                "U3.5": "VCCA",
                "U3.6": "VCCB",
                "U3.7": "GND",
            }
        )
        pin_electrical_types.update(
            {
                "U3.1": "input",
                "U3.2": "output",
                "U3.3": "input",
                "U3.4": "output",
                "U3.5": "power_in",
                "U3.6": "power_in",
                "U3.7": "power_in",
            }
        )
    else:
        component_symbols = {
            "U1": "Synthetic:Controller",
            "U2": "Synthetic:Peripheral",
        }
    nets: dict[str, tuple[str, ...]] = {
        output_rail: ("U1.8", *(("U3.5",) if level_shifted else ())),
        "GND": ("U1.9", "U2.9", *(("U3.7",) if level_shifted else ())),
    }
    if level_shifted:
        nets.update(
            {
                input_rail: ("U2.8", "U3.6"),
                "SPI_SCK_CONTROLLER": ("U1.1", "U3.1"),
                "SPI_SCK_PERIPHERAL": ("U3.2", "U2.1"),
                "SPI_MOSI_CONTROLLER": ("U1.2", "U3.3"),
                "SPI_MOSI_PERIPHERAL": ("U3.4", "U2.2"),
            }
        )
    else:
        nets.update(
            {
                "SPI_SCK": ("U1.1", "U2.1"),
                "SPI_MOSI": ("U1.2", "U2.2"),
            }
        )
    if not unconnected_input_supply and "U2.8" not in nets.get(input_rail, ()):
        nets[input_rail] = (*nets.get(input_rail, ()), "U2.8")
    if input_extra_supply:
        pin_functions["U2.10"] = "VDDIO"
        pin_electrical_types["U2.10"] = "power_in"
        nets["+1V8"] = ("U2.10",)
    if missing_pin_types:
        pin_electrical_types = {}
    return NetlistContract(
        components=components,
        nets=nets,
        dnp_components=dnp,
        component_symbols=component_symbols,
        pin_functions=pin_functions,
        pin_electrical_types=pin_electrical_types,
        component_pin_numbers=component_pin_numbers,
    )


def spi_peer_voltage_map(
    pins: tuple[tuple[str, str], ...] = (("U1.1", "U2.1"),),
    *,
    with_limits: bool = True,
    receiver_absolute_maximum_v: float = 3.6,
) -> DigitalPeerVoltageAnalysis:
    links = []
    for index, (output_pin, input_pin) in enumerate(pins, start=1):
        net = "SPI_SCK" if output_pin.endswith(".1") else "SPI_MOSI"
        links.append(
            DigitalPeerVoltageLink(
                id=f"spi-peer-{index}",
                basis="Synthetic exact SPI peer map with datasheet limits",
                driver=DigitalPeerPinRequirement(
                    reference="U1",
                    symbol="Synthetic:Controller",
                    footprint="Package:Controller",
                    pin=output_pin,
                    net=net,
                ),
                receiver=DigitalPeerPinRequirement(
                    reference="U2",
                    symbol="Synthetic:Peripheral",
                    footprint="Package:Peripheral",
                    pin=input_pin,
                    net=net,
                ),
                output_limits=(
                    DigitalLogicOutputLimits(
                        low_minimum_v=0.0,
                        low_maximum_v=0.4,
                        high_minimum_v=2.4,
                        high_maximum_v=5.0,
                        source="Synthetic controller datasheet Rev A, Table 8",
                        conditions="VDD=5 V, stated load, full temperature range",
                    )
                    if with_limits
                    else None
                ),
                input_limits=(
                    DigitalLogicInputLimits(
                        absolute_minimum_v=-0.3,
                        low_maximum_v=0.8,
                        high_minimum_v=2.0,
                        absolute_maximum_v=receiver_absolute_maximum_v,
                        source="Synthetic peripheral datasheet Rev B, Table 4",
                        conditions="VDD=3.3 V, full temperature range",
                    )
                    if with_limits
                    else None
                ),
            )
        )
    return DigitalPeerVoltageAnalysis(
        basis="Synthetic exact direct-peer voltage map for lint control coverage",
        links=tuple(links),
    )


def serial_peer_voltage_netlist(
    *,
    output_rail: str = "+5V",
    input_rail: str = "+3V3",
    output_function: str = "UART1_TX",
    input_function: str = "UART1_RX",
    output_type: str = "output",
    input_type: str = "input",
    input_extra_supply: bool = False,
    unconnected_input_supply: bool = False,
    missing_pin_types: bool = False,
    dnp: tuple[str, ...] = (),
) -> NetlistContract:
    """Build two synthetic UART endpoints and source-bound evidence controls."""
    u2_numbers = ("1", "8", *(("10",) if input_extra_supply else ()), "9")
    pin_functions = {
        "U1.1": output_function,
        "U1.8": "VDD",
        "U1.9": "GND",
        "U2.1": input_function,
        "U2.8": "VDD",
        "U2.9": "GND",
    }
    pin_types = {
        "U1.1": output_type,
        "U1.8": "power_in",
        "U1.9": "power_in",
        "U2.1": input_type,
        "U2.8": "power_in",
        "U2.9": "power_in",
    }
    nets: dict[str, tuple[str, ...]] = {
        "UART_TX": ("U1.1", "U2.1"),
        output_rail: ("U1.8",),
        "GND": ("U1.9", "U2.9"),
    }
    if not unconnected_input_supply:
        nets[input_rail] = (*nets.get(input_rail, ()), "U2.8")
    if input_extra_supply:
        pin_functions["U2.10"] = "VDDIO"
        pin_types["U2.10"] = "power_in"
        nets["+1V8"] = ("U2.10",)
    if missing_pin_types:
        pin_types = {}
    return NetlistContract(
        components={
            "U1": ComponentContract(
                value="Synthetic UART transmitter", footprint="Package:UART-TX"
            ),
            "U2": ComponentContract(value="Synthetic UART receiver", footprint="Package:UART-RX"),
        },
        nets=nets,
        dnp_components=dnp,
        component_symbols={
            "U1": "Synthetic:UartTransmitter",
            "U2": "Synthetic:UartReceiver",
        },
        pin_functions=pin_functions,
        pin_electrical_types=pin_types,
        component_pin_numbers={"U1": ("1", "8", "9"), "U2": u2_numbers},
    )


def serial_peer_voltage_translator_netlist() -> NetlistContract:
    """Model a UART link whose endpoints meet only through a level translator."""
    return NetlistContract(
        components={
            "U1": ComponentContract(
                value="Synthetic UART transmitter", footprint="Package:UART-TX"
            ),
            "U2": ComponentContract(value="Synthetic UART receiver", footprint="Package:UART-RX"),
            "U3": ComponentContract(
                value="Synthetic UART level translator", footprint="Package:UART-XLAT"
            ),
        },
        nets={
            "UART_A_TX": ("U1.1", "U3.1"),
            "UART_B_TX": ("U3.2", "U2.1"),
            "+5V": ("U1.8", "U3.3"),
            "+3V3": ("U2.8", "U3.4"),
            "GND": ("U1.9", "U2.9", "U3.5"),
        },
        component_symbols={
            "U1": "Synthetic:UartTransmitter",
            "U2": "Synthetic:UartReceiver",
            "U3": "Synthetic:UartLevelTranslator",
        },
        pin_functions={
            "U1.1": "UART1_TX",
            "U1.8": "VDD",
            "U1.9": "GND",
            "U2.1": "UART1_RX",
            "U2.8": "VDD",
            "U2.9": "GND",
            "U3.1": "A_TX",
            "U3.2": "B_RX",
            "U3.3": "VCCA",
            "U3.4": "VCCB",
            "U3.5": "GND",
        },
        pin_electrical_types={
            "U1.1": "output",
            "U1.8": "power_in",
            "U1.9": "power_in",
            "U2.1": "input",
            "U2.8": "power_in",
            "U2.9": "power_in",
            "U3.1": "input",
            "U3.2": "output",
            "U3.3": "power_in",
            "U3.4": "power_in",
            "U3.5": "power_in",
        },
        component_pin_numbers={
            "U1": ("1", "8", "9"),
            "U2": ("1", "8", "9"),
            "U3": ("1", "2", "3", "4", "5"),
        },
    )


def serial_peer_voltage_map(*, with_limits: bool = True) -> DigitalPeerVoltageAnalysis:
    return DigitalPeerVoltageAnalysis(
        basis="Synthetic exact UART peer map with datasheet limits",
        links=(
            DigitalPeerVoltageLink(
                id="uart-tx-rx",
                basis="Controller TX directly drives receiver RX",
                driver=DigitalPeerPinRequirement(
                    reference="U1",
                    symbol="Synthetic:UartTransmitter",
                    footprint="Package:UART-TX",
                    pin="U1.1",
                    net="UART_TX",
                ),
                receiver=DigitalPeerPinRequirement(
                    reference="U2",
                    symbol="Synthetic:UartReceiver",
                    footprint="Package:UART-RX",
                    pin="U2.1",
                    net="UART_TX",
                ),
                output_limits=(
                    DigitalLogicOutputLimits(
                        low_minimum_v=0.0,
                        low_maximum_v=0.4,
                        high_minimum_v=2.4,
                        high_maximum_v=5.0,
                        source="Synthetic controller datasheet Rev A, Table 8",
                        conditions="VDD=5 V, stated load, full temperature range",
                    )
                    if with_limits
                    else None
                ),
                input_limits=(
                    DigitalLogicInputLimits(
                        absolute_minimum_v=-0.3,
                        low_maximum_v=0.8,
                        high_minimum_v=2.0,
                        absolute_maximum_v=3.6,
                        source="Synthetic receiver datasheet Rev B, Table 4",
                        conditions="VDD=3.3 V, full temperature range",
                    )
                    if with_limits
                    else None
                ),
            ),
        ),
    )


def header_only_spi_uart_netlist() -> NetlistContract:
    """Model external bus headers that are not direct on-board IC peers."""
    references = ("J1", "J2")
    pin_numbers = ("1", "2", "3", "4", "5", "6")
    nets = {
        "SPI_SCK": ("J1.1", "J2.1"),
        "SPI_MOSI": ("J1.2", "J2.2"),
        "UART0_TX": ("J1.3", "J2.3"),
        "UART0_RX": ("J1.4", "J2.4"),
        "+5V": ("J1.5",),
        "+3V3": ("J2.5",),
        "GND": ("J1.6", "J2.6"),
    }
    pin_functions = {
        "J1.1": "SCK",
        "J1.2": "MOSI",
        "J1.3": "UART0_TX",
        "J1.4": "UART0_RX",
        "J1.5": "VCC",
        "J1.6": "GND",
        "J2.1": "SCK",
        "J2.2": "MOSI",
        "J2.3": "UART0_TX",
        "J2.4": "UART0_RX",
        "J2.5": "VCC",
        "J2.6": "GND",
    }
    electrical_types = {
        "J1.1": "output",
        "J1.2": "output",
        "J1.3": "output",
        "J1.4": "input",
        "J1.5": "power_in",
        "J1.6": "power_in",
        "J2.1": "input",
        "J2.2": "input",
        "J2.3": "input",
        "J2.4": "output",
        "J2.5": "power_in",
        "J2.6": "power_in",
    }
    return NetlistContract(
        components={
            reference: ComponentContract(
                value="External bus header",
                footprint="Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical",
            )
            for reference in references
        },
        nets=nets,
        component_symbols={reference: "Synthetic:ExternalBusHeader" for reference in references},
        pin_functions=pin_functions,
        pin_electrical_types=electrical_types,
        component_pin_numbers={reference: pin_numbers for reference in references},
    )


class DesignLintTests(unittest.TestCase):
    def test_spi_peer_voltage_prompt_requires_unambiguous_native_evidence(self) -> None:
        source = spi_peer_voltage_netlist()
        findings = [
            item for item in candidates(source) if item.rule_id == "bus.spi_peer_voltage_review"
        ]
        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual(
            finding.subject,
            "U1 -> U2: SPI voltage-domain review",
        )
        self.assertEqual(finding.evidence["output_supply_net"], ("+5V",))
        self.assertEqual(finding.evidence["output_supply_label_value"], ("5 V",))
        self.assertEqual(finding.evidence["input_supply_net"], ("+3V3",))
        self.assertEqual(finding.evidence["input_supply_label_value"], ("3.3 V",))
        self.assertEqual(len(finding.evidence["shared_SPI_pin_assignments"]), 2)
        self.assertIn("does not establish incompatibility", finding.message)

        controls = {
            "same named rail": spi_peer_voltage_netlist(output_rail="+3V3", input_rail="+3V3"),
            "DNP receiver": spi_peer_voltage_netlist(dnp=("U2",)),
            "missing native pin types": spi_peer_voltage_netlist(missing_pin_types=True),
            "unconnected receiver supply": spi_peer_voltage_netlist(unconnected_input_supply=True),
            "multiple receiver supplies": spi_peer_voltage_netlist(input_extra_supply=True),
            "level-shifted peer path": spi_peer_voltage_netlist(level_shifted=True),
            "unrecognized signal functions": spi_peer_voltage_netlist(
                all_signal_function="ANALOG_IN"
            ),
            "open-collector signal": spi_peer_voltage_netlist(output_type="open_collector"),
            "input-only peers": spi_peer_voltage_netlist(output_type="input"),
            "negative supply label": spi_peer_voltage_netlist(output_rail="-5V"),
            "ambiguous supply label": spi_peer_voltage_netlist(output_rail="SUPPLY_5V_1V8"),
        }
        for label, control in controls.items():
            with self.subTest(control=label):
                self.assertNotIn(
                    "bus.spi_peer_voltage_review",
                    {item.rule_id for item in candidates(control)},
                )

    def test_peer_voltage_coverage_distinguishes_evaluated_and_incomplete_scope(self) -> None:
        fault = evaluate("peer-voltage", coach(spi_peer_voltage_netlist()), DesignLintPolicy())
        spi = next(
            item
            for item in fault.digital_peer_voltage_coverage
            if item.rule_id == "bus.spi_peer_voltage_review"
        )
        self.assertEqual(
            (
                spi.status,
                spi.recognized_endpoint_count,
                spi.assigned_endpoint_count,
                spi.direct_peer_link_count,
                spi.voltage_comparison_count,
                spi.same_voltage_link_count,
                spi.different_voltage_link_count,
                spi.candidate_group_count,
            ),
            ("EVALUATED", 4, 4, 2, 2, 0, 2, 1),
        )

        same_rail = evaluate(
            "peer-voltage",
            coach(spi_peer_voltage_netlist(output_rail="+3V3", input_rail="+3V3")),
            DesignLintPolicy(),
        )
        same_rail_spi = next(
            item
            for item in same_rail.digital_peer_voltage_coverage
            if item.rule_id == "bus.spi_peer_voltage_review"
        )
        self.assertEqual(
            (
                same_rail_spi.status,
                same_rail_spi.voltage_comparison_count,
                same_rail_spi.same_voltage_link_count,
                same_rail_spi.different_voltage_link_count,
                same_rail_spi.candidate_group_count,
            ),
            ("EVALUATED", 2, 2, 0, 0),
        )

        incomplete = evaluate(
            "peer-voltage",
            coach(spi_peer_voltage_netlist(missing_pin_types=True)),
            DesignLintPolicy(),
        )
        incomplete_spi = next(
            item
            for item in incomplete.digital_peer_voltage_coverage
            if item.rule_id == "bus.spi_peer_voltage_review"
        )
        self.assertEqual(
            (
                incomplete_spi.status,
                incomplete_spi.recognized_endpoint_count,
                incomplete_spi.assigned_endpoint_count,
                incomplete_spi.direct_peer_link_count,
            ),
            ("INCOMPLETE", 4, 0, 0),
        )

        unsupported = evaluate(
            "peer-voltage",
            coach(spi_peer_voltage_netlist(all_signal_function="ANALOG_IN")),
            DesignLintPolicy(),
        )
        unsupported_spi = next(
            item
            for item in unsupported.digital_peer_voltage_coverage
            if item.rule_id == "bus.spi_peer_voltage_review"
        )
        self.assertEqual(unsupported_spi.status, "NO_SUPPORTED_ENDPOINTS")

        mapped = evaluate(
            "peer-voltage",
            coach(serial_peer_voltage_netlist()),
            DesignLintPolicy(),
            digital_peer_voltage_context=DigitalPeerVoltageLintContext(
                state="required",
                analysis=serial_peer_voltage_map(),
            ),
        )
        mapped_serial = next(
            item
            for item in mapped.digital_peer_voltage_coverage
            if item.rule_id == "bus.serial_peer_voltage_review"
        )
        self.assertEqual(
            (
                mapped_serial.status,
                mapped_serial.authored_map_state,
                mapped_serial.direct_peer_link_count,
                mapped_serial.voltage_comparison_count,
                mapped_serial.different_voltage_link_count,
                mapped_serial.mapped_mismatch_link_count,
                mapped_serial.candidate_group_count,
            ),
            ("EVALUATED", "required", 1, 1, 1, 1, 0),
        )

        report_text = text_report(fault)
        self.assertIn("Direct SPI/UART peer-voltage heuristic coverage:", report_text)
        self.assertIn("2 voltage comparison(s)", report_text)

    def test_spi_peer_voltage_prompt_suppresses_translator_separated_paths(self) -> None:
        source = spi_peer_voltage_netlist(level_shifted=True)

        self.assertEqual(source.nets["SPI_SCK_CONTROLLER"], ("U1.1", "U3.1"))
        self.assertEqual(source.nets["SPI_SCK_PERIPHERAL"], ("U3.2", "U2.1"))
        self.assertEqual(source.nets["+5V"], ("U1.8", "U3.5"))
        self.assertEqual(source.nets["+3V3"], ("U2.8", "U3.6"))
        self.assertNotIn(
            "bus.spi_peer_voltage_review",
            {item.rule_id for item in candidates(source)},
        )

    def test_peer_voltage_coverage_excludes_header_only_spi_and_uart_endpoints(self) -> None:
        external_interfaces = header_only_spi_uart_netlist()

        report = evaluate(
            "synthetic-external-buses", coach(external_interfaces), DesignLintPolicy()
        )
        peer_coverage = {item.rule_id: item for item in report.digital_peer_voltage_coverage}
        self.assertEqual(
            {
                rule_id: (
                    item.status,
                    item.recognized_endpoint_count,
                    item.direct_peer_link_count,
                    item.voltage_comparison_count,
                    item.candidate_group_count,
                )
                for rule_id, item in peer_coverage.items()
            },
            {
                "bus.spi_peer_voltage_review": ("NO_SUPPORTED_ENDPOINTS", 0, 0, 0, 0),
                "bus.serial_peer_voltage_review": ("NO_SUPPORTED_ENDPOINTS", 0, 0, 0, 0),
            },
        )
        self.assertEqual(
            {
                item.rule_id
                for item in report.findings
                if item.rule_id in {"bus.spi_peer_voltage_review", "bus.serial_peer_voltage_review"}
            },
            set(),
        )

    def test_spi_peer_voltage_prompt_suppresses_only_exact_fully_mapped_links(self) -> None:
        source = spi_peer_voltage_netlist()
        incomplete = spi_peer_voltage_map(with_limits=False)
        still_open = [
            item
            for item in candidates(
                source,
                digital_peer_voltage_context=DigitalPeerVoltageLintContext(
                    state="required", analysis=incomplete
                ),
            )
            if item.rule_id == "bus.spi_peer_voltage_review"
        ]
        self.assertEqual(len(still_open), 1)
        self.assertEqual(len(still_open[0].evidence["shared_SPI_pin_assignments"]), 2)

        one_mapped = spi_peer_voltage_map()
        remaining = [
            item
            for item in candidates(
                source,
                digital_peer_voltage_context=DigitalPeerVoltageLintContext(
                    state="required", analysis=one_mapped
                ),
            )
            if item.rule_id == "bus.spi_peer_voltage_review"
        ]
        self.assertEqual(len(remaining), 1)
        self.assertEqual(
            remaining[0].evidence["shared_SPI_pin_assignments"],
            ("SPI_MOSI: U1.2 (MOSI, output) -> U2.2 (MOSI, input)",),
        )

        all_mapped = spi_peer_voltage_map(
            (("U1.1", "U2.1"), ("U1.2", "U2.2")),
            receiver_absolute_maximum_v=5.5,
        )
        self.assertNotIn(
            "bus.spi_peer_voltage_review",
            {
                item.rule_id
                for item in candidates(
                    source,
                    digital_peer_voltage_context=DigitalPeerVoltageLintContext(
                        state="required", analysis=all_mapped
                    ),
                )
            },
        )

        stale_link = one_mapped.links[0].model_copy(
            update={
                "receiver": one_mapped.links[0].receiver.model_copy(
                    update={"footprint": "Other:Part"}
                )
            }
        )
        stale_map = one_mapped.model_copy(update={"links": (stale_link,)})
        self.assertIn(
            "bus.spi_peer_voltage_review",
            {
                item.rule_id
                for item in candidates(
                    source,
                    digital_peer_voltage_context=DigitalPeerVoltageLintContext(
                        state="required", analysis=stale_map
                    ),
                )
            },
        )

    def test_spi_peer_voltage_prompt_is_stable_and_project_configurable(self) -> None:
        source = spi_peer_voltage_netlist()
        reordered = source.model_copy(
            update={
                "nets": dict(reversed(tuple(source.nets.items()))),
                "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
                "pin_electrical_types": dict(reversed(tuple(source.pin_electrical_types.items()))),
                "component_pin_numbers": {
                    reference: tuple(reversed(numbers))
                    for reference, numbers in source.component_pin_numbers.items()
                },
            }
        )
        initial = next(
            item for item in candidates(source) if item.rule_id == "bus.spi_peer_voltage_review"
        )
        reordered_finding = next(
            item for item in candidates(reordered) if item.rule_id == "bus.spi_peer_voltage_review"
        )
        self.assertEqual(fingerprint(initial), fingerprint(reordered_finding))

        default = evaluate("spi-voltage", coach(source), DesignLintPolicy())
        open_finding = next(
            item for item in default.findings if item.rule_id == "bus.spi_peer_voltage_review"
        )
        self.assertEqual(
            (default.status, open_finding.mode, open_finding.disposition),
            ("REVIEW", "review", "OPEN"),
        )

        off_policy = DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="bus.spi_peer_voltage_review",
                    mode="off",
                    reason="This synthetic project explicitly accepts rail-name prompts as inapplicable",
                ),
            )
        )
        off = evaluate("spi-voltage", coach(source), off_policy)
        off_finding = next(
            item for item in off.findings if item.rule_id == "bus.spi_peer_voltage_review"
        )
        self.assertEqual(off_finding.disposition, "RULE_OFF")

        block_policy = DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="bus.spi_peer_voltage_review",
                    mode="block",
                    reason="Synthetic project illustrates explicit owner escalation",
                ),
            )
        )
        blocked = evaluate("spi-voltage", coach(source), block_policy)
        self.assertEqual(blocked.status, "FAIL")

        ignored_policy = DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=open_finding.rule_id,
                    fingerprint=open_finding.fingerprint,
                    reason="Synthetic control records this exact reviewed rail pair",
                ),
            )
        )
        ignored = evaluate("spi-voltage", coach(source), ignored_policy)
        ignored_finding = next(
            item for item in ignored.findings if item.rule_id == "bus.spi_peer_voltage_review"
        )
        self.assertEqual(ignored_finding.disposition, "IGNORED")

    def test_serial_peer_voltage_prompt_requires_matching_role_and_unambiguous_native_evidence(
        self,
    ) -> None:
        source = serial_peer_voltage_netlist()
        findings = [
            item for item in candidates(source) if item.rule_id == "bus.serial_peer_voltage_review"
        ]
        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual(finding.subject, "U1 -> U2: serial voltage-domain review")
        self.assertEqual(finding.evidence["output_supply_net"], ("+5V",))
        self.assertEqual(finding.evidence["output_supply_label_value"], ("5 V",))
        self.assertEqual(finding.evidence["input_supply_net"], ("+3V3",))
        self.assertEqual(finding.evidence["input_supply_label_value"], ("3.3 V",))
        self.assertEqual(
            finding.evidence["shared_serial_pin_assignments"],
            ("UART_TX: U1.1 (UART1_TX, output) -> U2.1 (UART1_RX, input)",),
        )
        self.assertIn("does not establish incompatibility", finding.message)

        controls = {
            "same rail": serial_peer_voltage_netlist(output_rail="+3V3", input_rail="+3V3"),
            "level-translated TX path": serial_peer_voltage_translator_netlist(),
            "DNP receiver": serial_peer_voltage_netlist(dnp=("U2",)),
            "missing native pin types": serial_peer_voltage_netlist(missing_pin_types=True),
            "unconnected receiver supply": serial_peer_voltage_netlist(
                unconnected_input_supply=True
            ),
            "multiple receiver supplies": serial_peer_voltage_netlist(input_extra_supply=True),
            "TX function on receiver": serial_peer_voltage_netlist(input_function="UART1_TX"),
            "RX function on driver": serial_peer_voltage_netlist(output_function="UART1_RX"),
            "input-only TX": serial_peer_voltage_netlist(output_type="input"),
            "open-collector TX": serial_peer_voltage_netlist(output_type="open_collector"),
            "negative supply": serial_peer_voltage_netlist(output_rail="-5V"),
            "ambiguous supply": serial_peer_voltage_netlist(output_rail="SUPPLY_5V_1V8"),
        }
        for label, control in controls.items():
            with self.subTest(control=label):
                self.assertNotIn(
                    "bus.serial_peer_voltage_review",
                    {item.rule_id for item in candidates(control)},
                )

    def test_serial_peer_voltage_prompt_suppresses_only_exact_fully_mapped_links(self) -> None:
        source = serial_peer_voltage_netlist()
        incomplete = serial_peer_voltage_map(with_limits=False)
        still_open = [
            item
            for item in candidates(
                source,
                digital_peer_voltage_context=DigitalPeerVoltageLintContext(
                    state="required", analysis=incomplete
                ),
            )
            if item.rule_id == "bus.serial_peer_voltage_review"
        ]
        self.assertEqual(len(still_open), 1)

        mapped = serial_peer_voltage_map()
        self.assertNotIn(
            "bus.serial_peer_voltage_review",
            {
                item.rule_id
                for item in candidates(
                    source,
                    digital_peer_voltage_context=DigitalPeerVoltageLintContext(
                        state="required", analysis=mapped
                    ),
                )
            },
        )

        stale_link = mapped.links[0].model_copy(
            update={
                "receiver": mapped.links[0].receiver.model_copy(update={"footprint": "Other:Part"})
            }
        )
        stale_map = mapped.model_copy(update={"links": (stale_link,)})
        self.assertIn(
            "bus.serial_peer_voltage_review",
            {
                item.rule_id
                for item in candidates(
                    source,
                    digital_peer_voltage_context=DigitalPeerVoltageLintContext(
                        state="required", analysis=stale_map
                    ),
                )
            },
        )

    def test_serial_peer_voltage_prompt_is_stable_and_project_configurable(self) -> None:
        source = serial_peer_voltage_netlist()
        reordered = source.model_copy(
            update={
                "nets": dict(reversed(tuple(source.nets.items()))),
                "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
                "pin_electrical_types": dict(reversed(tuple(source.pin_electrical_types.items()))),
                "component_pin_numbers": {
                    reference: tuple(reversed(numbers))
                    for reference, numbers in source.component_pin_numbers.items()
                },
            }
        )
        initial = next(
            item for item in candidates(source) if item.rule_id == "bus.serial_peer_voltage_review"
        )
        reordered_finding = next(
            item
            for item in candidates(reordered)
            if item.rule_id == "bus.serial_peer_voltage_review"
        )
        self.assertEqual(fingerprint(initial), fingerprint(reordered_finding))

        default = evaluate("serial-voltage", coach(source), DesignLintPolicy())
        finding = next(
            item for item in default.findings if item.rule_id == "bus.serial_peer_voltage_review"
        )
        self.assertEqual(
            (default.status, finding.mode, finding.disposition), ("REVIEW", "review", "OPEN")
        )

        off = evaluate(
            "serial-voltage",
            coach(source),
            DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id="bus.serial_peer_voltage_review",
                        mode="off",
                        reason="Synthetic owner decision disables this review prompt",
                    ),
                )
            ),
        )
        off_finding = next(
            item for item in off.findings if item.rule_id == "bus.serial_peer_voltage_review"
        )
        self.assertEqual(off_finding.disposition, "RULE_OFF")

        blocked = evaluate(
            "serial-voltage",
            coach(source),
            DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id="bus.serial_peer_voltage_review",
                        mode="block",
                        reason="Synthetic owner decision explicitly escalates this prompt",
                    ),
                )
            ),
        )
        self.assertEqual(blocked.status, "FAIL")

        ignored = evaluate(
            "serial-voltage",
            coach(source),
            DesignLintPolicy(
                ignores=(
                    DesignLintIgnore(
                        rule_id=finding.rule_id,
                        fingerprint=finding.fingerprint,
                        reason="Synthetic exact reviewed rail pair",
                    ),
                )
            ),
        )
        ignored_finding = next(
            item for item in ignored.findings if item.rule_id == "bus.serial_peer_voltage_review"
        )
        self.assertEqual(ignored_finding.disposition, "IGNORED")

    def test_connector_capacitor_only_net_requests_dc_reference_review(self) -> None:
        source = connector_capacitor_only_netlist()
        candidates_for_net = [
            item
            for item in candidates(source)
            if item.rule_id == "net.connector_capacitor_only_no_dc_anchor"
        ]
        self.assertEqual(len(candidates_for_net), 1)
        candidate = candidates_for_net[0]
        self.assertEqual(candidate.subject, "ANALOG_IN: connector/capacitor-only net")
        self.assertEqual(candidate.evidence["connector_pins"], ("J1.1",))
        self.assertEqual(candidate.evidence["capacitor_pins"], ("C1.1",))
        self.assertIn("off-board source", candidate.message)
        self.assertIn("does not trace a complete DC path", candidate.message)

        report = evaluate("synthetic-dc-reference", coach(source), DesignLintPolicy())
        finding = next(
            item
            for item in report.findings
            if item.rule_id == "net.connector_capacitor_only_no_dc_anchor"
        )
        self.assertEqual(report.status, "REVIEW")
        self.assertEqual(finding.mode, "review")
        self.assertEqual(finding.disposition, "OPEN")

    def test_connector_capacitor_only_prompt_requires_fitted_known_peer_pins(self) -> None:
        cases = (
            (connector_capacitor_only_netlist(dnp=("C1",)), False),
            (connector_capacitor_only_netlist(dnp=("J1",)), False),
            (connector_capacitor_only_netlist(extra_signal_pin=True), False),
            (
                connector_capacitor_only_netlist().model_copy(
                    update={
                        "component_symbols": {
                            "J1": "Device:R",
                            "C1": "Device:C",
                        }
                    }
                ),
                False,
            ),
            (
                connector_capacitor_only_netlist().model_copy(
                    update={"nets": {"ANALOG_IN": ("C1.1",), "GND": ("C1.2",)}}
                ),
                False,
            ),
            (
                connector_capacitor_only_netlist().model_copy(
                    update={
                        "nets": {
                            "ANALOG_IN": ("J1.1", "C1.1"),
                            "GND": ("J1.2", "C1.2"),
                        },
                        "pin_functions": {"J1.1": "GND"},
                    }
                ),
                False,
            ),
        )
        for source, expected in cases:
            with self.subTest(dnp=source.dnp_components, nets=source.nets):
                found = {
                    item.rule_id
                    for item in candidates(source)
                    if item.rule_id == "net.connector_capacitor_only_no_dc_anchor"
                }
                self.assertEqual(bool(found), expected)

    def test_connector_capacitor_only_prompt_supports_project_policy_and_ignore(self) -> None:
        source = connector_capacitor_only_netlist()
        initial = evaluate("synthetic-dc-reference-policy", coach(source), DesignLintPolicy())
        finding = next(
            item
            for item in initial.findings
            if item.rule_id == "net.connector_capacitor_only_no_dc_anchor"
        )
        blocked = evaluate(
            "synthetic-dc-reference-policy",
            coach(source),
            DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id="net.connector_capacitor_only_no_dc_anchor",
                        mode="block",
                        reason="Synthetic project requires local DC-reference review",
                    ),
                )
            ),
        )
        self.assertEqual(blocked.status, "FAIL")

        disabled = evaluate(
            "synthetic-dc-reference-policy",
            coach(source),
            DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id="net.connector_capacitor_only_no_dc_anchor",
                        mode="off",
                        reason="Synthetic interface is biased by its external source",
                    ),
                )
            ),
        )
        self.assertEqual(disabled.status, "PASS")
        self.assertEqual(
            next(
                item
                for item in disabled.findings
                if item.rule_id == "net.connector_capacitor_only_no_dc_anchor"
            ).disposition,
            "RULE_OFF",
        )

        ignored_policy = DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id="net.connector_capacitor_only_no_dc_anchor",
                    fingerprint=finding.fingerprint,
                    reason="Synthetic project records the external DC source",
                ),
            )
        )
        ignored = evaluate("synthetic-dc-reference-policy", coach(source), ignored_policy)
        self.assertEqual(ignored.status, "PASS")
        self.assertEqual(
            next(
                item
                for item in ignored.findings
                if item.rule_id == "net.connector_capacitor_only_no_dc_anchor"
            ).disposition,
            "IGNORED",
        )

    def test_connector_capacitor_only_finding_is_order_stable_and_extra_pin_clears_it(self) -> None:
        source = connector_capacitor_only_netlist()
        original = next(
            item
            for item in candidates(source)
            if item.rule_id == "net.connector_capacitor_only_no_dc_anchor"
        )
        reordered = source.model_copy(
            update={
                "nets": dict(reversed(tuple(source.nets.items()))),
                "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
            }
        )
        repeated = next(
            item
            for item in candidates(reordered)
            if item.rule_id == "net.connector_capacitor_only_no_dc_anchor"
        )
        self.assertEqual(fingerprint(original), fingerprint(repeated))

        expanded = connector_capacitor_only_netlist(extra_signal_pin=True)
        self.assertNotIn(
            "net.connector_capacitor_only_no_dc_anchor",
            {item.rule_id for item in candidates(expanded)},
        )

    def test_ic_power_rail_without_fitted_capacitor_needs_review(self) -> None:
        report = evaluate(
            "synthetic-decoupling-presence",
            coach(ic_power_decoupling_fixture()),
            DesignLintPolicy(),
        )
        findings = [
            item
            for item in report.findings
            if item.rule_id == "power.ic_rail_without_fitted_capacitor"
        ]
        self.assertEqual(report.status, "REVIEW")
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].subject, "+3V3: IC supply decoupling review")
        self.assertEqual(
            findings[0].evidence,
            {
                "net": ("+3V3",),
                "power_input_pins": ("U1.1",),
                "component_references": ("U1",),
            },
        )
        self.assertIn("does not establish local", findings[0].message)

    def test_fitted_capacitor_to_return_controls_review(self) -> None:
        report = evaluate(
            "synthetic-decoupling-presence-control",
            coach(ic_power_decoupling_fixture(capacitor_net="+3V3")),
            DesignLintPolicy(),
        )
        self.assertNotIn(
            "power.ic_rail_without_fitted_capacitor",
            {item.rule_id for item in report.findings},
        )

    def test_ic_decoupling_prompt_is_order_stable_and_fitted_capacitor_clears_it(
        self,
    ) -> None:
        rule_id = "power.ic_rail_without_fitted_capacitor"
        source = ic_power_decoupling_fixture()

        def lint(netlist: NetlistContract) -> tuple[str, DesignLintReport]:
            source_hash = hashlib.sha256(netlist.model_dump_json().encode("utf-8")).hexdigest()
            return source_hash, evaluate(
                "synthetic-decoupling-presence",
                coach(netlist, source_hash),
                DesignLintPolicy(),
            )

        source_hash, original = lint(source)
        self.assertEqual(original.netlist_sha256, source_hash)
        original_findings = {
            item.subject: (item.fingerprint, item.evidence)
            for item in original.findings
            if item.rule_id == rule_id
        }
        self.assertEqual(len(original_findings), 1)

        reordered_source = source.model_copy(
            update={
                "components": dict(reversed(tuple(source.components.items()))),
                "nets": dict(reversed(tuple(source.nets.items()))),
                "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
                "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
                "pin_electrical_types": dict(reversed(tuple(source.pin_electrical_types.items()))),
            }
        )
        reordered_hash, reordered = lint(reordered_source)
        self.assertNotEqual(source_hash, reordered_hash)
        self.assertEqual(reordered.netlist_sha256, reordered_hash)
        reordered_findings = {
            item.subject: (item.fingerprint, item.evidence)
            for item in reordered.findings
            if item.rule_id == rule_id
        }
        self.assertEqual(reordered_findings, original_findings)

        repaired_hash, repaired = lint(ic_power_decoupling_fixture(capacitor_net="+3V3"))
        self.assertNotEqual(source_hash, repaired_hash)
        self.assertNotIn(rule_id, {item.rule_id for item in repaired.findings})

    def test_ic_power_decoupling_enforces_capacitor_and_scope_boundaries(
        self,
    ) -> None:
        custom_return = ic_power_decoupling_fixture(
            capacitor_net="+3V3", capacitor_reference_net="CAP_REF"
        )
        custom_return = custom_return.model_copy(
            update={
                "components": {
                    **custom_return.components,
                    "U2": ComponentContract(value="Synthetic return pin", footprint=""),
                },
                "component_symbols": {
                    **custom_return.component_symbols,
                    "U2": "Synthetic:ReturnPin",
                },
                "nets": {**custom_return.nets, "CAP_REF": ("C1.2", "U2.2")},
                "pin_functions": {**custom_return.pin_functions, "U2.2": "GND"},
            }
        )
        cases = (
            # A DNP capacitor does not count as fitted.
            (ic_power_decoupling_fixture(capacitor_net="+3V3", dnp_capacitor=True), True),
            # A capacitor on another rail does not cover this rail.
            (ic_power_decoupling_fixture(capacitor_net="+5V"), True),
            # A capacitor without a recognized return connection does not count.
            (
                ic_power_decoupling_fixture(capacitor_net="+3V3", capacitor_reference_net="+5V"),
                True,
            ),
            (
                ic_power_decoupling_fixture(
                    capacitor_net="+3V3", capacitor_reference_net="CAP_REF"
                ),
                True,
            ),
            (custom_return, False),
            # An open or same-net terminal assignment does not count.
            (
                ic_power_decoupling_fixture(capacitor_net="+3V3", capacitor_reference_net=None),
                True,
            ),
            (
                ic_power_decoupling_fixture(capacitor_net="+3V3", capacitor_reference_net="+3V3"),
                True,
            ),
            # A CP-prefixed IC library name is not a capacitor symbol.
            (
                ic_power_decoupling_fixture().model_copy(
                    update={"component_symbols": {"U1": "Synthetic:CP2102"}}
                ),
                True,
            ),
            # DNP ICs and connector power pins are outside the rule.
            (ic_power_decoupling_fixture(dnp_ic=True), False),
            (ic_power_decoupling_fixture(reference="J1"), False),
            # Only native power-input pins on narrowly recognized positive rails qualify.
            (ic_power_decoupling_fixture(electrical_type="passive"), False),
            (
                ic_power_decoupling_fixture(rail="LOCAL_A", power_function="LOCAL_SUPPLY"),
                False,
            ),
        )
        for source, expected in cases:
            with self.subTest(
                dnp=source.dnp_components,
                rails=tuple(source.nets),
                power_type=source.pin_electrical_types,
            ):
                report = evaluate(
                    "synthetic-decoupling-presence-boundary",
                    coach(source),
                    DesignLintPolicy(),
                )
                present = "power.ic_rail_without_fitted_capacitor" in {
                    item.rule_id for item in report.findings
                }
                self.assertEqual(present, expected)

    def test_ic_power_decoupling_review_supports_rule_policy_and_exact_ignore(self) -> None:
        source = ic_power_decoupling_fixture()
        initial = evaluate(
            "synthetic-decoupling-presence-policy", coach(source), DesignLintPolicy()
        )
        finding = next(
            item
            for item in initial.findings
            if item.rule_id == "power.ic_rail_without_fitted_capacitor"
        )
        blocked = evaluate(
            "synthetic-decoupling-presence-policy",
            coach(source),
            DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id="power.ic_rail_without_fitted_capacitor",
                        mode="block",
                        reason="Synthetic project requires owner review of uncapped IC rails",
                    ),
                )
            ),
        )
        self.assertEqual(blocked.status, "FAIL")

        disabled = evaluate(
            "synthetic-decoupling-presence-policy",
            coach(source),
            DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id="power.ic_rail_without_fitted_capacitor",
                        mode="off",
                        reason="Synthetic project documents internal or off-board decoupling",
                    ),
                )
            ),
        )
        self.assertEqual(disabled.status, "PASS")
        self.assertEqual(
            next(
                item
                for item in disabled.findings
                if item.rule_id == "power.ic_rail_without_fitted_capacitor"
            ).disposition,
            "RULE_OFF",
        )

        ignored = evaluate(
            "synthetic-decoupling-presence-policy",
            coach(source),
            DesignLintPolicy(
                ignores=(
                    DesignLintIgnore(
                        rule_id="power.ic_rail_without_fitted_capacitor",
                        fingerprint=finding.fingerprint,
                        reason="Synthetic control records an intentional remote decoupling plan",
                    ),
                )
            ),
        )
        self.assertEqual(ignored.status, "PASS")
        self.assertEqual(
            next(
                item
                for item in ignored.findings
                if item.rule_id == "power.ic_rail_without_fitted_capacitor"
            ).disposition,
            "IGNORED",
        )

    def test_schematic_geometry_is_project_opt_in_and_uses_review_block_and_ignore_policy(
        self,
    ) -> None:
        fixture = Path(__file__).parent / "fixtures/design_lint/near-miss-pin-line.kicad_sch"
        source = fixture.read_bytes()
        scan = scan_wire_ends_on_pin_lines(
            source,
            source_path="tests/fixtures/design_lint/near-miss-pin-line.kicad_sch",
            kicad_version="10.0.6",
            unconnected_pins=frozenset({"R1.1"}),
        )
        native = coach(NetlistContract(components={}, nets={"unconnected-(R1-Pad1)": ("R1.1",)}))

        default = evaluate(
            "synthetic-geometry", native, DesignLintPolicy(), schematic_geometry=scan
        )
        self.assertEqual(default.status, "PASS")
        self.assertEqual(default.schematic_geometry.status, "DISABLED")
        self.assertEqual(default.schematic_geometry.mode, "off")
        default_finding = next(
            item for item in default.findings if item.rule_id == "schematic.wire_end_on_pin_line"
        )
        self.assertEqual(default_finding.disposition, "RULE_OFF")

        review_policy = DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="schematic.wire_end_on_pin_line",
                    mode="review",
                    reason="Review suspected schematic endpoint near misses",
                ),
            )
        )
        review = evaluate("synthetic-geometry", native, review_policy, schematic_geometry=scan)
        self.assertEqual(review.status, "REVIEW")
        open_finding = next(
            item for item in review.findings if item.rule_id == "schematic.wire_end_on_pin_line"
        )
        self.assertEqual(open_finding.disposition, "OPEN")
        self.assertEqual(open_finding.evidence["schematic_sha256"], (scan.source_sha256,))

        blocked_policy = DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="schematic.wire_end_on_pin_line",
                    mode="block",
                    reason="This reviewed project gates pin-line near misses",
                ),
            )
        )
        blocked = evaluate("synthetic-geometry", native, blocked_policy, schematic_geometry=scan)
        self.assertEqual(blocked.status, "FAIL")

        ignored_policy = review_policy.model_copy(
            update={
                "ignores": (
                    DesignLintIgnore(
                        rule_id=open_finding.rule_id,
                        fingerprint=open_finding.fingerprint,
                        reason="Synthetic control records an intentional drawing exception",
                    ),
                )
            }
        )
        ignored = evaluate("synthetic-geometry", native, ignored_policy, schematic_geometry=scan)
        ignored_finding = next(
            item for item in ignored.findings if item.rule_id == "schematic.wire_end_on_pin_line"
        )
        self.assertEqual(ignored_finding.disposition, "IGNORED")
        self.assertEqual(ignored.status, "PASS")

        changed_source = source.replace(b"FAULT_NET", b"FAULT_NET_CHANGED", 1)
        changed_scan = scan_wire_ends_on_pin_lines(
            changed_source,
            source_path=scan.source_path,
            kicad_version="10.0.6",
            unconnected_pins=frozenset({"R1.1"}),
        )
        stale = evaluate(
            "synthetic-geometry", native, ignored_policy, schematic_geometry=changed_scan
        )
        self.assertEqual(stale.status, "REVIEW")
        self.assertEqual(len(stale.stale_ignores), 1)

    def test_pin_tip_on_wire_interior_has_independent_project_policy(self) -> None:
        source_path = Path(__file__).parent / (
            "fixtures/design_lint/pin-on-wire-middle-no-junction.kicad_sch"
        )
        scan = scan_wire_ends_on_pin_lines(
            source_path.read_bytes(),
            source_path="tests/fixtures/design_lint/pin-on-wire-middle-no-junction.kicad_sch",
            kicad_version="10.0.6",
            unconnected_pins=frozenset({"R1.1"}),
        )
        self.assertEqual(scan.findings, ())
        self.assertEqual(len(scan.pin_tip_on_wire_interiors), 1)
        native = coach(NetlistContract(components={}, nets={"unconnected-(R1-Pad1)": ("R1.1",)}))

        default = evaluate(
            "synthetic-wire-middle", native, DesignLintPolicy(), schematic_geometry=scan
        )
        self.assertEqual(default.status, "PASS")
        self.assertEqual(default.schematic_geometry.finding_count, 1)
        default_finding = next(
            item
            for item in default.findings
            if item.rule_id == "schematic.pin_tip_on_wire_interior"
        )
        self.assertEqual(default_finding.disposition, "RULE_OFF")

        review_policy = DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="schematic.pin_tip_on_wire_interior",
                    mode="review",
                    reason="Review native-open pins crossed by wire segments",
                ),
            )
        )
        review = evaluate("synthetic-wire-middle", native, review_policy, schematic_geometry=scan)
        self.assertEqual(review.status, "REVIEW")
        self.assertEqual(
            review.schematic_geometry.rule_modes["schematic.pin_tip_on_wire_interior"],
            "review",
        )
        self.assertEqual(
            review.schematic_geometry.rule_modes["schematic.wire_end_on_pin_line"], "off"
        )
        finding = next(
            item for item in review.findings if item.rule_id == "schematic.pin_tip_on_wire_interior"
        )
        self.assertEqual(finding.evidence["pin"], ("R1.1",))
        self.assertEqual(finding.evidence["wire_segment_start_mm"], ("50.800000,71.120000",))
        self.assertEqual(finding.evidence["wire_segment_end_mm"], ("101.600000,71.120000",))

        blocking = DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="schematic.pin_tip_on_wire_interior",
                    mode="block",
                    reason="This project explicitly gates wire-interior pin misses",
                ),
            )
        )
        blocked = evaluate("synthetic-wire-middle", native, blocking, schematic_geometry=scan)
        self.assertEqual(blocked.status, "FAIL")

        ignored_policy = review_policy.model_copy(
            update={
                "ignores": (
                    DesignLintIgnore(
                        rule_id=finding.rule_id,
                        fingerprint=finding.fingerprint,
                        reason="Reviewed intentionally open pin adjacent to wire geometry",
                    ),
                )
            }
        )
        ignored = evaluate("synthetic-wire-middle", native, ignored_policy, schematic_geometry=scan)
        ignored_finding = next(
            item
            for item in ignored.findings
            if item.rule_id == "schematic.pin_tip_on_wire_interior"
        )
        self.assertEqual(ignored_finding.disposition, "IGNORED")
        self.assertEqual(ignored.status, "PASS")

    def test_wire_endpoint_near_pin_tip_has_independent_project_policy(self) -> None:
        source_path = Path(__file__).parent / (
            "fixtures/design_lint/wire-end-near-pin-tip.kicad_sch"
        )
        source = source_path.read_bytes()
        scan = scan_wire_ends_on_pin_lines(
            source,
            source_path="tests/fixtures/design_lint/wire-end-near-pin-tip.kicad_sch",
            kicad_version="10.0.6",
            unconnected_pins=frozenset({"R1.1"}),
        )
        self.assertEqual(scan.findings, ())
        self.assertEqual(scan.pin_tip_on_wire_interiors, ())
        self.assertEqual(len(scan.wire_endpoints_near_pin_tips), 1)
        native = coach(NetlistContract(components={}, nets={"unconnected-(R1-Pad1)": ("R1.1",)}))

        default = evaluate(
            "synthetic-wire-end-near-pin-tip", native, DesignLintPolicy(), schematic_geometry=scan
        )
        self.assertEqual(default.status, "PASS")
        self.assertEqual(default.schematic_geometry.finding_count, 1)
        default_finding = next(
            item
            for item in default.findings
            if item.rule_id == "schematic.wire_endpoint_near_pin_tip"
        )
        self.assertEqual(default_finding.disposition, "RULE_OFF")

        review_policy = DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="schematic.wire_endpoint_near_pin_tip",
                    mode="review",
                    reason="Review native-open pins with nearby wire endpoints",
                ),
            )
        )
        review = evaluate(
            "synthetic-wire-end-near-pin-tip", native, review_policy, schematic_geometry=scan
        )
        self.assertEqual(review.status, "REVIEW")
        self.assertEqual(
            review.schematic_geometry.rule_modes["schematic.wire_endpoint_near_pin_tip"],
            "review",
        )
        finding = next(
            item
            for item in review.findings
            if item.rule_id == "schematic.wire_endpoint_near_pin_tip"
        )
        self.assertEqual(finding.evidence["pin"], ("R1.1",))
        self.assertEqual(finding.evidence["wire_endpoint_mm"], ("76.200000,70.620000",))
        self.assertEqual(finding.evidence["distance_to_pin_tip_mm"], ("0.500000",))

        blocking_policy = DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="schematic.wire_endpoint_near_pin_tip",
                    mode="block",
                    reason="This reviewed project gates wire-to-pin near misses",
                ),
            )
        )
        blocked = evaluate(
            "synthetic-wire-end-near-pin-tip", native, blocking_policy, schematic_geometry=scan
        )
        self.assertEqual(blocked.status, "FAIL")

        ignored_policy = review_policy.model_copy(
            update={
                "ignores": (
                    DesignLintIgnore(
                        rule_id=finding.rule_id,
                        fingerprint=finding.fingerprint,
                        reason="Synthetic review accepts this exact near miss",
                    ),
                )
            }
        )
        ignored = evaluate(
            "synthetic-wire-end-near-pin-tip", native, ignored_policy, schematic_geometry=scan
        )
        ignored_finding = next(
            item
            for item in ignored.findings
            if item.rule_id == "schematic.wire_endpoint_near_pin_tip"
        )
        self.assertEqual(ignored_finding.disposition, "IGNORED")
        self.assertEqual(ignored.status, "PASS")

        changed_source = source.replace(b"70.62", b"70.61", 1)
        changed_scan = scan_wire_ends_on_pin_lines(
            changed_source,
            source_path=scan.source_path,
            kicad_version="10.0.6",
            unconnected_pins=frozenset({"R1.1"}),
        )
        stale = evaluate(
            "synthetic-wire-end-near-pin-tip",
            native,
            ignored_policy,
            schematic_geometry=changed_scan,
        )
        self.assertEqual(stale.status, "REVIEW")
        self.assertEqual(len(stale.stale_ignores), 1)

    def test_label_near_wire_endpoint_has_independent_project_policy(self) -> None:
        source_path = Path(__file__).parent / (
            "fixtures/design_lint/label-near-wire-endpoint.kicad_sch"
        )
        scan = scan_wire_ends_on_pin_lines(
            source_path.read_bytes(),
            source_path="tests/fixtures/design_lint/label-near-wire-endpoint.kicad_sch",
            kicad_version="10.0.6",
            unconnected_pins=frozenset(),
        )
        self.assertEqual(scan.findings, ())
        self.assertEqual(scan.pin_tip_on_wire_interiors, ())
        self.assertEqual(len(scan.labels_near_wire_endpoints), 1)
        native = coach(NetlistContract(components={}, nets={}))

        default = evaluate(
            "synthetic-label-near-endpoint", native, DesignLintPolicy(), schematic_geometry=scan
        )
        self.assertEqual(default.status, "PASS")
        self.assertEqual(default.schematic_geometry.finding_count, 1)
        default_finding = next(
            item
            for item in default.findings
            if item.rule_id == "schematic.label_near_wire_endpoint"
        )
        self.assertEqual(default_finding.disposition, "RULE_OFF")

        review_policy = DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="schematic.label_near_wire_endpoint",
                    mode="review",
                    reason="Review labels placed close to, but off, wire endpoints",
                ),
            )
        )
        review = evaluate(
            "synthetic-label-near-endpoint", native, review_policy, schematic_geometry=scan
        )
        self.assertEqual(review.status, "REVIEW")
        self.assertEqual(
            review.schematic_geometry.rule_modes["schematic.label_near_wire_endpoint"], "review"
        )
        finding = next(
            item for item in review.findings if item.rule_id == "schematic.label_near_wire_endpoint"
        )
        self.assertEqual(finding.evidence["label_uuid"], ("b0000000-0000-4000-8000-000000000006",))
        self.assertEqual(
            finding.evidence["near_wire_endpoints"],
            ("b0000000-0000-4000-8000-000000000005@101.600000,71.120000 (0.500000 mm)",),
        )

        blocking_policy = DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="schematic.label_near_wire_endpoint",
                    mode="block",
                    reason="This project explicitly gates schematic label near misses",
                ),
            )
        )
        blocked = evaluate(
            "synthetic-label-near-endpoint", native, blocking_policy, schematic_geometry=scan
        )
        self.assertEqual(blocked.status, "FAIL")

        ignored_policy = review_policy.model_copy(
            update={
                "ignores": (
                    DesignLintIgnore(
                        rule_id=finding.rule_id,
                        fingerprint=finding.fingerprint,
                        reason="Synthetic review control records an intentional detached label",
                    ),
                )
            }
        )
        ignored = evaluate(
            "synthetic-label-near-endpoint", native, ignored_policy, schematic_geometry=scan
        )
        ignored_finding = next(
            item
            for item in ignored.findings
            if item.rule_id == "schematic.label_near_wire_endpoint"
        )
        self.assertEqual(ignored_finding.disposition, "IGNORED")
        self.assertEqual(ignored.status, "PASS")

    def test_unmarked_wire_crossing_has_independent_review_and_ignore_policy(self) -> None:
        source_path = Path(__file__).parent / (
            "fixtures/design_lint/unmarked-orthogonal-crossing.kicad_sch"
        )
        scan = scan_wire_ends_on_pin_lines(
            source_path.read_bytes(),
            source_path="tests/fixtures/design_lint/unmarked-orthogonal-crossing.kicad_sch",
            kicad_version="10.0.6",
            unconnected_pins=frozenset(),
        )
        self.assertEqual(len(scan.unmarked_wire_crossings), 1)
        native = coach(NetlistContract(components={}, nets={}))

        default = evaluate(
            "synthetic-wire-crossing", native, DesignLintPolicy(), schematic_geometry=scan
        )
        self.assertEqual(default.status, "PASS")
        self.assertEqual(default.schematic_geometry.finding_count, 1)
        default_finding = next(
            item for item in default.findings if item.rule_id == "schematic.unmarked_wire_crossing"
        )
        self.assertEqual(default_finding.disposition, "RULE_OFF")

        review_policy = DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="schematic.unmarked_wire_crossing",
                    mode="review",
                    reason="Review unmarked wire crossings for intended connectivity",
                ),
            )
        )
        review = evaluate("synthetic-wire-crossing", native, review_policy, schematic_geometry=scan)
        self.assertEqual(review.status, "REVIEW")
        finding = next(
            item for item in review.findings if item.rule_id == "schematic.unmarked_wire_crossing"
        )
        self.assertEqual(finding.evidence["crossing_mm"], ("127.000000,127.000000",))
        self.assertEqual(
            finding.evidence["wire_uuids"],
            (
                "c0000000-0000-4000-8000-000000000008",
                "c0000000-0000-4000-8000-000000000009",
            ),
        )

        blocked = evaluate(
            "synthetic-wire-crossing",
            native,
            review_policy.model_copy(
                update={
                    "rules": (
                        DesignLintRuleOverride(
                            rule_id="schematic.unmarked_wire_crossing",
                            mode="block",
                            reason="This project gates all unresolved wire crossings",
                        ),
                    )
                }
            ),
            schematic_geometry=scan,
        )
        self.assertEqual(blocked.status, "FAIL")

        ignored_policy = review_policy.model_copy(
            update={
                "ignores": (
                    DesignLintIgnore(
                        rule_id=finding.rule_id,
                        fingerprint=finding.fingerprint,
                        reason="This unmarked crossing is intentionally unconnected",
                    ),
                )
            }
        )
        ignored = evaluate(
            "synthetic-wire-crossing", native, ignored_policy, schematic_geometry=scan
        )
        ignored_finding = next(
            item for item in ignored.findings if item.rule_id == "schematic.unmarked_wire_crossing"
        )
        self.assertEqual(ignored_finding.disposition, "IGNORED")
        self.assertEqual(ignored.status, "PASS")

    def test_unmarked_t_junction_has_independent_review_and_ignore_policy(self) -> None:
        source_path = Path(__file__).parent / (
            "fixtures/design_lint/t-junction/fault-no-junction.kicad_sch"
        )
        scan = scan_wire_ends_on_pin_lines(
            source_path.read_bytes(),
            source_path="tests/fixtures/design_lint/t-junction/fault-no-junction.kicad_sch",
            kicad_version="10.0.6",
            unconnected_pins=frozenset({"R1.2"}),
        )
        self.assertEqual(len(scan.unmarked_t_junctions), 1)
        native = coach(NetlistContract(components={}, nets={}))
        review_policy = DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="schematic.unmarked_t_junction",
                    mode="review",
                    reason="Review endpoint-to-interior contacts for missing junctions",
                ),
            )
        )

        default = evaluate(
            "synthetic-t-junction", native, DesignLintPolicy(), schematic_geometry=scan
        )
        self.assertEqual(default.status, "PASS")
        self.assertEqual(default.schematic_geometry.finding_count, 1)
        self.assertEqual(
            next(
                item for item in default.findings if item.rule_id == "schematic.unmarked_t_junction"
            ).disposition,
            "RULE_OFF",
        )

        review = evaluate("synthetic-t-junction", native, review_policy, schematic_geometry=scan)
        self.assertEqual(review.status, "REVIEW")
        finding = next(
            item for item in review.findings if item.rule_id == "schematic.unmarked_t_junction"
        )
        self.assertEqual(finding.evidence["junction_mm"], ("88.900000,71.120000",))
        self.assertEqual(
            finding.evidence["endpoint_wire_uuid"],
            ("c0000000-0000-4000-8000-000000000012",),
        )
        self.assertEqual(
            finding.evidence["interior_wire_uuid"],
            ("b0000000-0000-4000-8000-000000000005",),
        )

        blocked = evaluate(
            "synthetic-t-junction",
            native,
            review_policy.model_copy(
                update={
                    "rules": (
                        DesignLintRuleOverride(
                            rule_id="schematic.unmarked_t_junction",
                            mode="block",
                            reason="This project requires explicit junction markers at T contacts",
                        ),
                    )
                }
            ),
            schematic_geometry=scan,
        )
        self.assertEqual(blocked.status, "FAIL")

        ignored_policy = review_policy.model_copy(
            update={
                "ignores": (
                    DesignLintIgnore(
                        rule_id=finding.rule_id,
                        fingerprint=finding.fingerprint,
                        reason="This branch intentionally remains separate",
                    ),
                )
            }
        )
        ignored = evaluate("synthetic-t-junction", native, ignored_policy, schematic_geometry=scan)
        ignored_finding = next(
            item for item in ignored.findings if item.rule_id == "schematic.unmarked_t_junction"
        )
        self.assertEqual(ignored_finding.disposition, "IGNORED")
        self.assertEqual(ignored.status, "PASS")

    def test_coincident_text_anchor_rule_is_configurable_and_review_only_by_default(self) -> None:
        scan = scan_wire_ends_on_pin_lines(
            free_text_anchor_fixture((25.4, 25.4), (25.4, 25.4)),
            source_path="synthetic/text-anchor/coincident.kicad_sch",
            kicad_version="10.0.6",
            unconnected_pins=frozenset(),
        )
        native = coach(NetlistContract(components={}, nets={}))
        review_policy = DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="schematic.coincident_text_anchors",
                    mode="review",
                    reason="Review coincident free-text source anchors",
                ),
            )
        )

        default = evaluate(
            "synthetic-text-anchor", native, DesignLintPolicy(), schematic_geometry=scan
        )
        self.assertEqual(default.status, "PASS")
        self.assertEqual(default.schematic_geometry.finding_count, 1)
        self.assertEqual(
            next(
                item
                for item in default.findings
                if item.rule_id == "schematic.coincident_text_anchors"
            ).disposition,
            "RULE_OFF",
        )

        review = evaluate("synthetic-text-anchor", native, review_policy, schematic_geometry=scan)
        self.assertEqual(review.status, "REVIEW")
        finding = next(
            item for item in review.findings if item.rule_id == "schematic.coincident_text_anchors"
        )
        self.assertEqual(finding.evidence["anchor_mm"], ("25.400000,25.400000",))
        self.assertEqual(
            finding.evidence["first_text_uuid"], ("d0000000-0000-4000-8000-000000000001",)
        )

        blocked = evaluate(
            "synthetic-text-anchor",
            native,
            review_policy.model_copy(
                update={
                    "rules": (
                        DesignLintRuleOverride(
                            rule_id="schematic.coincident_text_anchors",
                            mode="block",
                            reason="This project requires unique free-text anchors",
                        ),
                    )
                }
            ),
            schematic_geometry=scan,
        )
        self.assertEqual(blocked.status, "FAIL")

        ignored = evaluate(
            "synthetic-text-anchor",
            native,
            review_policy.model_copy(
                update={
                    "ignores": (
                        DesignLintIgnore(
                            rule_id=finding.rule_id,
                            fingerprint=finding.fingerprint,
                            reason="The two annotations intentionally share an anchor",
                        ),
                    )
                }
            ),
            schematic_geometry=scan,
        )
        ignored_finding = next(
            item for item in ignored.findings if item.rule_id == "schematic.coincident_text_anchors"
        )
        self.assertEqual(ignored_finding.disposition, "IGNORED")
        self.assertEqual(ignored.status, "PASS")

    def test_free_text_overlap_rule_is_configurable_and_review_only_by_default(self) -> None:
        scan = scan_wire_ends_on_pin_lines(
            free_text_objects_fixture(
                "LONG_LABEL_ALPHA", (25.4, 25.4), "LONG_LABEL_BETA", (29.0, 25.4)
            ),
            source_path="synthetic/text-overlap/fault.kicad_sch",
            kicad_version="10.0.6",
            unconnected_pins=frozenset(),
        )
        native = coach(NetlistContract(components={}, nets={}))
        review_policy = DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="schematic.free_text_overlap",
                    mode="review",
                    reason="Review the bounded native-font text-overlap candidate",
                ),
            )
        )

        default = evaluate(
            "synthetic-text-overlap", native, DesignLintPolicy(), schematic_geometry=scan
        )
        self.assertEqual(default.status, "PASS")
        self.assertEqual(default.schematic_geometry.finding_count, 1)
        self.assertEqual(
            next(
                item for item in default.findings if item.rule_id == "schematic.free_text_overlap"
            ).disposition,
            "RULE_OFF",
        )

        review = evaluate("synthetic-text-overlap", native, review_policy, schematic_geometry=scan)
        self.assertEqual(review.status, "REVIEW")
        finding = next(
            item for item in review.findings if item.rule_id == "schematic.free_text_overlap"
        )
        self.assertEqual(
            finding.evidence["first_text_uuid"],
            ("d0000000-0000-4000-8000-000000000001",),
        )
        self.assertIn("overlap_box_mm", finding.evidence)

        blocked = evaluate(
            "synthetic-text-overlap",
            native,
            review_policy.model_copy(
                update={
                    "rules": (
                        DesignLintRuleOverride(
                            rule_id="schematic.free_text_overlap",
                            mode="block",
                            reason="This project requires free-text envelopes to stay clear",
                        ),
                    )
                }
            ),
            schematic_geometry=scan,
        )
        self.assertEqual(blocked.status, "FAIL")

        ignored = evaluate(
            "synthetic-text-overlap",
            native,
            review_policy.model_copy(
                update={
                    "ignores": (
                        DesignLintIgnore(
                            rule_id=finding.rule_id,
                            fingerprint=finding.fingerprint,
                            reason="The annotations intentionally overlap for this project",
                        ),
                    )
                }
            ),
            schematic_geometry=scan,
        )
        ignored_finding = next(
            item for item in ignored.findings if item.rule_id == "schematic.free_text_overlap"
        )
        self.assertEqual(ignored_finding.disposition, "IGNORED")
        self.assertEqual(ignored.status, "PASS")

    def test_free_text_over_wire_rule_is_configurable_and_review_only_by_default(self) -> None:
        scan = scan_wire_ends_on_pin_lines(
            free_text_wire_fixture("WIRE CROSSING FAULT", (88.9, 71.12)),
            source_path="synthetic/text-wire/fault.kicad_sch",
            kicad_version="10.0.6",
            unconnected_pins=frozenset(),
        )
        native = coach(NetlistContract(components={}, nets={}))
        review_policy = DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="schematic.free_text_over_wire",
                    mode="review",
                    reason="Review free-text placement across native wire geometry",
                ),
            )
        )

        default = evaluate(
            "synthetic-text-wire", native, DesignLintPolicy(), schematic_geometry=scan
        )
        self.assertEqual(default.status, "PASS")
        self.assertEqual(default.schematic_geometry.finding_count, 1)
        self.assertEqual(
            next(
                item for item in default.findings if item.rule_id == "schematic.free_text_over_wire"
            ).disposition,
            "RULE_OFF",
        )

        review = evaluate("synthetic-text-wire", native, review_policy, schematic_geometry=scan)
        self.assertEqual(review.status, "REVIEW")
        finding = next(
            item for item in review.findings if item.rule_id == "schematic.free_text_over_wire"
        )
        self.assertEqual(finding.evidence["text"], ("WIRE CROSSING FAULT",))
        self.assertEqual(finding.evidence["wire_uuid"], ("b0000000-0000-4000-8000-000000000005",))
        self.assertIn("overlap_segment_mm", finding.evidence)

        blocked = evaluate(
            "synthetic-text-wire",
            native,
            review_policy.model_copy(
                update={
                    "rules": (
                        DesignLintRuleOverride(
                            rule_id="schematic.free_text_over_wire",
                            mode="block",
                            reason="This project requires annotations to stay clear of wires",
                        ),
                    )
                }
            ),
            schematic_geometry=scan,
        )
        self.assertEqual(blocked.status, "FAIL")

        ignored = evaluate(
            "synthetic-text-wire",
            native,
            review_policy.model_copy(
                update={
                    "ignores": (
                        DesignLintIgnore(
                            rule_id=finding.rule_id,
                            fingerprint=finding.fingerprint,
                            reason="This schematic annotation intentionally crosses the wire",
                        ),
                    )
                }
            ),
            schematic_geometry=scan,
        )
        ignored_finding = next(
            item for item in ignored.findings if item.rule_id == "schematic.free_text_over_wire"
        )
        self.assertEqual(ignored_finding.disposition, "IGNORED")
        self.assertEqual(ignored.status, "PASS")

    def test_wire_through_symbol_body_rule_is_configurable_and_off_by_default(self) -> None:
        scan = scan_wire_ends_on_pin_lines(
            symbol_body_wire_fixture(),
            source_path="synthetic/body-wire/fault.kicad_sch",
            kicad_version="10.0.6",
            unconnected_pins=frozenset(),
        )
        native = coach(NetlistContract(components={}, nets={}))
        default = evaluate(
            "synthetic-body-wire", native, DesignLintPolicy(), schematic_geometry=scan
        )
        self.assertEqual(default.status, "PASS")
        self.assertEqual(default.schematic_geometry.finding_count, 1)
        self.assertEqual(
            next(
                item
                for item in default.findings
                if item.rule_id == "schematic.wire_through_symbol_body"
            ).disposition,
            "RULE_OFF",
        )

        review_policy = DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="schematic.wire_through_symbol_body",
                    mode="review",
                    reason="Review wires that overlap symbol body graphics",
                ),
            )
        )
        review = evaluate("synthetic-body-wire", native, review_policy, schematic_geometry=scan)
        self.assertEqual(review.status, "REVIEW")
        finding = next(
            item for item in review.findings if item.rule_id == "schematic.wire_through_symbol_body"
        )
        self.assertEqual(finding.evidence["reference"], ("R1",))
        self.assertEqual(finding.evidence["symbol_library_id"], ("Lint:R",))
        self.assertEqual(finding.evidence["wire_uuid"], ("f1000000-0000-4000-8000-000000000001",))
        self.assertIn("body_box_mm", finding.evidence)
        self.assertIn("overlap_segment_mm", finding.evidence)

        blocked = evaluate(
            "synthetic-body-wire",
            native,
            review_policy.model_copy(
                update={
                    "rules": (
                        DesignLintRuleOverride(
                            rule_id="schematic.wire_through_symbol_body",
                            mode="block",
                            reason="This project requires clear separation of wires and symbol bodies",
                        ),
                    )
                }
            ),
            schematic_geometry=scan,
        )
        self.assertEqual(blocked.status, "FAIL")

        ignored = evaluate(
            "synthetic-body-wire",
            native,
            review_policy.model_copy(
                update={
                    "ignores": (
                        DesignLintIgnore(
                            rule_id=finding.rule_id,
                            fingerprint=finding.fingerprint,
                            reason="This crossing is a deliberate schematic convention",
                        ),
                    )
                }
            ),
            schematic_geometry=scan,
        )
        ignored_finding = next(
            item
            for item in ignored.findings
            if item.rule_id == "schematic.wire_through_symbol_body"
        )
        self.assertEqual(ignored_finding.disposition, "IGNORED")
        self.assertEqual(ignored.status, "PASS")

    def test_geometry_coverage_is_scoped_to_enabled_rule_capabilities(self) -> None:
        source = symbol_body_wire_fixture()
        text = (
            b'  (text "UNSUPPORTED~{LINE}" (at 25.4 25.4 0) '
            b"(effects (font (size 1.27 1.27))) "
            b'(uuid "f1000000-0000-4000-8000-000000000009"))\n'
        )
        source = source.replace(b"  (sheet_instances", text + b"  (sheet_instances", 1)
        scan = scan_wire_ends_on_pin_lines(
            source,
            source_path="synthetic/body-wire-with-unsupported-text.kicad_sch",
            kicad_version="10.0.6",
            unconnected_pins=frozenset(),
        )
        native = coach(NetlistContract(components={}, nets={}))

        wire_policy = DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="schematic.wire_through_symbol_body",
                    mode="review",
                    reason="Review body crossings in this project",
                ),
            )
        )
        wire_report = evaluate(
            "synthetic-rule-coverage", native, wire_policy, schematic_geometry=scan
        )
        self.assertEqual(wire_report.status, "REVIEW")
        self.assertEqual(wire_report.schematic_geometry.status, "COMPLETE")
        self.assertEqual(
            wire_report.schematic_geometry.rule_coverage["schematic.wire_through_symbol_body"],
            "COMPLETE",
        )
        self.assertEqual(
            wire_report.schematic_geometry.rule_coverage["schematic.free_text_overlap"],
            "DISABLED",
        )
        self.assertEqual(wire_report.schematic_geometry.unsupported, ())

        text_policy = DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="schematic.free_text_overlap",
                    mode="review",
                    reason="Review supported free-text geometry in this project",
                ),
            )
        )
        text_report = evaluate(
            "synthetic-rule-coverage", native, text_policy, schematic_geometry=scan
        )
        self.assertEqual(text_report.status, "REVIEW")
        self.assertEqual(text_report.schematic_geometry.status, "PARTIAL")
        self.assertEqual(
            text_report.schematic_geometry.rule_coverage["schematic.free_text_overlap"],
            "PARTIAL",
        )
        self.assertIn(
            "schematic.free_text_overlap", text_report.schematic_geometry.unsupported_by_rule
        )
        self.assertEqual(
            text_report.schematic_geometry.rule_coverage["schematic.wire_through_symbol_body"],
            "DISABLED",
        )

        multiline_scan = scan_wire_ends_on_pin_lines(
            free_text_wire_fixture("FIRST\nSECOND", (88.9, 80.01)),
            source_path="synthetic/body-wire-with-supported-multiline-text.kicad_sch",
            kicad_version="10.0.6",
            unconnected_pins=frozenset(),
        )
        multiline_report = evaluate(
            "synthetic-rule-coverage", native, text_policy, schematic_geometry=multiline_scan
        )
        self.assertEqual(multiline_report.status, "PASS")
        self.assertEqual(multiline_report.schematic_geometry.status, "COMPLETE")
        self.assertEqual(
            multiline_report.schematic_geometry.rule_coverage["schematic.free_text_overlap"],
            "COMPLETE",
        )
        self.assertEqual(multiline_report.schematic_geometry.unsupported, ())

    def test_free_text_over_symbol_body_rule_is_configurable_and_off_by_default(self) -> None:
        scan = scan_wire_ends_on_pin_lines(
            free_text_symbol_body_fixture(),
            source_path="synthetic/text-body/fault.kicad_sch",
            kicad_version="10.0.6",
            unconnected_pins=frozenset(),
        )
        native = coach(NetlistContract(components={}, nets={}))
        default = evaluate(
            "synthetic-text-body", native, DesignLintPolicy(), schematic_geometry=scan
        )
        self.assertEqual(default.status, "PASS")
        self.assertEqual(default.schematic_geometry.finding_count, 1)
        self.assertEqual(
            next(
                item
                for item in default.findings
                if item.rule_id == "schematic.free_text_over_symbol_body"
            ).disposition,
            "RULE_OFF",
        )

        review_policy = DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="schematic.free_text_over_symbol_body",
                    mode="review",
                    reason="Review free text that overlaps a component body",
                ),
            )
        )
        review = evaluate("synthetic-text-body", native, review_policy, schematic_geometry=scan)
        self.assertEqual(review.status, "REVIEW")
        finding = next(
            item
            for item in review.findings
            if item.rule_id == "schematic.free_text_over_symbol_body"
        )
        self.assertEqual(finding.evidence["text"], ("BODY NOTE",))
        self.assertEqual(finding.evidence["reference"], ("R1",))
        self.assertEqual(finding.evidence["text_uuid"], ("f2000000-0000-4000-8000-000000000001",))
        self.assertEqual(finding.evidence["symbol_library_id"], ("Lint:R",))
        self.assertIn("overlap_box_mm", finding.evidence)
        self.assertIn("overlap_area_mm2", finding.evidence)

        blocked = evaluate(
            "synthetic-text-body",
            native,
            review_policy.model_copy(
                update={
                    "rules": (
                        DesignLintRuleOverride(
                            rule_id="schematic.free_text_over_symbol_body",
                            mode="block",
                            reason="This project requires annotation clearance from symbols",
                        ),
                    )
                }
            ),
            schematic_geometry=scan,
        )
        self.assertEqual(blocked.status, "FAIL")

        ignored = evaluate(
            "synthetic-text-body",
            native,
            review_policy.model_copy(
                update={
                    "ignores": (
                        DesignLintIgnore(
                            rule_id=finding.rule_id,
                            fingerprint=finding.fingerprint,
                            reason="This note intentionally sits within the symbol outline",
                        ),
                    )
                }
            ),
            schematic_geometry=scan,
        )
        ignored_finding = next(
            item
            for item in ignored.findings
            if item.rule_id == "schematic.free_text_over_symbol_body"
        )
        self.assertEqual(ignored_finding.disposition, "IGNORED")
        self.assertEqual(ignored.status, "PASS")

    def test_repeated_component_supply_pins_on_different_nets_need_review(self) -> None:
        report = evaluate(
            "synthetic-component-supplies",
            coach(repeated_component_supply_pins()),
            DesignLintPolicy(),
        )
        findings = [
            item
            for item in report.findings
            if item.rule_id == "component.repeated_supply_pin_function"
        ]
        self.assertEqual(report.status, "REVIEW")
        self.assertEqual(len(findings), 1)
        self.assertEqual(
            findings[0].subject,
            "U1 (Synthetic:MultiSupplyLogic): VDD supply pins",
        )
        self.assertEqual(
            findings[0].evidence,
            {"U1.1": ("+3V3",), "U1.2": ("+1V8",)},
        )
        self.assertIn("intended split", findings[0].message)

    def test_repeated_supply_mapping_order_is_stable_and_shared_rail_clears_it(self) -> None:
        source = repeated_component_supply_pins()
        original = evaluate("synthetic-component-supplies", coach(source), DesignLintPolicy())
        reordered_source = source.model_copy(
            update={
                "components": dict(reversed(tuple(source.components.items()))),
                "nets": dict(reversed(tuple(source.nets.items()))),
                "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
                "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            }
        )
        reordered = evaluate(
            "synthetic-component-supplies",
            coach(reordered_source),
            DesignLintPolicy(),
        )
        original_finding = next(
            item
            for item in original.findings
            if item.rule_id == "component.repeated_supply_pin_function"
        )
        reordered_finding = next(
            item
            for item in reordered.findings
            if item.rule_id == "component.repeated_supply_pin_function"
        )
        self.assertEqual(reordered_finding.evidence, original_finding.evidence)
        self.assertEqual(reordered_finding.fingerprint, original_finding.fingerprint)

        shared_rail = source.model_copy(update={"nets": {"+3V3": ("U1.1", "U1.2")}})
        repaired = evaluate(
            "synthetic-component-supplies",
            coach(shared_rail),
            DesignLintPolicy(),
        )
        self.assertNotIn(
            "component.repeated_supply_pin_function",
            {item.rule_id for item in repaired.findings},
        )

    def test_shared_rail_distinct_supply_functions_and_dnp_are_controls(self) -> None:
        shared = evaluate(
            "synthetic-component-supplies",
            coach(repeated_component_supply_pins(split=False)),
            DesignLintPolicy(),
        )
        separate_functions = evaluate(
            "synthetic-component-supplies",
            coach(repeated_component_supply_pins(second_function="VDDIO")),
            DesignLintPolicy(),
        )
        dnp_split = evaluate(
            "synthetic-component-supplies",
            coach(repeated_component_supply_pins(dnp=True)),
            DesignLintPolicy(),
        )
        for report in (shared, separate_functions, dnp_split):
            self.assertNotIn(
                "component.repeated_supply_pin_function",
                {item.rule_id for item in report.findings},
            )

    def test_unassigned_duplicate_supply_pin_uses_specific_open_pin_rule(self) -> None:
        report = evaluate(
            "synthetic-component-supplies",
            coach(repeated_component_supply_pins(second_pin_assigned=False)),
            DesignLintPolicy(),
        )
        rule_ids = {item.rule_id for item in report.findings}
        self.assertIn("component.unconnected_supply_pin", rule_ids)
        self.assertNotIn("component.repeated_supply_pin_function", rule_ids)

    def test_repeated_supply_finding_uses_project_override_and_exact_ignore(self) -> None:
        source = repeated_component_supply_pins()
        initial = evaluate("synthetic-component-supplies", coach(source), DesignLintPolicy())
        finding = next(
            item
            for item in initial.findings
            if item.rule_id == "component.repeated_supply_pin_function"
        )
        ignored_policy = DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id="component.repeated_supply_pin_function",
                    fingerprint=finding.fingerprint,
                    reason="Synthetic control records an intentionally filtered rail split",
                ),
            )
        )
        ignored = evaluate("synthetic-component-supplies", coach(source), ignored_policy)
        self.assertEqual(ignored.status, "PASS")
        self.assertEqual(
            next(
                item
                for item in ignored.findings
                if item.rule_id == "component.repeated_supply_pin_function"
            ).disposition,
            "IGNORED",
        )

        changed_source = source.model_copy(update={"nets": {"+3V3": ("U1.1",), "+2V5": ("U1.2",)}})
        changed = evaluate("synthetic-component-supplies", coach(changed_source), ignored_policy)
        self.assertEqual(changed.status, "REVIEW")
        self.assertEqual(changed.stale_ignores, ignored_policy.ignores)

        blocking_policy = DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="component.repeated_supply_pin_function",
                    mode="block",
                    reason="Synthetic project requires reviewed same-function supply pins",
                ),
            )
        )
        blocked = evaluate("synthetic-component-supplies", coach(source), blocking_policy)
        self.assertEqual(blocked.status, "FAIL")
        self.assertEqual(blocked.findings[0].mode, "block")

    def test_ambiguous_component_supply_assignment_is_reported(self) -> None:
        source = repeated_component_supply_pins().model_copy(
            update={
                "nets": {
                    "+3V3": ("U1.1", "U1.2"),
                    "+1V8": ("U1.1",),
                }
            }
        )
        report = evaluate("synthetic-component-supplies", coach(source), DesignLintPolicy())
        finding = next(
            item
            for item in report.findings
            if item.rule_id == "component.repeated_supply_pin_function"
        )
        self.assertEqual(finding.evidence["U1.1"], ("+1V8", "+3V3"))

    def test_peer_component_power_pin_splits_surface_review_and_controls(self) -> None:
        report = evaluate(
            "synthetic-peer-component-power-pins",
            coach(peer_component_power_pins()),
            DesignLintPolicy(),
        )
        findings = [
            item
            for item in report.findings
            if item.rule_id == "component.peer_power_pin_assignment_divergence"
        ]
        self.assertEqual(len(findings), 2)
        self.assertEqual(
            {item.evidence["peer_role"][0] for item in findings},
            {"ground/return", "supply"},
        )
        return_finding = next(
            item for item in findings if item.evidence["peer_role"] == ("ground/return",)
        )
        self.assertEqual(return_finding.evidence["U1.2"], ("GND",))
        self.assertEqual(return_finding.evidence["U2.2"], ("AGND",))
        self.assertIn("intentionally separate", return_finding.message)

        shared_power = evaluate(
            "synthetic-peer-component-power-pins",
            coach(peer_component_power_pins(split_return=False, split_supply=False)),
            DesignLintPolicy(),
        )
        dnp_peer = evaluate(
            "synthetic-peer-component-power-pins",
            coach(peer_component_power_pins(dnp=("U2",))),
            DesignLintPolicy(),
        )
        different_symbols = peer_component_power_pins().model_copy(
            update={
                "component_symbols": {
                    "U1": "Synthetic:PowerPeer",
                    "U2": "Synthetic:OtherPowerPeer",
                }
            }
        )
        different_symbol_report = evaluate(
            "synthetic-peer-component-power-pins",
            coach(different_symbols),
            DesignLintPolicy(),
        )
        for control in (shared_power, dnp_peer, different_symbol_report):
            self.assertNotIn(
                "component.peer_power_pin_assignment_divergence",
                {item.rule_id for item in control.findings},
            )

        open_return = peer_component_power_pins(split_return=False, split_supply=False).model_copy(
            update={"nets": {"+3V3": ("U1.1", "U2.1"), "GND": ("U1.2",)}}
        )
        open_report = evaluate(
            "synthetic-peer-component-power-pins",
            coach(open_return),
            DesignLintPolicy(),
        )
        open_rule_ids = {item.rule_id for item in open_report.findings}
        self.assertNotIn("component.peer_power_pin_assignment_divergence", open_rule_ids)
        self.assertIn("component.unconnected_return_pin", open_rule_ids)

    def test_peer_component_power_pin_splits_follow_rule_policy_and_ignore(self) -> None:
        source = peer_component_power_pins(split_supply=False)
        initial = evaluate(
            "synthetic-peer-component-return-split", coach(source), DesignLintPolicy()
        )
        finding = next(
            item
            for item in initial.findings
            if item.rule_id == "component.peer_power_pin_assignment_divergence"
        )
        blocking_policy = DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="component.peer_power_pin_assignment_divergence",
                    mode="block",
                    reason="Synthetic project requires reviewed peer return domains",
                ),
            )
        )
        blocked = evaluate("synthetic-peer-component-return-split", coach(source), blocking_policy)
        self.assertEqual(blocked.status, "FAIL")
        self.assertEqual(blocked.findings[0].mode, "block")

        off_policy = DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="component.peer_power_pin_assignment_divergence",
                    mode="off",
                    reason="Synthetic isolation control is explicitly reviewed",
                ),
            )
        )
        off = evaluate("synthetic-peer-component-return-split", coach(source), off_policy)
        self.assertEqual(off.status, "PASS")
        self.assertEqual(off.findings[0].disposition, "RULE_OFF")

        ignored_policy = DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id="component.peer_power_pin_assignment_divergence",
                    fingerprint=finding.fingerprint,
                    reason="Synthetic return-domain isolation is intentional",
                ),
            )
        )
        ignored = evaluate("synthetic-peer-component-return-split", coach(source), ignored_policy)
        self.assertEqual(ignored.status, "PASS")
        self.assertEqual(ignored.findings[0].disposition, "IGNORED")

        changed_source = source.model_copy(
            update={"nets": {"+3V3": ("U1.1", "U2.1"), "GND": ("U1.2",), "CHASSIS": ("U2.2",)}}
        )
        stale = evaluate(
            "synthetic-peer-component-return-split", coach(changed_source), ignored_policy
        )
        self.assertEqual(stale.status, "REVIEW")
        self.assertEqual(stale.stale_ignores, ignored_policy.ignores)

    def test_peer_component_power_pin_order_is_stable_and_commoning_clears_findings(self) -> None:
        source = peer_component_power_pins()
        original = evaluate(
            "synthetic-peer-component-power-pins", coach(source), DesignLintPolicy()
        )
        reordered_source = source.model_copy(
            update={
                "components": dict(reversed(tuple(source.components.items()))),
                "nets": dict(reversed(tuple(source.nets.items()))),
                "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
                "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
                "component_pin_numbers": dict(
                    reversed(tuple(source.component_pin_numbers.items()))
                ),
            }
        )
        reordered = evaluate(
            "synthetic-peer-component-power-pins",
            coach(reordered_source),
            DesignLintPolicy(),
        )
        original_findings = [
            item
            for item in original.findings
            if item.rule_id == "component.peer_power_pin_assignment_divergence"
        ]
        reordered_findings = [
            item
            for item in reordered.findings
            if item.rule_id == "component.peer_power_pin_assignment_divergence"
        ]
        self.assertEqual(
            [(item.evidence, item.fingerprint) for item in reordered_findings],
            [(item.evidence, item.fingerprint) for item in original_findings],
        )

        commoned = peer_component_power_pins(split_return=False, split_supply=False)
        corrected = evaluate(
            "synthetic-peer-component-power-pins", coach(commoned), DesignLintPolicy()
        )
        self.assertNotIn(
            "component.peer_power_pin_assignment_divergence",
            {item.rule_id for item in corrected.findings},
        )

    def test_open_findings_include_missing_power_and_separate_returns(self) -> None:
        report = evaluate("synthetic-ports", coach(observed()), DesignLintPolicy())
        self.assertEqual(report.status, "REVIEW")
        self.assertEqual(len(report.findings), 3)
        power = next(item for item in report.findings if item.subject.endswith("PWR"))
        self.assertEqual(power.evidence["J3.1"], ())
        self.assertEqual(power.disposition, "OPEN")
        self.assertEqual(
            {item.rule_id for item in report.findings},
            {"connector.repeated_pin_function", "net.numbered_returns"},
        )
        self.assertTrue(all(len(item.fingerprint) == 64 for item in report.findings))
        self.assertFalse(report.build_authorized)

    def test_connector_population_heuristics_ignore_dnp_instances(self) -> None:
        peers = NetlistContract(
            components={},
            nets={
                "USB_RETURN": ("J1.1",),
                "SERIAL_RETURN": ("J2.1",),
                "DATA_A": ("J2.3",),
                "DATA_B": ("J2.4",),
                "DATA_C": ("J2.5",),
            },
            component_symbols={"J1": "Synthetic:Port", "J2": "Synthetic:Port"},
            pin_functions={
                "J1.1": "GND",
                "J2.1": "GND",
                "J2.2": "VBUS",
                "J2.3": "1",
                "J2.4": "2",
                "J2.5": "3",
            },
        )
        populated = evaluate("synthetic-populated-ports", coach(peers), DesignLintPolicy())
        self.assertEqual(
            {item.rule_id for item in populated.findings},
            {"connector.repeated_pin_function", "connector.unconnected_supply_pin"},
        )

        dnp_peers = peers.model_copy(update={"dnp_components": ("j2",)})
        dnp = evaluate("synthetic-dnp-ports", coach(dnp_peers), DesignLintPolicy())
        self.assertFalse(dnp.findings)

        open_named_pins = NetlistContract(
            components={},
            nets={"DATA": ("J3.1",)},
            dnp_components=("J3",),
            component_symbols={"J3": "Synthetic:Port"},
            pin_functions={"J3.1": "DATA", "J3.2": "VBUS", "J3.3": "GND"},
        )
        open_pin_report = evaluate(
            "synthetic-dnp-open-pins", coach(open_named_pins), DesignLintPolicy()
        )
        self.assertFalse(open_pin_report.findings)

        no_return = multiconductor_connector(return_named=False)
        fitted_no_return = evaluate(
            "synthetic-fitted-no-return", coach(no_return), DesignLintPolicy()
        )
        self.assertIn(
            "connector.no_connected_return",
            {item.rule_id for item in fitted_no_return.findings},
        )
        dnp_no_return = evaluate(
            "synthetic-dnp-no-return",
            coach(no_return.model_copy(update={"dnp_components": ("J1",)})),
            DesignLintPolicy(),
        )
        self.assertNotIn(
            "connector.no_connected_return",
            {item.rule_id for item in dnp_no_return.findings},
        )

    def test_connector_identity_uses_standard_symbols_and_project_reviewed_custom_refs(
        self,
    ) -> None:
        fault = evaluate(
            "synthetic-standard-connector-identities",
            coach(standard_connector_identity_peers()),
            DesignLintPolicy(),
        )
        fault_rules = {item.rule_id for item in fault.findings}
        self.assertIn("connector.repeated_pin_function", fault_rules)
        self.assertNotIn("component.unconnected_supply_pin", fault_rules)
        self.assertNotIn("power.ic_rail_without_fitted_capacitor", fault_rules)
        repeated = next(
            item for item in fault.findings if item.rule_id == "connector.repeated_pin_function"
        )
        self.assertIn("U7.2", repeated.evidence)

        control = evaluate(
            "synthetic-standard-connector-control",
            coach(standard_connector_identity_peers(common_return=True, supply_connected=True)),
            DesignLintPolicy(),
        )
        self.assertFalse(control.findings)

        dnp = evaluate(
            "synthetic-standard-connector-dnp-control",
            coach(standard_connector_identity_peers(dnp=("U7",))),
            DesignLintPolicy(),
        )
        self.assertFalse(dnp.findings)

        generic_peer_fault = NetlistContract(
            components={
                reference: ComponentContract(value="Synthetic connector", footprint="")
                for reference in ("J1", "U7", "J2")
            },
            nets={
                "GND": ("J1.1", "U7.1", "J2.1"),
                "DATA": ("J1.2", "J2.2"),
            },
            component_symbols={
                reference: "Connector_Generic:Conn_01x02" for reference in ("J1", "U7", "J2")
            },
            component_pin_numbers={reference: ("1", "2") for reference in ("J1", "U7", "J2")},
            pin_functions={f"{reference}.1": "GND" for reference in ("J1", "U7", "J2")},
        )
        peer_fault = evaluate(
            "synthetic-standard-connector-peer-outlier",
            coach(generic_peer_fault),
            DesignLintPolicy(),
        )
        peer_finding = next(
            item
            for item in peer_fault.findings
            if item.rule_id == "connector.peer_pin_assignment_outlier"
        )
        self.assertIn("U7.2", peer_finding.evidence)
        peer_control = evaluate(
            "synthetic-standard-connector-peer-control",
            coach(
                generic_peer_fault.model_copy(
                    update={
                        "nets": {"GND": ("J1.1", "U7.1", "J2.1"), "DATA": ("J1.2", "U7.2", "J2.2")}
                    }
                )
            ),
            DesignLintPolicy(),
        )
        self.assertNotIn(
            "connector.peer_pin_assignment_outlier",
            {item.rule_id for item in peer_control.findings},
        )

        custom = custom_reviewed_connector_peers()
        unreviewed = evaluate(
            "synthetic-custom-connector-unreviewed",
            coach(custom),
            DesignLintPolicy(),
        )
        self.assertNotIn(
            "connector.repeated_pin_function",
            {item.rule_id for item in unreviewed.findings},
        )
        coverage = ConnectorCoverageReport(
            status="COMPLETE",
            scope="Synthetic project-reviewed interface references",
            inventory_review_basis="The synthetic interface inventory is complete",
            entries=(
                ConnectorCoverageEntry(
                    reference="A1",
                    status="COVERED",
                    interface_id="synthetic_port",
                    basis="The symbol was reviewed as an external connector",
                ),
                ConnectorCoverageEntry(
                    reference="A2",
                    status="COVERED",
                    interface_id="synthetic_port",
                    basis="The symbol was reviewed as an external connector",
                ),
            ),
        )
        reviewed = evaluate(
            "synthetic-custom-connector-reviewed",
            coach(custom),
            DesignLintPolicy(),
            connector_coverage=coverage,
        )
        self.assertIn(
            "connector.repeated_pin_function",
            {item.rule_id for item in reviewed.findings},
        )

        def return_coverage_netlist(*, connected_return: bool) -> NetlistContract:
            nets = {
                "DATA_A": ("U8.1",),
                "DATA_B": ("U8.2",),
                "DATA_C": ("U8.3",),
            }
            pin_functions = {f"U8.{number}": str(number) for number in (1, 2, 3)}
            pin_numbers = ("1", "2", "3")
            if connected_return:
                nets["GND"] = ("U8.4",)
                pin_functions["U8.4"] = "GND"
                pin_numbers = (*pin_numbers, "4")
            return NetlistContract(
                components={"U8": ComponentContract(value="Synthetic port", footprint="")},
                nets=nets,
                component_symbols={"U8": "Connector_Generic:Conn_01x04"},
                component_pin_numbers={"U8": pin_numbers},
                pin_functions=pin_functions,
            )

        no_return = evaluate(
            "synthetic-standard-connector-no-return",
            coach(return_coverage_netlist(connected_return=False)),
            DesignLintPolicy(),
        )
        self.assertIn(
            "connector.no_connected_return",
            {item.rule_id for item in no_return.findings},
        )
        with_return = evaluate(
            "synthetic-standard-connector-return-control",
            coach(return_coverage_netlist(connected_return=True)),
            DesignLintPolicy(),
        )
        self.assertNotIn(
            "connector.no_connected_return",
            {item.rule_id for item in with_return.findings},
        )

    def test_exact_ignore_resurfaces_after_connection_changes(self) -> None:
        initial = evaluate("synthetic-ports", coach(observed()), DesignLintPolicy())
        power = next(item for item in initial.findings if item.subject.endswith("PWR"))
        policy = DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id="connector.repeated_pin_function",
                    fingerprint=power.fingerprint,
                    reason="Independent review permits the currently unconnected third port",
                ),
            ),
        )
        ignored = evaluate("synthetic-ports", coach(observed()), policy)
        self.assertEqual(
            next(item for item in ignored.findings if item.subject.endswith("PWR")).disposition,
            "IGNORED",
        )
        changed = evaluate("synthetic-ports", coach(observed(True)), policy)
        self.assertEqual(changed.status, "REVIEW")
        self.assertEqual(changed.stale_ignores, policy.ignores)
        self.assertNotEqual(
            fingerprint(
                next(item for item in candidates(observed()) if item.subject.endswith("PWR"))
            ),
            fingerprint(
                next(item for item in candidates(observed(True)) if item.subject.endswith("PWR"))
            ),
        )

    def test_return_functions_across_connector_symbols_need_review(self) -> None:
        report = evaluate("synthetic-ports", coach(cross_symbol_returns()), DesignLintPolicy())
        self.assertEqual(report.status, "REVIEW")
        returns = [
            item
            for item in report.findings
            if item.subject == "multiple connector symbols: ground/return"
        ]
        self.assertEqual(len(returns), 1)
        self.assertEqual(
            returns[0].evidence,
            {"J1.4": ("USB_RETURN",), "J2.7": ("SERIAL_RETURN",)},
        )
        self.assertIn("common, bonded, or intentionally isolated", returns[0].message)

    def test_cross_connector_return_order_preserves_finding_and_commoning_clears_it(self) -> None:
        separate = cross_symbol_returns()
        reordered = separate.model_copy(
            update={
                "nets": dict(reversed(tuple(separate.nets.items()))),
                "component_symbols": dict(reversed(tuple(separate.component_symbols.items()))),
                "pin_functions": dict(reversed(tuple(separate.pin_functions.items()))),
            }
        )
        original_report = evaluate("synthetic-ports", coach(separate), DesignLintPolicy())
        reordered_report = evaluate("synthetic-ports", coach(reordered), DesignLintPolicy())
        original_finding = next(
            item
            for item in original_report.findings
            if item.subject == "multiple connector symbols: ground/return"
        )
        reordered_finding = next(
            item
            for item in reordered_report.findings
            if item.subject == "multiple connector symbols: ground/return"
        )
        self.assertEqual(
            (reordered_finding.fingerprint, reordered_finding.evidence),
            (original_finding.fingerprint, original_finding.evidence),
        )

        common_report = evaluate(
            "synthetic-ports-common",
            coach(cross_symbol_returns(common=True)),
            DesignLintPolicy(),
        )
        self.assertEqual(common_report.status, "PASS")
        self.assertNotIn(
            "connector.repeated_pin_function",
            {item.rule_id for item in common_report.findings},
        )

    def test_unconnected_return_pin_across_symbols_is_reported(self) -> None:
        report = evaluate(
            "synthetic-ports",
            coach(cross_symbol_returns(serial_connected=False)),
            DesignLintPolicy(),
        )
        returns = [
            item
            for item in report.findings
            if item.subject == "multiple connector symbols: ground/return"
        ]
        self.assertEqual(len(returns), 1)
        self.assertEqual(returns[0].evidence["J2.7"], ())

    def test_supply_pins_across_connector_symbols_need_review(self) -> None:
        report = evaluate("synthetic-ports", coach(cross_symbol_power()), DesignLintPolicy())
        self.assertEqual(report.status, "REVIEW")
        self.assertEqual(len(report.findings), 1)
        finding = report.findings[0]
        self.assertEqual(finding.subject, "multiple connector symbols: PWR")
        self.assertEqual(
            finding.evidence,
            {"J1.1": ("USB_SUPPLY",), "J2.1": ("SERIAL_SUPPLY",)},
        )
        self.assertIn("independent supplies", finding.message)

    def test_three_generic_power_pins_report_different_and_missing_sibling_assignments(
        self,
    ) -> None:
        report = evaluate(
            "synthetic-three-port-power",
            coach(three_port_power_pin_drift()),
            DesignLintPolicy(),
        )
        self.assertEqual(report.status, "REVIEW")
        self.assertEqual(
            {item.rule_id for item in report.findings},
            {"connector.repeated_pin_function", "net.numbered_power_rails"},
        )

        sibling_pins = next(
            item for item in report.findings if item.rule_id == "connector.repeated_pin_function"
        )
        self.assertEqual(
            sibling_pins.evidence,
            {"J1.1": ("+5V_1",), "J2.1": ("5V-2",), "J3.1": ()},
        )
        numbered_rails = next(
            item for item in report.findings if item.rule_id == "net.numbered_power_rails"
        )
        self.assertEqual(numbered_rails.evidence, {"+5V_1": ("J1.1",), "5V-2": ("J2.1",)})

        common = evaluate(
            "synthetic-three-port-power-common",
            coach(three_port_power_pin_drift(common=True)),
            DesignLintPolicy(),
        )
        self.assertEqual(common.status, "PASS")
        self.assertFalse(common.findings)

    def test_numbered_power_rail_order_is_stable_and_commoning_clears_the_hint(self) -> None:
        source = three_port_power_pin_drift()
        reordered = source.model_copy(
            update={
                "nets": dict(reversed(tuple(source.nets.items()))),
                "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
                "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            }
        )
        original_report = evaluate("synthetic-three-port-power", coach(source), DesignLintPolicy())
        reordered_report = evaluate(
            "synthetic-three-port-power", coach(reordered), DesignLintPolicy()
        )
        original_finding = next(
            item for item in original_report.findings if item.rule_id == "net.numbered_power_rails"
        )
        reordered_finding = next(
            item for item in reordered_report.findings if item.rule_id == "net.numbered_power_rails"
        )
        self.assertEqual(
            (reordered_finding.fingerprint, reordered_finding.evidence),
            (original_finding.fingerprint, original_finding.evidence),
        )

        common_report = evaluate(
            "synthetic-three-port-power-common",
            coach(three_port_power_pin_drift(common=True)),
            DesignLintPolicy(),
        )
        self.assertNotIn(
            "net.numbered_power_rails", {item.rule_id for item in common_report.findings}
        )

    def test_exact_symbol_peer_pin_outlier_localizes_missing_generic_contact(self) -> None:
        source = peer_connector_pin_assignments()
        report = evaluate("synthetic-peer-pin-gap", coach(source), DesignLintPolicy())
        findings = [
            item
            for item in report.findings
            if item.rule_id == "connector.peer_pin_assignment_outlier"
        ]
        self.assertEqual(len(findings), 1)
        self.assertEqual(report.status, "REVIEW")
        finding = findings[0]
        self.assertEqual(finding.subject, "Synthetic:PeripheralPort pin 2")
        self.assertEqual(finding.evidence["J1.2"], ("RETURN",))
        self.assertEqual(finding.evidence["J2.2"], ("RETURN",))
        self.assertEqual(finding.evidence["J3.2"], ())
        self.assertEqual(finding.evidence["outlier_pins"], ("J3.2",))
        self.assertIn("do not prove that their nets must be common", finding.message)

        blocked = evaluate(
            "synthetic-peer-pin-gap",
            coach(source),
            DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id="connector.peer_pin_assignment_outlier",
                        mode="block",
                        reason="Synthetic project requires disposition of sibling pin gaps",
                    ),
                )
            ),
        )
        self.assertEqual(blocked.status, "FAIL")
        self.assertEqual(blocked.findings[0].mode, "block")

        ignored = evaluate(
            "synthetic-peer-pin-gap",
            coach(source),
            DesignLintPolicy(
                ignores=(
                    DesignLintIgnore(
                        rule_id="connector.peer_pin_assignment_outlier",
                        fingerprint=finding.fingerprint,
                        reason="Synthetic review accepts the unconnected optional contact",
                    ),
                )
            ),
        )
        self.assertEqual(ignored.status, "PASS")
        self.assertEqual(ignored.findings[0].disposition, "IGNORED")

        disabled = evaluate(
            "synthetic-peer-pin-gap",
            coach(source),
            DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id="connector.peer_pin_assignment_outlier",
                        mode="off",
                        reason="Synthetic project reviewed the generic connector inventory",
                    ),
                )
            ),
        )
        self.assertEqual(disabled.status, "PASS")
        self.assertEqual(disabled.findings[0].disposition, "RULE_OFF")

        minority_net = evaluate(
            "synthetic-peer-pin-minority",
            coach(peer_connector_pin_assignments(("RETURN", "RETURN", "ISOLATED"))),
            DesignLintPolicy(),
        )
        minority = next(
            item
            for item in minority_net.findings
            if item.rule_id == "connector.peer_pin_assignment_outlier"
        )
        self.assertEqual(minority.evidence["outlier_pins"], ("J3.2",))
        self.assertNotIn(
            "connector.peer_pin_assignment_divergence",
            {item.rule_id for item in minority_net.findings},
        )

    def test_two_peer_open_generic_contact_prompts_and_supports_exact_ignore(self) -> None:
        source = peer_connector_pin_assignments(("+5V", None)).model_copy(
            update={
                "nets": {"+5V": ("J1.1",), "GND": ("J1.2", "J2.2")},
                "pin_functions": {
                    "J1.1": "Pin_1",
                    "J2.1": "Pin_1",
                    "J1.2": "GND",
                    "J2.2": "GND",
                },
            }
        )
        report = evaluate(
            "synthetic-two-peer-open-power-contact", coach(source), DesignLintPolicy()
        )
        findings = [
            item
            for item in report.findings
            if item.rule_id == "connector.peer_pin_assignment_outlier"
        ]
        self.assertEqual(report.status, "REVIEW")
        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual(finding.subject, "Synthetic:PeripheralPort pin 1")
        self.assertEqual(finding.evidence["J1.1"], ("+5V",))
        self.assertEqual(finding.evidence["J2.1"], ())
        self.assertEqual(finding.evidence["outlier_pins"], ("J2.1",))
        self.assertIn("do not prove that their nets must be common", finding.message)

        tied_control = source.model_copy(
            update={"nets": {"+5V": ("J1.1", "J2.1"), "GND": ("J1.2", "J2.2")}}
        )
        control_report = evaluate(
            "synthetic-two-peer-common-power-contact", coach(tied_control), DesignLintPolicy()
        )
        self.assertEqual(control_report.status, "PASS")
        self.assertNotIn(
            "connector.peer_pin_assignment_outlier",
            {item.rule_id for item in control_report.findings},
        )

        ignored = evaluate(
            "synthetic-two-peer-open-power-contact",
            coach(source),
            DesignLintPolicy(
                ignores=(
                    DesignLintIgnore(
                        rule_id="connector.peer_pin_assignment_outlier",
                        fingerprint=finding.fingerprint,
                        reason="Synthetic project reviewed this optional contact as intentionally open",
                    ),
                )
            ),
        )
        self.assertEqual(ignored.status, "PASS")
        self.assertEqual(ignored.findings[0].disposition, "IGNORED")

    def test_exact_symbol_peer_pin_controls_exclude_consistent_independent_and_dnp_cases(
        self,
    ) -> None:
        controls = (
            peer_connector_pin_assignments(("RETURN", "RETURN", "RETURN")),
            peer_connector_pin_assignments(("PORT_A", "PORT_B", "PORT_C")),
            peer_connector_pin_assignments(dnp=("J3",)),
        )
        for source in controls:
            with self.subTest(nets=source.nets, dnp=source.dnp_components):
                report = evaluate("synthetic-peer-pin-control", coach(source), DesignLintPolicy())
                self.assertNotIn(
                    "connector.peer_pin_assignment_outlier",
                    {item.rule_id for item in report.findings},
                )

        # Complete pin-role metadata remains covered by the named-function rule.
        named = peer_connector_pin_assignments().model_copy(
            update={
                "pin_functions": {
                    "J1.2": "GND",
                    "J2.2": "GND",
                    "J3.2": "GND",
                }
            }
        )
        named_report = evaluate(
            "synthetic-peer-pin-named-control", coach(named), DesignLintPolicy()
        )
        self.assertNotIn(
            "connector.peer_pin_assignment_outlier",
            {item.rule_id for item in named_report.findings},
        )

    def test_generic_connector_outlier_order_is_stable_and_completion_clears_it(self) -> None:
        source = peer_connector_pin_assignments()
        reordered = source.model_copy(
            update={
                "nets": dict(reversed(tuple(source.nets.items()))),
                "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
                "component_pin_numbers": dict(
                    reversed(tuple(source.component_pin_numbers.items()))
                ),
            }
        )
        original_report = evaluate("synthetic-peer-pin-gap", coach(source), DesignLintPolicy())
        reordered_report = evaluate("synthetic-peer-pin-gap", coach(reordered), DesignLintPolicy())
        original_finding = next(
            item
            for item in original_report.findings
            if item.rule_id == "connector.peer_pin_assignment_outlier"
        )
        reordered_finding = next(
            item
            for item in reordered_report.findings
            if item.rule_id == "connector.peer_pin_assignment_outlier"
        )
        self.assertEqual(
            (reordered_finding.fingerprint, reordered_finding.evidence),
            (original_finding.fingerprint, original_finding.evidence),
        )

        completed = evaluate(
            "synthetic-peer-pin-complete",
            coach(peer_connector_pin_assignments(("RETURN", "RETURN", "RETURN"))),
            DesignLintPolicy(),
        )
        self.assertNotIn(
            "connector.peer_pin_assignment_outlier",
            {item.rule_id for item in completed.findings},
        )

    def test_exact_symbol_peer_pin_divergence_reviews_conflicting_generic_assignments(self) -> None:
        source = peer_connector_pin_assignments(("PORT_A", "PORT_B"))
        report = evaluate("synthetic-peer-pin-divergence", coach(source), DesignLintPolicy())
        findings = [
            item
            for item in report.findings
            if item.rule_id == "connector.peer_pin_assignment_divergence"
        ]
        self.assertEqual(len(findings), 1)
        self.assertEqual(report.status, "REVIEW")
        finding = findings[0]
        self.assertEqual(finding.subject, "Synthetic:PeripheralPort pin 2")
        self.assertEqual(finding.evidence["J1.2"], ("PORT_A",))
        self.assertEqual(finding.evidence["J2.2"], ("PORT_B",))
        self.assertEqual(finding.evidence["missing_pin_function_pins"], ("J1.2", "J2.2"))
        self.assertIn("does not establish a required connection", finding.message)

        blocked = evaluate(
            "synthetic-peer-pin-divergence",
            coach(source),
            DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id="connector.peer_pin_assignment_divergence",
                        mode="block",
                        reason="Synthetic project requires review of generic peer pin maps",
                    ),
                )
            ),
        )
        self.assertEqual(blocked.status, "FAIL")

        ignored = evaluate(
            "synthetic-peer-pin-divergence",
            coach(source),
            DesignLintPolicy(
                ignores=(
                    DesignLintIgnore(
                        rule_id=finding.rule_id,
                        fingerprint=finding.fingerprint,
                        reason="Synthetic peer contacts are intentionally independent",
                    ),
                )
            ),
        )
        self.assertEqual(ignored.status, "PASS")
        self.assertEqual(ignored.findings[0].disposition, "IGNORED")

        disabled = evaluate(
            "synthetic-peer-pin-divergence",
            coach(source),
            DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id="connector.peer_pin_assignment_divergence",
                        mode="off",
                        reason="Synthetic project reviewed these peer contacts elsewhere",
                    ),
                )
            ),
        )
        self.assertEqual(disabled.status, "PASS")
        self.assertEqual(disabled.findings[0].disposition, "RULE_OFF")

    def test_generic_pin_function_placeholders_use_peer_assignment_rules(self) -> None:
        two_peer_placeholder = peer_connector_pin_assignments(("PORT_A", "PORT_B")).model_copy(
            update={"pin_functions": {"J1.2": "Pin_2", "J2.2": "Pin_2"}}
        )
        divergence = evaluate(
            "synthetic-generic-pin-placeholder-divergence",
            coach(two_peer_placeholder),
            DesignLintPolicy(),
        )
        self.assertEqual(
            {item.rule_id for item in divergence.findings},
            {"connector.peer_pin_assignment_divergence"},
        )
        finding = divergence.findings[0]
        self.assertEqual(
            finding.evidence["missing_pin_function_pins"],
            ("J1.2", "J2.2"),
        )
        self.assertIn("generic Pin_N placeholder is treated as unknown", finding.message)

        majority_placeholder = peer_connector_pin_assignments(
            ("PORT_A", "PORT_A", "PORT_B")
        ).model_copy(
            update={
                "pin_functions": {
                    "J1.2": "Pin_2",
                    "J2.2": "Pin_2",
                    "J3.2": "Pin_2",
                }
            }
        )
        outlier = evaluate(
            "synthetic-generic-pin-placeholder-outlier",
            coach(majority_placeholder),
            DesignLintPolicy(),
        )
        self.assertEqual(
            {item.rule_id for item in outlier.findings},
            {"connector.peer_pin_assignment_outlier"},
        )
        self.assertEqual(outlier.findings[0].evidence["outlier_pins"], ("J3.2",))

        common_placeholder = peer_connector_pin_assignments(
            ("PORT_A", "PORT_A", "PORT_A")
        ).model_copy(
            update={
                "pin_functions": {
                    "J1.2": "Pin_2",
                    "J2.2": "Pin_2",
                    "J3.2": "Pin_2",
                }
            }
        )
        control = evaluate(
            "synthetic-generic-pin-placeholder-control",
            coach(common_placeholder),
            DesignLintPolicy(),
        )
        self.assertFalse(control.findings)

    def test_peer_pin_divergence_order_is_stable_and_agreement_clears_it(self) -> None:
        source = peer_connector_pin_assignments(("PORT_A", "PORT_B"))
        reordered = source.model_copy(
            update={
                "nets": dict(reversed(tuple(source.nets.items()))),
                "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
                "component_pin_numbers": dict(
                    reversed(tuple(source.component_pin_numbers.items()))
                ),
            }
        )
        original_report = evaluate(
            "synthetic-peer-pin-divergence", coach(source), DesignLintPolicy()
        )
        reordered_report = evaluate(
            "synthetic-peer-pin-divergence", coach(reordered), DesignLintPolicy()
        )
        original_finding = next(
            item
            for item in original_report.findings
            if item.rule_id == "connector.peer_pin_assignment_divergence"
        )
        reordered_finding = next(
            item
            for item in reordered_report.findings
            if item.rule_id == "connector.peer_pin_assignment_divergence"
        )
        self.assertEqual(
            (reordered_finding.fingerprint, reordered_finding.evidence),
            (original_finding.fingerprint, original_finding.evidence),
        )

        agreed = evaluate(
            "synthetic-peer-pin-agreed",
            coach(peer_connector_pin_assignments(("PORT_A", "PORT_A"))),
            DesignLintPolicy(),
        )
        self.assertNotIn(
            "connector.peer_pin_assignment_divergence",
            {item.rule_id for item in agreed.findings},
        )

    def test_peer_pin_tie_uses_divergence_without_arbitrary_outlier(self) -> None:
        source = peer_connector_pin_assignments(("PORT_A", "PORT_A", "PORT_B", "PORT_B"))
        report = evaluate("synthetic-peer-pin-tie", coach(source), DesignLintPolicy())
        rule_ids = {item.rule_id for item in report.findings}
        self.assertNotIn("connector.peer_pin_assignment_outlier", rule_ids)
        self.assertIn("connector.peer_pin_assignment_divergence", rule_ids)
        finding = next(
            item
            for item in report.findings
            if item.rule_id == "connector.peer_pin_assignment_divergence"
        )
        self.assertEqual(finding.evidence["J1.2"], ("PORT_A",))
        self.assertEqual(finding.evidence["J2.2"], ("PORT_A",))
        self.assertEqual(finding.evidence["J3.2"], ("PORT_B",))
        self.assertEqual(finding.evidence["J4.2"], ("PORT_B",))

    def test_peer_pin_divergence_requires_conflict_and_missing_function_metadata(self) -> None:
        controls = (
            peer_connector_pin_assignments(("PORT_A", "PORT_A")),
            peer_connector_pin_assignments(("PORT_A", "PORT_B"), dnp=("J2",)),
        )
        for source in controls:
            with self.subTest(nets=source.nets, dnp=source.dnp_components):
                report = evaluate(
                    "synthetic-peer-pin-divergence-control", coach(source), DesignLintPolicy()
                )
                self.assertNotIn(
                    "connector.peer_pin_assignment_divergence",
                    {item.rule_id for item in report.findings},
                )

        named = peer_connector_pin_assignments(("PORT_A", "PORT_B")).model_copy(
            update={"pin_functions": {"J1.2": "GND", "J2.2": "GND"}}
        )
        named_report = evaluate(
            "synthetic-peer-pin-named-divergence", coach(named), DesignLintPolicy()
        )
        self.assertNotIn(
            "connector.peer_pin_assignment_divergence",
            {item.rule_id for item in named_report.findings},
        )

        partially_named = peer_connector_pin_assignments(("PORT_A", "PORT_B", "PORT_C")).model_copy(
            update={"pin_functions": {"J1.2": "GND", "J2.2": "GND"}}
        )
        partial_report = evaluate(
            "synthetic-peer-pin-partial-metadata",
            coach(partially_named),
            DesignLintPolicy(),
        )
        self.assertNotIn(
            "connector.peer_pin_assignment_divergence",
            {item.rule_id for item in partial_report.findings},
        )
        self.assertIn(
            "connector.repeated_pin_function",
            {item.rule_id for item in partial_report.findings},
        )

    def test_two_pin_led_directly_bridging_supply_and_return_is_configurable(self) -> None:
        source = led_rail_bridge_netlist()
        report = evaluate("synthetic-led-direct-rails", coach(source), DesignLintPolicy())
        findings = [
            item
            for item in report.findings
            if item.rule_id == "component.led_directly_across_supply_and_return"
        ]
        self.assertEqual(report.status, "REVIEW")
        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual(finding.subject, "D1: LED directly spans supply and return")
        self.assertEqual(finding.evidence["led_pins"], ("D1.1", "D1.2"))
        self.assertEqual(finding.evidence["positive_net"], ("+3V3",))
        self.assertEqual(finding.evidence["return_net"], ("GND",))
        self.assertIn("does not establish operating current", finding.message)

        blocked = evaluate(
            "synthetic-led-direct-rails",
            coach(source),
            DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id="component.led_directly_across_supply_and_return",
                        mode="block",
                        reason="Synthetic project requires explicit review of direct rail bridges",
                    ),
                )
            ),
        )
        self.assertEqual(blocked.status, "FAIL")

        ignored = evaluate(
            "synthetic-led-direct-rails",
            coach(source),
            DesignLintPolicy(
                ignores=(
                    DesignLintIgnore(
                        rule_id=finding.rule_id,
                        fingerprint=finding.fingerprint,
                        reason="Synthetic rail is independently current limited",
                    ),
                )
            ),
        )
        self.assertEqual(ignored.status, "PASS")
        self.assertEqual(ignored.findings[0].disposition, "IGNORED")

        disabled = evaluate(
            "synthetic-led-direct-rails",
            coach(source),
            DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id="component.led_directly_across_supply_and_return",
                        mode="off",
                        reason="Synthetic project reviews this LED through a separate driver contract",
                    ),
                )
            ),
        )
        self.assertEqual(disabled.status, "PASS")
        self.assertEqual(disabled.findings[0].disposition, "RULE_OFF")

    def test_led_bridge_is_order_stable_and_series_path_clears_it(self) -> None:
        rule_id = "component.led_directly_across_supply_and_return"
        source = led_rail_bridge_netlist()

        def lint(netlist: NetlistContract) -> tuple[str, DesignLintReport]:
            source_hash = hashlib.sha256(netlist.model_dump_json().encode("utf-8")).hexdigest()
            return source_hash, evaluate(
                "synthetic-led-direct-rails",
                coach(netlist, source_hash),
                DesignLintPolicy(),
            )

        source_hash, original = lint(source)
        self.assertEqual(original.netlist_sha256, source_hash)
        original_findings = {
            item.subject: (item.fingerprint, item.evidence)
            for item in original.findings
            if item.rule_id == rule_id
        }
        self.assertEqual(len(original_findings), 1)

        reordered_source = source.model_copy(
            update={
                "components": dict(reversed(tuple(source.components.items()))),
                "nets": dict(reversed(tuple(source.nets.items()))),
                "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
                "component_pin_numbers": dict(
                    reversed(tuple(source.component_pin_numbers.items()))
                ),
            }
        )
        reordered_hash, reordered = lint(reordered_source)
        self.assertNotEqual(source_hash, reordered_hash)
        self.assertEqual(reordered.netlist_sha256, reordered_hash)
        reordered_findings = {
            item.subject: (item.fingerprint, item.evidence)
            for item in reordered.findings
            if item.rule_id == rule_id
        }
        self.assertEqual(reordered_findings, original_findings)

        repaired_hash, repaired = lint(led_rail_bridge_netlist(series_resistor=True))
        self.assertNotEqual(source_hash, repaired_hash)
        self.assertNotIn(rule_id, {item.rule_id for item in repaired.findings})

    def test_led_rail_bridge_predicate_uses_exact_topology_and_symbol_controls(self) -> None:
        controls = (
            led_rail_bridge_netlist(series_resistor=True),
            led_rail_bridge_netlist(dnp=("D1",)),
            led_rail_bridge_netlist(symbol="Custom:LED"),
            led_rail_bridge_netlist(pin_numbers=("1",)),
            led_rail_bridge_netlist(positive_net="UNCLASSIFIED_SUPPLY"),
            led_rail_bridge_netlist(
                positive_net="LOCAL_RAIL",
                pin_functions={"U1.1": "VDD", "U2.1": "GND"},
            ),
        )
        for source in controls:
            with self.subTest(
                nets=source.nets,
                dnp=source.dnp_components,
                symbols=source.component_symbols,
            ):
                report = evaluate(
                    "synthetic-led-rail-bridge-control", coach(source), DesignLintPolicy()
                )
                self.assertNotIn(
                    "component.led_directly_across_supply_and_return",
                    {item.rule_id for item in report.findings},
                )

        parallel_resistor = led_rail_bridge_netlist(parallel_resistor=True)
        parallel_report = evaluate(
            "synthetic-led-parallel-resistor", coach(parallel_resistor), DesignLintPolicy()
        )
        self.assertIn(
            "component.led_directly_across_supply_and_return",
            {item.rule_id for item in parallel_report.findings},
        )

        recognized_pin_functions = led_rail_bridge_netlist(
            positive_net="LOCAL_RAIL",
            pin_functions={"U1.1": "VDD", "U2.1": "GND"},
        ).model_copy(
            update={
                "nets": {
                    "LOCAL_RAIL": ("D1.1", "U1.1"),
                    "LOCAL_RETURN": ("D1.2", "U2.1"),
                }
            }
        )
        recognized_report = evaluate(
            "synthetic-led-pin-function-rails",
            coach(recognized_pin_functions),
            DesignLintPolicy(),
        )
        self.assertIn(
            "component.led_directly_across_supply_and_return",
            {item.rule_id for item in recognized_report.findings},
        )

    def test_numbered_positive_supply_rail_names_need_review(self) -> None:
        observed_rails = NetlistContract(
            components={},
            nets={"+5V_1": ("J7.1",), "5V-2": ("J8.1",)},
            component_symbols={"J7": "Synthetic:UsbPower", "J8": "Synthetic:SerialPower"},
            pin_functions={"J7.1": "1", "J8.1": "1"},
        )
        report = evaluate("synthetic-numbered-power", coach(observed_rails), DesignLintPolicy())
        self.assertEqual(report.status, "REVIEW")
        self.assertEqual(len(report.findings), 1)
        finding = report.findings[0]
        self.assertEqual(finding.rule_id, "net.numbered_power_rails")
        self.assertEqual(finding.subject, "5V")
        self.assertEqual(finding.evidence, {"+5V_1": ("J7.1",), "5V-2": ("J8.1",)})
        self.assertIn("do not establish a required connection", finding.message)

        blocked = evaluate(
            "synthetic-numbered-power",
            coach(observed_rails),
            DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id="net.numbered_power_rails",
                        mode="block",
                        reason="Numbered external rails require explicit release review",
                    ),
                )
            ),
        )
        self.assertEqual(blocked.status, "FAIL")

        disabled = evaluate(
            "synthetic-numbered-power",
            coach(observed_rails),
            DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id="net.numbered_power_rails",
                        mode="off",
                        reason="This board intentionally isolates the named supply domains",
                    ),
                )
            ),
        )
        self.assertEqual(disabled.status, "PASS")
        self.assertEqual(disabled.findings[0].disposition, "RULE_OFF")

    def test_channel_prefixed_positive_supply_rail_names_need_review(self) -> None:
        observed_rails = NetlistContract(
            components={},
            nets={
                "CH2_VDD": ("J1.1",),
                "CH3_VDD": ("J2.1",),
                "P1_5V": ("J3.1",),
                "P2_5.0V": ("J4.1",),
                "RAIL4_VIN": ("J5.1",),
                "RAIL5_VIN": ("J6.1",),
                "CH2_SIGNAL": ("J1.2",),
                "CH3_SIGNAL": ("J2.2",),
                "CH2_VCC": ("J7.1",),
                "CH3_VDDIO": ("J8.1",),
            },
        )

        report = evaluate(
            "synthetic-channel-prefixed-power", coach(observed_rails), DesignLintPolicy()
        )

        self.assertEqual(report.status, "REVIEW")
        findings = {finding.subject: finding for finding in report.findings}
        self.assertEqual(set(findings), {"CH VDD", "P 5V", "RAIL VIN"})
        self.assertEqual(findings["CH VDD"].evidence, {"CH2_VDD": ("J1.1",), "CH3_VDD": ("J2.1",)})
        self.assertEqual(findings["P 5V"].evidence, {"P1_5V": ("J3.1",), "P2_5.0V": ("J4.1",)})
        self.assertEqual(
            findings["RAIL VIN"].evidence,
            {"RAIL4_VIN": ("J5.1",), "RAIL5_VIN": ("J6.1",)},
        )
        self.assertTrue(
            all(finding.rule_id == "net.numbered_power_rails" for finding in findings.values())
        )

    def test_channel_prefixed_power_name_controls_do_not_infer_or_merge_rails(self) -> None:
        controls = (
            NetlistContract(
                components={},
                nets={"CH2_SIGNAL": ("J1.1",), "CH3_SIGNAL": ("J2.1",)},
            ),
            NetlistContract(
                components={},
                nets={"CH2_VDD": ("J1.1",), "CH2_VCC": ("J2.1",)},
            ),
            NetlistContract(components={}, nets={"CH2_VDD": ("J1.1",)}),
        )

        for observed_rails in controls:
            with self.subTest(nets=tuple(observed_rails.nets)):
                report = evaluate(
                    "synthetic-channel-prefixed-power-control",
                    coach(observed_rails),
                    DesignLintPolicy(),
                )
                self.assertNotIn(
                    "net.numbered_power_rails", {item.rule_id for item in report.findings}
                )

    def test_numbered_power_rail_control_names_do_not_merge_distinct_or_ambiguous_rails(
        self,
    ) -> None:
        controls = (
            NetlistContract(
                components={},
                nets={"+5V_1": ("J1.1",), "1V8_2": ("J2.1",)},
                component_symbols={"J1": "Synthetic:PowerIn", "J2": "Synthetic:RegulatedOut"},
                pin_functions={"J1.1": "1", "J2.1": "1"},
            ),
            NetlistContract(
                components={},
                nets={"+5V1": ("J1.1",), "+5V2": ("J2.1",)},
                component_symbols={"J1": "Synthetic:PowerIn", "J2": "Synthetic:PowerOut"},
                pin_functions={"J1.1": "1", "J2.1": "1"},
            ),
        )
        for observed_rails in controls:
            with self.subTest(nets=tuple(observed_rails.nets)):
                report = evaluate(
                    "synthetic-numbered-power-control",
                    coach(observed_rails),
                    DesignLintPolicy(),
                )
                self.assertNotIn(
                    "net.numbered_power_rails", {item.rule_id for item in report.findings}
                )

    def test_unconnected_supply_pin_across_symbols_is_reported(self) -> None:
        report = evaluate(
            "synthetic-ports",
            coach(cross_symbol_power(serial_connected=False)),
            DesignLintPolicy(),
        )
        self.assertEqual(len(report.findings), 1)
        self.assertEqual(report.findings[0].evidence["J2.1"], ())

    def test_unconnected_supply_and_return_pins_without_a_peer_are_reported(self) -> None:
        isolated_named_pins = NetlistContract(
            components={},
            nets={"DATA": ("J1.2",)},
            component_symbols={"J1": "Synthetic:PowerPort"},
            pin_functions={"J1.1": "VCC", "J1.2": "TX", "J1.3": "GND"},
        )
        report = evaluate("synthetic-ports", coach(isolated_named_pins), DesignLintPolicy())
        self.assertEqual(report.status, "REVIEW")
        self.assertEqual(
            {item.rule_id for item in report.findings},
            {"connector.unconnected_supply_pin", "connector.unconnected_return_pin"},
        )
        self.assertEqual(
            {item.subject: item.evidence for item in report.findings},
            {"J1.1: VCC": {"J1.1": ()}, "J1.3: GND": {"J1.3": ()}},
        )

        negative_rail = NetlistContract(
            components={},
            nets={},
            component_symbols={"J9": "Synthetic:NegativeSupplyPort"},
            pin_functions={"J9.1": "-5V"},
        )
        negative_report = evaluate("synthetic-ports", coach(negative_rail), DesignLintPolicy())
        self.assertEqual(len(negative_report.findings), 1)
        self.assertEqual(negative_report.findings[0].rule_id, "connector.unconnected_supply_pin")

        configured = evaluate(
            "synthetic-ports",
            coach(isolated_named_pins),
            DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id="connector.unconnected_supply_pin",
                        mode="block",
                        reason="An unused port supply pin requires an owner decision",
                    ),
                    DesignLintRuleOverride(
                        rule_id="connector.unconnected_return_pin",
                        mode="off",
                        reason="This reviewed port does not use the return pin",
                    ),
                ),
            ),
        )
        self.assertEqual(configured.status, "FAIL")
        self.assertEqual(
            {item.rule_id: item.disposition for item in configured.findings},
            {
                "connector.unconnected_supply_pin": "OPEN",
                "connector.unconnected_return_pin": "RULE_OFF",
            },
        )

    def test_named_open_connector_supply_and_return_order_and_completion(self) -> None:
        source = NetlistContract(
            components={},
            nets={"DATA": ("J1.2",)},
            component_symbols={"J1": "Synthetic:PowerPort"},
            pin_functions={"J1.1": "VCC", "J1.2": "TX", "J1.3": "GND"},
        )
        reordered = source.model_copy(
            update={
                "nets": dict(reversed(tuple(source.nets.items()))),
                "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
                "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            }
        )
        original_report = evaluate("synthetic-ports", coach(source), DesignLintPolicy())
        reordered_report = evaluate("synthetic-ports", coach(reordered), DesignLintPolicy())
        target_rules = {"connector.unconnected_supply_pin", "connector.unconnected_return_pin"}
        original_findings = {
            item.rule_id: (item.fingerprint, item.evidence)
            for item in original_report.findings
            if item.rule_id in target_rules
        }
        reordered_findings = {
            item.rule_id: (item.fingerprint, item.evidence)
            for item in reordered_report.findings
            if item.rule_id in target_rules
        }
        self.assertEqual(set(original_findings), target_rules)
        self.assertEqual(reordered_findings, original_findings)

        supply_connected = source.model_copy(update={"nets": {**source.nets, "+5V": ("J1.1",)}})
        supply_report = evaluate(
            "synthetic-ports-supply-connected", coach(supply_connected), DesignLintPolicy()
        )
        supply_rules = {item.rule_id for item in supply_report.findings}
        self.assertNotIn("connector.unconnected_supply_pin", supply_rules)
        self.assertIn("connector.unconnected_return_pin", supply_rules)

        both_connected = supply_connected.model_copy(
            update={"nets": {**supply_connected.nets, "GND": ("J1.3",)}}
        )
        complete_report = evaluate(
            "synthetic-ports-complete", coach(both_connected), DesignLintPolicy()
        )
        complete_rules = {item.rule_id for item in complete_report.findings}
        self.assertFalse(target_rules & complete_rules)

    def test_i2c_pullup_hint_detects_missing_or_invalid_local_resistors(self) -> None:
        policy = policy_without_i2c_map_prompt()
        report = evaluate("synthetic-i2c", coach(i2c_netlist()), policy)
        self.assertEqual(report.status, "REVIEW")
        open_findings = [item for item in report.findings if item.disposition == "OPEN"]
        self.assertEqual(len(open_findings), 1)
        finding = open_findings[0]
        self.assertEqual(finding.rule_id, "bus.i2c_missing_pullup")
        self.assertEqual(finding.evidence["missing_pullups"], ("SDA", "SCL"))
        self.assertIn("internal or off-board pull-ups", finding.message)

        one_line = evaluate("synthetic-i2c", coach(i2c_netlist(pullups=("SDA",))), policy)
        one_line_finding = next(item for item in one_line.findings if item.disposition == "OPEN")
        self.assertEqual(one_line_finding.evidence["missing_pullups"], ("SCL",))

        connected = evaluate(
            "synthetic-i2c",
            coach(i2c_netlist(pullups=("SDA", "SCL"), resistance="4k7")),
            policy,
        )
        self.assertEqual(connected.status, "PASS")
        self.assertFalse([item for item in connected.findings if item.disposition == "OPEN"])

        for boundary in ("1k", "100k"):
            with self.subTest(resistance_boundary=boundary):
                boundary_report = evaluate(
                    "synthetic-i2c",
                    coach(i2c_netlist(pullups=("SDA", "SCL"), resistance=boundary)),
                    policy,
                )
                self.assertEqual(boundary_report.status, "PASS")
                self.assertFalse(
                    [item for item in boundary_report.findings if item.disposition == "OPEN"]
                )

        unpopulated_pullups = i2c_netlist(pullups=("SDA", "SCL")).model_copy(
            update={"dnp_components": ("R1", "R2")}
        )
        dnp_report = evaluate("synthetic-i2c", coach(unpopulated_pullups), policy)
        self.assertEqual(dnp_report.status, "REVIEW")
        dnp_finding = next(item for item in dnp_report.findings if item.disposition == "OPEN")
        self.assertEqual(dnp_finding.rule_id, "bus.i2c_missing_pullup")
        self.assertEqual(dnp_finding.evidence["missing_pullups"], ("SDA", "SCL"))

        invalid_value = evaluate(
            "synthetic-i2c",
            coach(i2c_netlist(pullups=("SDA", "SCL"), resistance="0R")),
            policy,
        )
        self.assertEqual(invalid_value.status, "REVIEW")
        invalid_finding = next(
            item for item in invalid_value.findings if item.disposition == "OPEN"
        )
        self.assertEqual(invalid_finding.evidence["missing_pullups"], ("SDA", "SCL"))

        negative_rail = evaluate(
            "synthetic-i2c",
            coach(i2c_netlist(pullups=("SDA", "SCL"), rail="-5V")),
            policy,
        )
        self.assertEqual(negative_rail.status, "REVIEW")

    def test_i2c_missing_pullup_is_order_stable_and_tracks_each_line_path(self) -> None:
        policy = policy_without_i2c_map_prompt()
        source = i2c_netlist()
        original = evaluate("synthetic-i2c", coach(source), policy)
        reordered_source = source.model_copy(
            update={
                "nets": dict(reversed(tuple(source.nets.items()))),
                "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            }
        )
        reordered = evaluate("synthetic-i2c", coach(reordered_source), policy)

        def finding_for(report: DesignLintReport) -> DesignLintFinding:
            return next(
                item for item in report.findings if item.rule_id == "bus.i2c_missing_pullup"
            )

        original_finding = finding_for(original)
        reordered_finding = finding_for(reordered)
        self.assertEqual(
            (reordered_finding.fingerprint, reordered_finding.evidence),
            (original_finding.fingerprint, original_finding.evidence),
        )
        self.assertEqual(original_finding.evidence["missing_pullups"], ("SDA", "SCL"))

        for connected_line, remaining_line in (("SDA", "SCL"), ("SCL", "SDA")):
            with self.subTest(connected_line=connected_line):
                partial = evaluate(
                    "synthetic-i2c",
                    coach(i2c_netlist(pullups=(connected_line,))),
                    policy,
                )
                finding = finding_for(partial)
                self.assertEqual(finding.evidence["missing_pullups"], (remaining_line,))

        complete = evaluate(
            "synthetic-i2c",
            coach(i2c_netlist(pullups=("SDA", "SCL"), resistance="4k7")),
            policy,
        )
        self.assertNotIn("bus.i2c_missing_pullup", {item.rule_id for item in complete.findings})

    def test_i2c_series_pullup_paths_are_bounded_and_unbranched(self) -> None:
        policy = policy_without_i2c_map_prompt()
        series_control = evaluate(
            "synthetic-i2c",
            coach(i2c_netlist_with_series_sda()),
            policy,
        )
        self.assertEqual(series_control.status, "PASS")
        self.assertFalse([item for item in series_control.findings if item.disposition == "OPEN"])

        too_weak = evaluate(
            "synthetic-i2c",
            coach(i2c_netlist_with_series_sda("56k", "56k")),
            policy,
        )
        too_weak_findings = [item for item in too_weak.findings if item.disposition == "OPEN"]
        self.assertEqual(len(too_weak_findings), 1)
        self.assertEqual(too_weak_findings[0].rule_id, "bus.i2c_missing_pullup")
        self.assertEqual(too_weak_findings[0].evidence["missing_pullups"], ("SDA",))

        branched = evaluate(
            "synthetic-i2c",
            coach(i2c_netlist_with_series_sda(branched_junction=True)),
            policy,
        )
        branched_findings = [item for item in branched.findings if item.disposition == "OPEN"]
        self.assertEqual(len(branched_findings), 1)
        self.assertEqual(branched_findings[0].rule_id, "bus.i2c_missing_pullup")
        self.assertEqual(branched_findings[0].evidence["missing_pullups"], ("SDA",))

        dnp = i2c_netlist_with_series_sda().model_copy(update={"dnp_components": ("R4",)})
        unpopulated = evaluate("synthetic-i2c", coach(dnp), policy)
        unpopulated_findings = [item for item in unpopulated.findings if item.disposition == "OPEN"]
        self.assertEqual(len(unpopulated_findings), 1)
        self.assertEqual(unpopulated_findings[0].evidence["missing_pullups"], ("SDA",))

    def test_i2c_pullup_hint_can_be_configured_per_project(self) -> None:
        report = evaluate(
            "synthetic-i2c",
            coach(i2c_netlist()),
            DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id="bus.i2c_missing_pullup",
                        mode="block",
                        reason="Every local I2C bus requires reviewed pull-up evidence",
                    ),
                ),
            ),
        )
        self.assertEqual(report.status, "FAIL")

    def test_i2c_parallel_pullups_are_reviewed_by_nominal_equivalent_resistance(self) -> None:
        low_resistance = evaluate(
            "synthetic-i2c",
            coach(i2c_netlist_with_parallel_sda()),
            DesignLintPolicy(),
        )
        findings = [
            item
            for item in low_resistance.findings
            if item.rule_id == "bus.i2c_low_equivalent_resistance"
        ]
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].evidence["lines"], ("SDA",))
        self.assertEqual(findings[0].evidence["equivalent_ohms"], ("SDA=500Ω",))
        self.assertEqual(
            findings[0].evidence["pullup_resistors"],
            ("R1=1000Ω to +3V3", "R3=1000Ω to +3V3"),
        )

        ordered = i2c_netlist_with_parallel_sda(parallel_resistance="1k5")
        reordered = ordered.model_copy(
            update={"components": dict(reversed(tuple(ordered.components.items())))}
        )
        first_candidate = next(
            item
            for item in candidates(ordered)
            if item.rule_id == "bus.i2c_low_equivalent_resistance"
        )
        reordered_candidate = next(
            item
            for item in candidates(reordered)
            if item.rule_id == "bus.i2c_low_equivalent_resistance"
        )
        self.assertEqual(fingerprint(first_candidate), fingerprint(reordered_candidate))

        accepted = evaluate(
            "synthetic-i2c",
            coach(i2c_netlist_with_parallel_sda("4k7")),
            DesignLintPolicy(),
        )
        self.assertFalse(
            any(item.rule_id == "bus.i2c_low_equivalent_resistance" for item in accepted.findings)
        )

        dnp_control = i2c_netlist_with_parallel_sda().model_copy(update={"dnp_components": ("R3",)})
        dnp_report = evaluate("synthetic-i2c", coach(dnp_control), DesignLintPolicy())
        self.assertFalse(
            any(item.rule_id == "bus.i2c_low_equivalent_resistance" for item in dnp_report.findings)
        )

        blocked = evaluate(
            "synthetic-i2c",
            coach(i2c_netlist_with_parallel_sda()),
            DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id="bus.i2c_low_equivalent_resistance",
                        mode="block",
                        reason="The reviewed I2C bus requires at least 1 kΩ nominal pull-up resistance",
                    ),
                )
            ),
        )
        self.assertEqual(blocked.status, "FAIL")

    def test_i2c_low_equivalent_includes_series_pullup_paths(self) -> None:
        low_resistance = evaluate(
            "synthetic-i2c",
            coach(
                i2c_netlist_with_series_sda(
                    "1k",
                    "1k",
                    base_pullups=("SDA", "SCL"),
                    base_resistance="1k",
                )
            ),
            DesignLintPolicy(),
        )
        findings = [
            item
            for item in low_resistance.findings
            if item.rule_id == "bus.i2c_low_equivalent_resistance"
        ]
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].evidence["lines"], ("SDA",))
        self.assertEqual(findings[0].evidence["equivalent_ohms"], ("SDA=666.667Ω",))
        self.assertEqual(
            findings[0].evidence["pullup_resistors"],
            ("R1=1000Ω to +3V3", "R3 + R4=2000Ω to +3V3"),
        )

        valid = evaluate(
            "synthetic-i2c",
            coach(
                i2c_netlist_with_series_sda(
                    "4.7k",
                    "4.7k",
                    base_pullups=("SDA", "SCL"),
                    base_resistance="4.7k",
                )
            ),
            DesignLintPolicy(),
        )
        self.assertFalse(
            any(item.rule_id == "bus.i2c_low_equivalent_resistance" for item in valid.findings)
        )

    def test_i2c_pullups_to_distinct_rail_families_request_review(self) -> None:
        policy = policy_without_i2c_map_prompt()
        fault = i2c_netlist_with_pullup_rails(("+3V3", "+5V"), ("+3V3",))
        report = evaluate("synthetic-i2c-rail-review", coach(fault), policy)
        findings = [
            item
            for item in report.findings
            if item.rule_id == "bus.i2c_multiple_pullup_rail_families"
        ]
        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual(finding.disposition, "OPEN")
        self.assertEqual(finding.evidence["rail_families"], ("3v3", "5v"))
        self.assertEqual(
            finding.evidence["pullup_paths"],
            (
                "SCL: R3=4700Ω to +3V3 (3v3)",
                "SDA: R1=4700Ω to +3V3 (3v3)",
                "SDA: R2=4700Ω to +5V (5v)",
            ),
        )
        self.assertIn("do not establish voltage compatibility", finding.message)

        separate_line_fault = evaluate(
            "synthetic-i2c-rail-review",
            coach(i2c_netlist_with_pullup_rails(("+3V3",), ("+5V",))),
            policy,
        )
        self.assertEqual(
            sum(
                item.rule_id == "bus.i2c_multiple_pullup_rail_families"
                for item in separate_line_fault.findings
            ),
            1,
        )

        for sda_rails, scl_rails in (
            (("+3V3",), ("+3V3",)),
            (("+3V3", "+3.3V"), ("3V3",)),
            (("+3V3", "+9V_CUSTOM"), ("+3V3",)),
        ):
            with self.subTest(sda_rails=sda_rails, scl_rails=scl_rails):
                control = evaluate(
                    "synthetic-i2c-rail-review",
                    coach(i2c_netlist_with_pullup_rails(sda_rails, scl_rails)),
                    policy,
                )
                self.assertNotIn(
                    "bus.i2c_multiple_pullup_rail_families",
                    {item.rule_id for item in control.findings},
                )

        dnp_resistor = i2c_netlist_with_pullup_rails(("+3V3", "+5V"), ("+3V3",)).model_copy(
            update={"dnp_components": ("R2",)}
        )
        dnp_report = evaluate("synthetic-i2c-rail-review", coach(dnp_resistor), policy)
        self.assertNotIn(
            "bus.i2c_multiple_pullup_rail_families",
            {item.rule_id for item in dnp_report.findings},
        )

        dnp_bus = i2c_netlist_with_pullup_rails(("+3V3", "+5V"), ("+3V3",)).model_copy(
            update={"dnp_components": ("U1",)}
        )
        dnp_bus_report = evaluate("synthetic-i2c-rail-review", coach(dnp_bus), policy)
        self.assertNotIn(
            "bus.i2c_multiple_pullup_rail_families",
            {item.rule_id for item in dnp_bus_report.findings},
        )

        blocked = evaluate(
            "synthetic-i2c-rail-review",
            coach(fault),
            DesignLintPolicy(
                rules=(
                    *policy.rules,
                    DesignLintRuleOverride(
                        rule_id="bus.i2c_multiple_pullup_rail_families",
                        mode="block",
                        reason="Synthetic project explicitly reviews I2C voltage domains",
                    ),
                )
            ),
        )
        self.assertEqual(blocked.status, "FAIL")

        disabled = evaluate(
            "synthetic-i2c-rail-review",
            coach(fault),
            DesignLintPolicy(
                rules=(
                    *policy.rules,
                    DesignLintRuleOverride(
                        rule_id="bus.i2c_multiple_pullup_rail_families",
                        mode="off",
                        reason="Synthetic fixture disables this review prompt",
                    ),
                )
            ),
        )
        self.assertEqual(disabled.status, "PASS")
        ignored = evaluate(
            "synthetic-i2c-rail-review",
            coach(fault),
            DesignLintPolicy(
                rules=policy.rules,
                ignores=(
                    DesignLintIgnore(
                        rule_id="bus.i2c_multiple_pullup_rail_families",
                        fingerprint=finding.fingerprint,
                        reason="Synthetic fixture records an intentional level-domain exception",
                    ),
                ),
            ),
        )
        self.assertEqual(ignored.status, "PASS")
        ignored_finding = next(
            item
            for item in ignored.findings
            if item.rule_id == "bus.i2c_multiple_pullup_rail_families"
        )
        self.assertEqual(ignored_finding.disposition, "IGNORED")

    def test_i2c_pullup_rail_finding_is_order_stable(self) -> None:
        source = i2c_netlist_with_pullup_rails(("+3V3", "+5V"), ("+3V3",))
        policy = policy_without_i2c_map_prompt()
        reordered = source.model_copy(
            update={
                "components": dict(reversed(tuple(source.components.items()))),
                "nets": dict(reversed(tuple(source.nets.items()))),
                "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            }
        )
        original_finding = next(
            item
            for item in evaluate("synthetic-i2c-rail-review", coach(source), policy).findings
            if item.rule_id == "bus.i2c_multiple_pullup_rail_families"
        )
        reordered_finding = next(
            item
            for item in evaluate("synthetic-i2c-rail-review", coach(reordered), policy).findings
            if item.rule_id == "bus.i2c_multiple_pullup_rail_families"
        )
        self.assertEqual(
            (original_finding.fingerprint, original_finding.evidence),
            (reordered_finding.fingerprint, reordered_finding.evidence),
        )

    def test_unconnected_component_supply_and_return_pins_need_review(self) -> None:
        report = evaluate(
            "synthetic-logic", coach(unconnected_component_power_pins()), DesignLintPolicy()
        )
        self.assertEqual(report.status, "REVIEW")
        self.assertEqual(
            {item.rule_id for item in report.findings},
            {"component.unconnected_supply_pin", "component.unconnected_return_pin"},
        )
        self.assertEqual(
            {item.subject: item.evidence for item in report.findings},
            {"U1.1: VDD": {"U1.1": ()}, "U1.2: GND": {"U1.2": ()}},
        )

        connected = evaluate(
            "synthetic-logic",
            coach(unconnected_component_power_pins(connected=True)),
            DesignLintPolicy(),
        )
        self.assertEqual(connected.status, "PASS")
        self.assertFalse(connected.findings)

    def test_component_open_power_pin_findings_are_order_stable_and_assignment_clears_them(
        self,
    ) -> None:
        base = unconnected_component_power_pins()
        source = base.model_copy(
            update={
                "components": {
                    **base.components,
                    "U2": ComponentContract(value="Unrelated logic", footprint=""),
                    "U3": ComponentContract(value="Unrelated logic", footprint=""),
                },
                "nets": {
                    **base.nets,
                    "AUX_A": ("U2.1",),
                    "AUX_B": ("U3.1",),
                },
                "component_symbols": {
                    **base.component_symbols,
                    "U2": "Synthetic:Logic",
                    "U3": "Synthetic:Logic",
                },
                "pin_functions": {
                    **base.pin_functions,
                    "U2.1": "DATA",
                    "U3.1": "DATA",
                },
            }
        )
        original = evaluate("synthetic-logic", coach(source), DesignLintPolicy())
        reordered_source = source.model_copy(
            update={
                "components": dict(reversed(tuple(source.components.items()))),
                "nets": dict(reversed(tuple(source.nets.items()))),
                "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
                "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            }
        )
        reordered = evaluate("synthetic-logic", coach(reordered_source), DesignLintPolicy())
        target_rules = {
            "component.unconnected_supply_pin",
            "component.unconnected_return_pin",
        }
        original_findings = {
            item.rule_id: (item.fingerprint, item.evidence)
            for item in original.findings
            if item.rule_id in target_rules
        }
        reordered_findings = {
            item.rule_id: (item.fingerprint, item.evidence)
            for item in reordered.findings
            if item.rule_id in target_rules
        }
        self.assertEqual(set(original_findings), target_rules)
        self.assertEqual(reordered_findings, original_findings)

        repaired = source.model_copy(
            update={
                "nets": {
                    **source.nets,
                    "+3V3": ("U1.1",),
                    "GND": ("U1.2",),
                }
            }
        )
        repaired_report = evaluate("synthetic-logic", coach(repaired), DesignLintPolicy())
        self.assertFalse(target_rules & {item.rule_id for item in repaired_report.findings})

    def test_can_termination_hint_requires_a_direct_resistor_and_is_configurable(self) -> None:
        unassigned = can_netlist().model_copy(update={"nets": {}})
        unassigned_report = evaluate("synthetic-can", coach(unassigned), DesignLintPolicy())
        self.assertEqual(
            {item.rule_id for item in unassigned_report.findings},
            {"bus.can_unconnected_line"},
        )
        self.assertEqual(
            {item.subject for item in unassigned_report.findings},
            {"U1.1: CANH", "U1.2: CAN_L"},
        )

        missing = evaluate("synthetic-can", coach(can_netlist()), DesignLintPolicy())
        self.assertEqual(missing.status, "REVIEW")
        self.assertEqual(len(missing.findings), 1)
        finding = missing.findings[0]
        self.assertEqual(finding.rule_id, "bus.can_missing_termination")
        self.assertEqual(
            finding.evidence,
            {
                "CANH": ("CAN_HIGH",),
                "CANL": ("CAN_LOW",),
                "pins": ("U1.1", "U1.2"),
                "termination": (),
            },
        )
        self.assertIn("external or split termination", finding.message)

        direct_termination = evaluate(
            "synthetic-can", coach(can_netlist("121R")), DesignLintPolicy()
        )
        self.assertEqual(direct_termination.status, "PASS")
        self.assertFalse(direct_termination.findings)

        dnp_termination = can_netlist("121R").model_copy(update={"dnp_components": ("R1",)})
        dnp_report = evaluate("synthetic-can", coach(dnp_termination), DesignLintPolicy())
        self.assertEqual(dnp_report.findings[0].rule_id, "bus.can_missing_termination")

        outside_range = evaluate("synthetic-can", coach(can_netlist("100R")), DesignLintPolicy())
        self.assertEqual(outside_range.status, "REVIEW")

        blocked = evaluate(
            "synthetic-can",
            coach(can_netlist()),
            DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id="bus.can_missing_termination",
                        mode="block",
                        reason="This board's CAN interface requires local termination",
                    ),
                ),
            ),
        )
        self.assertEqual(blocked.status, "FAIL")

    def test_can_termination_finding_is_order_stable_and_population_sensitive(self) -> None:
        source = can_netlist()
        original = evaluate("synthetic-can", coach(source), DesignLintPolicy())
        rule_id = "bus.can_missing_termination"
        original_finding = next(item for item in original.findings if item.rule_id == rule_id)
        reordered_source = source.model_copy(
            update={
                "components": dict(reversed(tuple(source.components.items()))),
                "nets": dict(reversed(tuple(source.nets.items()))),
                "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
                "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            }
        )
        reordered = evaluate("synthetic-can", coach(reordered_source), DesignLintPolicy())
        reordered_finding = next(item for item in reordered.findings if item.rule_id == rule_id)
        self.assertEqual(
            (reordered_finding.fingerprint, reordered_finding.evidence),
            (original_finding.fingerprint, original_finding.evidence),
        )

        fitted = evaluate("synthetic-can", coach(can_netlist("121R")), DesignLintPolicy())
        self.assertNotIn(rule_id, {item.rule_id for item in fitted.findings})

        dnp_source = can_netlist("121R").model_copy(update={"dnp_components": ("R1",)})
        dnp_report = evaluate("synthetic-can", coach(dnp_source), DesignLintPolicy())
        dnp_finding = next(item for item in dnp_report.findings if item.rule_id == rule_id)
        self.assertEqual(
            (dnp_finding.fingerprint, dnp_finding.evidence),
            (original_finding.fingerprint, original_finding.evidence),
        )

    def test_can_peer_pair_divergence_is_a_configurable_review_hint(self) -> None:
        rule_id = "bus.can_peer_assignment_divergence"
        fault = evaluate(
            "synthetic-can-peers",
            coach(can_peer_netlist(divergent_peer=True)),
            DesignLintPolicy(),
        )
        findings = tuple(item for item in fault.findings if item.rule_id == rule_id)
        self.assertEqual(fault.status, "REVIEW")
        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual(finding.mode, "review")
        self.assertEqual(
            finding.evidence,
            {
                "shared_role": ("CANH",),
                "shared_net": ("NET_A",),
                "complementary_role": ("CANL",),
                "complementary_nets": ("NET_B", "NET_C"),
                "participants": (
                    "U1:U1.1=CANH/NET_A;U1.2=CANL/NET_B",
                    "U2:U2.1=CANH/NET_A;U2.2=CANL/NET_B",
                    "U3:U3.1=CANH/NET_A;U3.2=CANL/NET_C",
                ),
            },
        )
        self.assertIn("do not establish common-bus intent", finding.message)

        for mode, expected_status in (("block", "FAIL"), ("off", "PASS")):
            report = evaluate(
                "synthetic-can-peers",
                coach(can_peer_netlist(divergent_peer=True)),
                DesignLintPolicy(
                    rules=(
                        DesignLintRuleOverride(
                            rule_id=rule_id,
                            mode=mode,
                            reason="Exercise the project-configurable review lifecycle",
                        ),
                    )
                ),
            )
            self.assertEqual(report.status, expected_status)

        ignored = evaluate(
            "synthetic-can-peers",
            coach(can_peer_netlist(divergent_peer=True)),
            DesignLintPolicy(
                ignores=(
                    DesignLintIgnore(
                        rule_id=rule_id,
                        fingerprint=finding.fingerprint,
                        reason="The split CAN pair is intentional in this synthetic control",
                    ),
                )
            ),
        )
        self.assertEqual(ignored.status, "PASS")
        self.assertEqual(
            next(item for item in ignored.findings if item.rule_id == rule_id).disposition,
            "IGNORED",
        )

        same_bus = evaluate("synthetic-can-peers", coach(can_peer_netlist()), DesignLintPolicy())
        separate_buses = evaluate(
            "synthetic-can-peers",
            coach(can_peer_netlist(separate_buses=True)),
            DesignLintPolicy(),
        )
        self.assertNotIn(rule_id, {item.rule_id for item in same_bus.findings})
        self.assertNotIn(rule_id, {item.rule_id for item in separate_buses.findings})

    def test_can_peer_pair_divergence_is_order_stable_and_dnp_aware(self) -> None:
        rule_id = "bus.can_peer_assignment_divergence"
        source = can_peer_netlist(divergent_peer=True)
        original = evaluate("synthetic-can-peers", coach(source), DesignLintPolicy())
        finding = next(item for item in original.findings if item.rule_id == rule_id)
        reordered_source = source.model_copy(
            update={
                "components": dict(reversed(tuple(source.components.items()))),
                "nets": dict(reversed(tuple(source.nets.items()))),
                "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
                "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            }
        )
        reordered = evaluate("synthetic-can-peers", coach(reordered_source), DesignLintPolicy())
        reordered_finding = next(item for item in reordered.findings if item.rule_id == rule_id)
        self.assertEqual(
            (reordered_finding.fingerprint, reordered_finding.evidence),
            (finding.fingerprint, finding.evidence),
        )

        dnp_peer = source.model_copy(update={"dnp_components": ("U3",)})
        dnp_report = evaluate("synthetic-can-peers", coach(dnp_peer), DesignLintPolicy())
        self.assertNotIn(rule_id, {item.rule_id for item in dnp_report.findings})

        repaired = evaluate("synthetic-can-peers", coach(can_peer_netlist()), DesignLintPolicy())
        self.assertNotIn(rule_id, {item.rule_id for item in repaired.findings})

    def test_spi_active_low_select_bias_hint_is_review_only_and_configurable(self) -> None:
        report = evaluate(
            "synthetic-spi-bias",
            coach(spi_active_low_select_netlist()),
            DesignLintPolicy(),
        )
        self.assertEqual(report.status, "REVIEW")
        self.assertEqual(len(report.findings), 1)
        finding = report.findings[0]
        self.assertEqual(finding.rule_id, "bus.spi_active_low_chip_select_without_pullup")
        self.assertEqual(finding.mode, "review")
        self.assertEqual(
            finding.evidence,
            {
                "net": ("SPI_CS_N",),
                "active_low_chip_select_pins": ("U2.1",),
                "recognized_positive_rails": ("+3V3",),
                "visible_pullup_paths": (),
            },
        )
        self.assertIn("internal or off-board bias", finding.message)

        blocked = evaluate(
            "synthetic-spi-bias",
            coach(spi_active_low_select_netlist()),
            DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id="bus.spi_active_low_chip_select_without_pullup",
                        mode="block",
                        reason="This project's reviewed SPI devices require an external idle bias",
                    ),
                )
            ),
        )
        self.assertEqual(blocked.status, "FAIL")

        disabled = evaluate(
            "synthetic-spi-bias",
            coach(spi_active_low_select_netlist()),
            DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id="bus.spi_active_low_chip_select_without_pullup",
                        mode="off",
                        reason="This interface's controller guarantees the inactive state",
                    ),
                )
            ),
        )
        self.assertEqual(disabled.status, "PASS")
        self.assertEqual(disabled.findings[0].disposition, "RULE_OFF")

        ignored = evaluate(
            "synthetic-spi-bias",
            coach(spi_active_low_select_netlist()),
            DesignLintPolicy(
                ignores=(
                    DesignLintIgnore(
                        rule_id=finding.rule_id,
                        fingerprint=finding.fingerprint,
                        reason="Reviewed internal reset bias for this synthetic peripheral",
                    ),
                )
            ),
        )
        self.assertEqual(ignored.status, "PASS")
        self.assertEqual(ignored.findings[0].disposition, "IGNORED")

    def test_spi_select_bias_hint_checks_recognized_paths_and_valid_controls(self) -> None:
        for values in (("10k",), ("4.7k", "4.7k")):
            with self.subTest(values=values):
                report = evaluate(
                    "synthetic-spi-bias",
                    coach(spi_active_low_select_netlist(resistor_values=values)),
                    DesignLintPolicy(),
                )
                self.assertFalse(
                    any(
                        item.rule_id == "bus.spi_active_low_chip_select_without_pullup"
                        for item in report.findings
                    )
                )

        controls = (
            spi_active_low_select_netlist(device_dnp=True),
            spi_active_low_select_netlist(select_function="CS"),
            spi_active_low_select_netlist(select_electrical_type="output"),
        )
        for control in controls:
            with self.subTest(control=control):
                self.assertFalse(
                    any(
                        item.rule_id == "bus.spi_active_low_chip_select_without_pullup"
                        for item in evaluate(
                            "synthetic-spi-bias", coach(control), DesignLintPolicy()
                        ).findings
                    )
                )

        for fault in (
            spi_active_low_select_netlist(resistor_values=("10k",), resistor_dnp=("R1",)),
            spi_active_low_select_netlist(resistor_values=("0R",)),
            spi_active_low_select_netlist(resistor_values=("220k",)),
            spi_active_low_select_netlist(resistor_values=("10k",), resistor_rail="GND"),
        ):
            with self.subTest(fault=fault):
                self.assertTrue(
                    any(
                        item.rule_id == "bus.spi_active_low_chip_select_without_pullup"
                        for item in evaluate(
                            "synthetic-spi-bias", coach(fault), DesignLintPolicy()
                        ).findings
                    )
                )

    def test_spi_select_bias_finding_is_order_stable_and_fitted_path_clears_it(self) -> None:
        def with_gpio_control(resistor_values: tuple[str, ...] = ()) -> NetlistContract:
            base = spi_active_low_select_netlist(resistor_values=resistor_values)
            return base.model_copy(
                update={
                    "nets": {**base.nets, "CONTROL_GPIO": ("U1.4",)},
                    "pin_functions": {**base.pin_functions, "U1.4": "GPIO"},
                    "pin_electrical_types": {**base.pin_electrical_types, "U1.4": "input"},
                    "component_pin_numbers": {
                        **base.component_pin_numbers,
                        "U1": (*base.component_pin_numbers["U1"], "4"),
                    },
                }
            )

        source = with_gpio_control()
        original = evaluate("synthetic-spi-bias", coach(source), DesignLintPolicy())
        rule_id = "bus.spi_active_low_chip_select_without_pullup"
        original_finding = next(item for item in original.findings if item.rule_id == rule_id)
        reordered_source = source.model_copy(
            update={
                "components": dict(reversed(tuple(source.components.items()))),
                "nets": dict(reversed(tuple(source.nets.items()))),
                "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
                "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
                "pin_electrical_types": dict(reversed(tuple(source.pin_electrical_types.items()))),
                "component_pin_numbers": dict(
                    reversed(tuple(source.component_pin_numbers.items()))
                ),
            }
        )
        reordered = evaluate("synthetic-spi-bias", coach(reordered_source), DesignLintPolicy())
        reordered_finding = next(item for item in reordered.findings if item.rule_id == rule_id)
        self.assertEqual(
            (reordered_finding.fingerprint, reordered_finding.evidence),
            (original_finding.fingerprint, original_finding.evidence),
        )

        repaired = evaluate(
            "synthetic-spi-bias",
            coach(with_gpio_control(("10k",))),
            DesignLintPolicy(),
        )
        self.assertNotIn(rule_id, {item.rule_id for item in repaired.findings})

    def test_complementary_pair_assignments_are_reviewed_without_inferred_requirements(
        self,
    ) -> None:
        missing_side = evaluate(
            "synthetic-usb", coach(complementary_usb_netlist(negative_net=None)), DesignLintPolicy()
        )
        pair_findings = [
            item
            for item in missing_side.findings
            if item.rule_id == "bus.complementary_pair_assignment"
        ]
        self.assertEqual(len(pair_findings), 1)
        self.assertEqual(pair_findings[0].evidence["positive_pins"], ("J1.1",))
        self.assertEqual(pair_findings[0].evidence["negative_pins"], ("J1.2",))
        self.assertEqual(pair_findings[0].evidence["negative_nets"], ())
        self.assertIn("lack a unique", pair_findings[0].message)

        shorted = complementary_usb_netlist(positive_net="USB_DATA", negative_net="USB_DATA")
        shorted_report = evaluate("synthetic-usb", coach(shorted), DesignLintPolicy())
        shorted_findings = [
            item
            for item in shorted_report.findings
            if item.rule_id == "bus.complementary_pair_assignment"
        ]
        self.assertEqual(len(shorted_findings), 1)
        self.assertIn("share one schematic net", shorted_findings[0].message)

        can_shorted = can_netlist().model_copy(update={"nets": {"CAN_BUS": ("U1.1", "U1.2")}})
        can_pair_findings = [
            item
            for item in evaluate("synthetic-can", coach(can_shorted), DesignLintPolicy()).findings
            if item.rule_id == "bus.complementary_pair_assignment"
        ]
        self.assertEqual(len(can_pair_findings), 1)

        for family, functions in (("TX", ("TXP", "TXN")), ("RX", ("RX+", "RX−"))):
            with self.subTest(family=family):
                paired = NetlistContract(
                    components={},
                    nets={"POS": ("U2.1",), "NEG": ("U2.2",)},
                    component_symbols={"U2": "Synthetic:DifferentialDevice"},
                    pin_functions={"U2.1": functions[0], "U2.2": functions[1]},
                )
                self.assertFalse(
                    any(
                        item.rule_id == "bus.complementary_pair_assignment"
                        for item in candidates(paired)
                    )
                )

        missing_counterpart = NetlistContract(
            components={},
            nets={"TX_POS": ("U3.1",)},
            component_symbols={"U3": "Synthetic:DifferentialDevice"},
            pin_functions={"U3.1": "TXP"},
        )
        missing_function = next(
            item
            for item in candidates(missing_counterpart)
            if item.rule_id == "bus.complementary_pair_assignment"
        )
        self.assertEqual(missing_function.evidence["negative_pins"], ())
        self.assertIn("absent from the symbol pin functions", missing_function.message)

        valid_pair = evaluate(
            "synthetic-usb", coach(complementary_usb_netlist()), DesignLintPolicy()
        )
        self.assertFalse(
            any(item.rule_id == "bus.complementary_pair_assignment" for item in valid_pair.findings)
        )

        intentionally_unused = complementary_usb_netlist(positive_net=None, negative_net=None)
        candidate = next(
            item
            for item in candidates(intentionally_unused)
            if item.rule_id == "bus.complementary_pair_assignment"
        )
        reviewed_unused = evaluate(
            "synthetic-usb",
            coach(intentionally_unused),
            DesignLintPolicy(
                ignores=(
                    DesignLintIgnore(
                        rule_id=candidate.rule_id,
                        fingerprint=fingerprint(candidate),
                        reason="This approved variant leaves its USB data pair unused",
                    ),
                )
            ),
        )
        self.assertEqual(reviewed_unused.status, "PASS")
        self.assertEqual(reviewed_unused.findings[0].disposition, "IGNORED")

    def test_usb_superspeed_connector_aliases_have_fault_and_control_coverage(self) -> None:
        rule_id = "bus.complementary_pair_assignment"
        for prefix in ("", "StdA_", "StdB_"):
            with self.subTest(prefix=prefix):
                functions = {
                    "J1.1": f"{prefix}SSTX+",
                    "J1.2": f"{prefix}SSTX−",
                    "J1.3": f"{prefix}SSRX+",
                    "J1.4": f"{prefix}SSRX−",
                }
                nets = {
                    "HOST_TO_PORT_POS": ("J1.1",),
                    "HOST_TO_PORT_NEG": ("J1.2",),
                    "PORT_TO_HOST_POS": ("J1.3",),
                    "PORT_TO_HOST_NEG": ("J1.4",),
                }
                control = NetlistContract(
                    components={},
                    nets=nets,
                    component_symbols={"J1": "Synthetic:UsbSuperSpeedPort"},
                    pin_functions=functions,
                )
                self.assertFalse(any(item.rule_id == rule_id for item in candidates(control)))

                fault = control.model_copy(
                    update={
                        "nets": {name: pins for name, pins in nets.items() if "J1.4" not in pins}
                    }
                )
                findings = [item for item in candidates(fault) if item.rule_id == rule_id]
                self.assertEqual(len(findings), 1)
                self.assertEqual(findings[0].subject, "J1: USB SuperSpeed RX pair")
                self.assertEqual(findings[0].evidence["positive_pins"], ("J1.3",))
                self.assertEqual(findings[0].evidence["negative_pins"], ("J1.4",))
                self.assertEqual(findings[0].evidence["negative_nets"], ())

        # USB-C has lane-indexed TX1/TX2 and RX1/RX2 pairs. Keep those outside
        # this single-pair-per-role heuristic until it can preserve lane identity.
        lane_indexed = NetlistContract(
            components={},
            nets={
                "TX1P": ("J2.1",),
                "TX1N": ("J2.2",),
                "TX2P": ("J2.3",),
                "TX2N": ("J2.4",),
                "RX1P": ("J2.5",),
                "RX1N": ("J2.6",),
                "RX2P": ("J2.7",),
                "RX2N": ("J2.8",),
            },
            component_symbols={"J2": "Synthetic:UsbTypeCPort"},
            pin_functions={
                "J2.1": "TX1+",
                "J2.2": "TX1−",
                "J2.3": "TX2+",
                "J2.4": "TX2−",
                "J2.5": "RX1+",
                "J2.6": "RX1−",
                "J2.7": "RX2+",
                "J2.8": "RX2−",
            },
        )
        self.assertFalse(any(item.rule_id == rule_id for item in candidates(lane_indexed)))

    def test_project_complementary_aliases_are_symbol_scoped_and_stale_maps_block(self) -> None:
        rule_id = "bus.complementary_pair_assignment"
        alias = ComplementaryPinFunctionAlias(
            symbol="Vendor:DualOutput",
            family="lane 0",
            positive_functions=("OUTP", "OUT_PLUS"),
            negative_functions=("OUTN", "OUT_MINUS"),
            basis="Synthetic project review maps these exact symbol functions as one pair",
        )
        policy = DesignLintPolicy(
            complementary_pin_function_alias_map=ComplementaryPinFunctionAliasMap(entries=(alias,))
        )

        def source(*, negative_net: str | None = None, dnp: bool = False) -> NetlistContract:
            nets = {"LANE0_P": ("U1.1",)}
            if negative_net is not None:
                nets[negative_net] = ("U1.2",)
            return NetlistContract(
                components={"U1": ComponentContract(value="Synthetic PHY", footprint="")},
                nets=nets,
                dnp_components=("U1",) if dnp else (),
                component_symbols={"U1": "Vendor:DualOutput"},
                pin_functions={"U1.1": "OUTP", "U1.2": "OUTN"},
                component_pin_numbers={"U1": ("1", "2")},
            )

        fault_source = source()
        fault = evaluate("synthetic-vendor-pair", coach(fault_source), policy)
        finding = next(item for item in fault.findings if item.rule_id == rule_id)
        self.assertEqual(fault.status, "REVIEW")
        self.assertEqual(finding.subject, "U1: lane 0 pair")
        self.assertEqual(finding.evidence["positive_pins"], ("U1.1",))
        self.assertEqual(finding.evidence["negative_pins"], ("U1.2",))
        self.assertEqual(finding.evidence["negative_nets"], ())
        self.assertEqual(finding.evidence["alias_symbol"], ("Vendor:DualOutput",))
        self.assertEqual(finding.evidence["alias_basis"], (alias.basis,))
        self.assertRegex(finding.evidence["alias_sha256"][0], r"^[a-f0-9]{64}$")

        baseline = evaluate("synthetic-vendor-pair", coach(fault_source), DesignLintPolicy())
        self.assertNotIn(rule_id, {item.rule_id for item in baseline.findings})

        valid = evaluate("synthetic-vendor-pair", coach(source(negative_net="LANE0_N")), policy)
        self.assertNotIn(rule_id, {item.rule_id for item in valid.findings})
        dnp = evaluate("synthetic-vendor-pair", coach(source(dnp=True)), policy)
        self.assertNotIn(rule_id, {item.rule_id for item in dnp.findings})

        reordered_alias = alias.model_copy(
            update={
                "positive_functions": tuple(reversed(alias.positive_functions)),
                "negative_functions": tuple(reversed(alias.negative_functions)),
            }
        )
        reordered_policy = DesignLintPolicy(
            complementary_pin_function_alias_map=ComplementaryPinFunctionAliasMap(
                entries=(reordered_alias,)
            )
        )
        reordered = evaluate("synthetic-vendor-pair", coach(fault_source), reordered_policy)
        reordered_finding = next(item for item in reordered.findings if item.rule_id == rule_id)
        self.assertEqual(
            (reordered_finding.fingerprint, reordered_finding.evidence),
            (finding.fingerprint, finding.evidence),
        )

        changed_basis = alias.model_copy(update={"basis": "Synthetic alternate review record"})
        changed_policy = DesignLintPolicy(
            complementary_pin_function_alias_map=ComplementaryPinFunctionAliasMap(
                entries=(changed_basis,)
            )
        )
        changed = evaluate("synthetic-vendor-pair", coach(fault_source), changed_policy)
        changed_finding = next(item for item in changed.findings if item.rule_id == rule_id)
        self.assertNotEqual(changed_finding.fingerprint, finding.fingerprint)

        stale_alias = alias.model_copy(
            update={
                "positive_functions": ("OLD_POSITIVE",),
                "negative_functions": ("OLD_NEGATIVE",),
            }
        )
        stale = evaluate(
            "synthetic-vendor-pair",
            coach(fault_source),
            DesignLintPolicy(
                complementary_pin_function_alias_map=ComplementaryPinFunctionAliasMap(
                    entries=(stale_alias,)
                )
            ),
        )
        self.assertEqual(stale.status, "BLOCKED")
        self.assertTrue(any("is stale" in item for item in stale.issues))
        self.assertTrue(
            any(
                "Refresh the project complementary pin-function alias map" in item
                for item in stale.next_actions
            )
        )

        wrong_symbol = alias.model_copy(update={"symbol": "Vendor:RenamedDevice"})
        exact_identity = evaluate(
            "synthetic-vendor-pair",
            coach(fault_source),
            DesignLintPolicy(
                complementary_pin_function_alias_map=ComplementaryPinFunctionAliasMap(
                    entries=(wrong_symbol,)
                )
            ),
        )
        self.assertEqual(exact_identity.status, "BLOCKED")
        self.assertTrue(
            any("no exact native symbol instance" in item for item in exact_identity.issues)
        )

        repeated_builtin = alias.model_copy(
            update={"positive_functions": ("TX+",), "negative_functions": ("TX-",)}
        )
        built_in_collision = evaluate(
            "synthetic-vendor-pair",
            coach(fault_source),
            DesignLintPolicy(
                complementary_pin_function_alias_map=ComplementaryPinFunctionAliasMap(
                    entries=(repeated_builtin,)
                )
            ),
        )
        self.assertEqual(built_in_collision.status, "BLOCKED")
        self.assertTrue(any("repeats built-in" in item for item in built_in_collision.issues))

        with self.assertRaises(ValidationError):
            ComplementaryPinFunctionAlias(
                symbol="Vendor:DualOutput",
                family="ambiguous",
                positive_functions=("OUTP",),
                negative_functions=(" out_p ",),
                basis="Invalid overlapping aliases",
            )

    def test_complementary_pair_finding_is_order_stable_and_assignment_clears_it(self) -> None:
        rule_id = "bus.complementary_pair_assignment"
        source = complementary_usb_netlist(negative_net=None)

        def lint(netlist: NetlistContract) -> tuple[str, DesignLintReport]:
            source_hash = hashlib.sha256(netlist.model_dump_json().encode("utf-8")).hexdigest()
            return source_hash, evaluate(
                "synthetic-usb", coach(netlist, source_hash), DesignLintPolicy()
            )

        source_hash, original = lint(source)
        self.assertEqual(original.netlist_sha256, source_hash)
        original_findings = {
            item.subject: (item.fingerprint, item.evidence)
            for item in original.findings
            if item.rule_id == rule_id
        }
        self.assertEqual(len(original_findings), 1)

        reordered_source = source.model_copy(
            update={
                "nets": dict(reversed(tuple(source.nets.items()))),
                "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
                "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            }
        )
        reordered_hash, reordered = lint(reordered_source)
        self.assertNotEqual(source_hash, reordered_hash)
        self.assertEqual(reordered.netlist_sha256, reordered_hash)
        reordered_findings = {
            item.subject: (item.fingerprint, item.evidence)
            for item in reordered.findings
            if item.rule_id == rule_id
        }
        self.assertEqual(reordered_findings, original_findings)

        repaired_hash, repaired = lint(complementary_usb_netlist())
        self.assertNotEqual(source_hash, repaired_hash)
        self.assertNotIn(rule_id, {item.rule_id for item in repaired.findings})

    def test_named_complementary_nets_prompt_for_reviewed_pair_requirements(self) -> None:
        source = complementary_usb_netlist()
        default = evaluate("synthetic-usb-pair", coach(source), DesignLintPolicy())
        self.assertEqual(default.status, "REVIEW")
        finding = next(
            item
            for item in default.findings
            if item.rule_id == "signal.named_pair_without_reviewed_requirement"
        )
        self.assertEqual(finding.subject, "USB_DP / USB_DM")
        self.assertEqual(finding.evidence["naming_pattern"], ("_DP/_DM",))
        self.assertEqual(finding.evidence["positive_references"], ("J1.1",))
        self.assertIn("does not establish pair intent", finding.message)

        plus_minus_sources = (
            NetlistContract(
                components={},
                nets={"USB_D+": ("J1.1",), "USB_D-": ("J1.2",)},
            ),
            NetlistContract(
                components={
                    "R1": ComponentContract(value="22R", footprint=""),
                    "R2": ComponentContract(value="22R", footprint=""),
                },
                nets={
                    "USB_D+": ("J1.1", "R1.1"),
                    "USB_DP_PHY": ("R1.2",),
                    "USB_D-": ("J1.2", "R2.1"),
                    "USB_DM_PHY": ("R2.2",),
                },
                component_symbols={
                    "J1": "Connector:USB_A",
                    "R1": "Device:R",
                    "R2": "Device:R",
                },
                pin_functions={
                    "J1.1": "D+",
                    "J1.2": "D-",
                    "R1.1": "1",
                    "R1.2": "2",
                    "R2.1": "1",
                    "R2.2": "2",
                },
                component_pin_numbers={
                    "J1": ("1", "2"),
                    "R1": ("1", "2"),
                    "R2": ("1", "2"),
                },
            ),
        )
        for index, plus_minus_source in enumerate(plus_minus_sources):
            plus_minus_report = evaluate(
                f"synthetic-usb-plus-minus-{index}",
                coach(plus_minus_source),
                DesignLintPolicy(),
            )
            plus_minus_finding = next(
                item
                for item in plus_minus_report.findings
                if item.rule_id == "signal.named_pair_without_reviewed_requirement"
            )
            self.assertEqual(plus_minus_finding.subject, "USB_D+ / USB_D-")

        requirement_map = PcbDifferentialPairRuleMap(
            basis="Synthetic reviewed interface requirement",
            requirements=(
                PcbDifferentialPairRuleRequirement(
                    id="usb-data",
                    basis="Synthetic pair geometry requirement",
                    positive_net="USB_DP",
                    negative_net="USB_DM",
                    pair_selector="USB_",
                    track_width=PcbDrcMinMaxRequirement(min_nm=250_000),
                ),
            ),
        )
        self.assertFalse(
            any(
                item.rule_id == "signal.named_pair_without_reviewed_requirement"
                for item in candidates(source, pcb_differential_pair_rule_map=requirement_map)
            )
        )

        blocking = evaluate(
            "synthetic-usb-pair",
            coach(source),
            DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id="signal.named_pair_without_reviewed_requirement",
                        mode="block",
                        reason="Review every named complementary net pair",
                    ),
                )
            ),
        )
        self.assertEqual(blocking.status, "FAIL")

        disabled = evaluate(
            "synthetic-usb-pair",
            coach(source),
            DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id="signal.named_pair_without_reviewed_requirement",
                        mode="off",
                        reason="This project tracks pair limits in a separate review record",
                    ),
                )
            ),
        )
        self.assertEqual(disabled.status, "PASS")
        off_finding = next(
            item
            for item in disabled.findings
            if item.rule_id == "signal.named_pair_without_reviewed_requirement"
        )
        self.assertEqual(off_finding.disposition, "RULE_OFF")

        ignored = evaluate(
            "synthetic-usb-pair",
            coach(source),
            DesignLintPolicy(
                ignores=(
                    DesignLintIgnore(
                        rule_id=finding.rule_id,
                        fingerprint=finding.fingerprint,
                        reason="The synthetic low-speed pair has a reviewed exception",
                    ),
                )
            ),
        )
        self.assertEqual(ignored.status, "PASS")
        ignored_finding = next(
            item
            for item in ignored.findings
            if item.rule_id == "signal.named_pair_without_reviewed_requirement"
        )
        self.assertEqual(ignored_finding.disposition, "IGNORED")

        self.assertFalse(
            any(
                item.rule_id == "signal.named_pair_without_reviewed_requirement"
                for item in candidates(
                    NetlistContract(
                        components={},
                        nets={"VIP": ("U1.1",), "VIN": ("U1.2",)},
                    )
                )
            )
        )

    def test_named_pair_hint_is_stable_and_reviewed_map_suppresses_only_the_hint(self) -> None:
        rule_id = "signal.named_pair_without_reviewed_requirement"
        source = complementary_usb_netlist()
        requirements = (
            PcbDifferentialPairRuleRequirement(
                id="usb-data",
                basis="Synthetic USB pair geometry requirement",
                positive_net="USB_DP",
                negative_net="USB_DM",
                pair_selector="USB_",
                track_width=PcbDrcMinMaxRequirement(min_nm=250_000),
            ),
            PcbDifferentialPairRuleRequirement(
                id="can-data",
                basis="Synthetic CAN pair geometry requirement",
                positive_net="CANH",
                negative_net="CANL",
                pair_selector="CAN",
                track_width=PcbDrcMinMaxRequirement(min_nm=250_000),
            ),
        )
        requirement_map = PcbDifferentialPairRuleMap(
            basis="Synthetic reviewed interface requirements",
            requirements=requirements,
        )
        reordered_map = requirement_map.model_copy(
            update={"requirements": tuple(reversed(requirement_map.requirements))}
        )

        def lint(
            netlist: NetlistContract,
            pair_map: PcbDifferentialPairRuleMap | None = None,
        ) -> tuple[str, DesignLintReport]:
            source_hash = hashlib.sha256(netlist.model_dump_json().encode("utf-8")).hexdigest()
            report = evaluate(
                "synthetic-usb-pair",
                coach(netlist, source_hash),
                DesignLintPolicy(pcb_differential_pair_rule_map=pair_map),
            )
            return source_hash, report

        source_hash, original = lint(source)
        original_finding = next(item for item in original.findings if item.rule_id == rule_id)
        reordered_source = source.model_copy(
            update={
                "nets": dict(reversed(tuple(source.nets.items()))),
                "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
                "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            }
        )
        reordered_hash, reordered = lint(reordered_source)
        reordered_finding = next(item for item in reordered.findings if item.rule_id == rule_id)
        self.assertNotEqual(source_hash, reordered_hash)
        self.assertEqual(original.netlist_sha256, source_hash)
        self.assertEqual(reordered.netlist_sha256, reordered_hash)
        self.assertEqual(
            (reordered_finding.subject, reordered_finding.fingerprint, reordered_finding.evidence),
            (original_finding.subject, original_finding.fingerprint, original_finding.evidence),
        )

        reviewed_hash, reviewed = lint(source, requirement_map)
        reviewed_coverage = reviewed.pcb_differential_pair_rules
        expected_map_hash = hashlib.sha256(
            requirement_map.model_dump_json().encode("utf-8")
        ).hexdigest()
        self.assertEqual(reviewed.netlist_sha256, reviewed_hash)
        self.assertNotIn(rule_id, {item.rule_id for item in reviewed.findings})
        self.assertEqual(reviewed_coverage.status, "BLOCKED")
        self.assertEqual(reviewed_coverage.map_sha256, expected_map_hash)
        self.assertIn("native DRC rule evidence was not supplied", reviewed_coverage.issue or "")

        reordered_source_hash, reordered_reviewed = lint(reordered_source, reordered_map)
        reordered_map_hash = hashlib.sha256(
            reordered_map.model_dump_json().encode("utf-8")
        ).hexdigest()
        self.assertEqual(reordered_reviewed.netlist_sha256, reordered_source_hash)
        self.assertNotEqual(expected_map_hash, reordered_map_hash)
        self.assertNotIn(rule_id, {item.rule_id for item in reordered_reviewed.findings})
        self.assertEqual(
            reordered_reviewed.pcb_differential_pair_rules.map_sha256,
            reordered_map_hash,
        )

        unavailable = ContractCoachReport(
            status="BLOCKED",
            project_id="synthetic-ports",
            issues=("Synthetic native evidence unavailable",),
        )
        unavailable_report = evaluate(
            "synthetic-usb-pair",
            unavailable,
            DesignLintPolicy(pcb_differential_pair_rule_map=requirement_map),
        )
        self.assertEqual(unavailable_report.status, "BLOCKED")
        self.assertEqual(unavailable_report.pcb_differential_pair_rules.status, "BLOCKED")
        self.assertEqual(
            unavailable_report.pcb_differential_pair_rules.map_sha256, expected_map_hash
        )

        disabled_policy = DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id="pcb.differential_pair_rule_coverage",
                    mode="off",
                    reason="Synthetic control for the explicit pair-map lifecycle",
                ),
            ),
            pcb_differential_pair_rule_map=requirement_map,
        )
        disabled = evaluate(
            "synthetic-usb-pair",
            coach(source),
            disabled_policy,
        )
        self.assertEqual(disabled.pcb_differential_pair_rules.status, "DISABLED")
        self.assertEqual(disabled.pcb_differential_pair_rules.map_sha256, expected_map_hash)

        unavailable_disabled = evaluate("synthetic-usb-pair", unavailable, disabled_policy)
        self.assertEqual(unavailable_disabled.pcb_differential_pair_rules.status, "DISABLED")
        self.assertEqual(
            unavailable_disabled.pcb_differential_pair_rules.map_sha256,
            expected_map_hash,
        )

    def test_unconnected_i2c_spi_and_usb_c_control_pins_are_distinct_review_rules(self) -> None:
        report = evaluate(
            "synthetic-interfaces", coach(unconnected_protocol_pins()), DesignLintPolicy()
        )
        self.assertEqual(report.status, "REVIEW")
        self.assertEqual(
            {item.rule_id for item in report.findings},
            {
                "bus.i2c_unconnected_pin",
                "bus.spi_unconnected_chip_select",
                "bus.usb_c_unconnected_cc_pin",
            },
        )
        self.assertEqual(
            {item.subject for item in report.findings},
            {
                "U1.1: SDA",
                "U1.2: I2C_SCL",
                "U2.1: CS_N",
                "J1.1: CC1",
                "J1.2: CC2",
            },
        )

        assigned = unconnected_protocol_pins().model_copy(
            update={
                "nets": {
                    "I2C_SDA": ("U1.1",),
                    "I2C_SCL": ("U1.2",),
                    "SPI_CS": ("U2.1",),
                    "USB_CC1": ("J1.1",),
                    "USB_CC2": ("J1.2",),
                }
            }
        )
        connected = evaluate("synthetic-interfaces", coach(assigned), DesignLintPolicy())
        self.assertEqual(
            {item.rule_id for item in connected.findings},
            {"bus.i2c_missing_pullup", "bus.i2c_unmapped_responder"},
        )

    def test_unconnected_protocol_pin_candidates_are_order_stable_and_clear_individually(
        self,
    ) -> None:
        base = unconnected_protocol_pins()
        source = base.model_copy(
            update={
                "nets": {
                    "CONTROL_GPIO": ("U1.3",),
                    "SPI_DATA": ("U2.2",),
                },
                "pin_functions": {
                    **base.pin_functions,
                    "U1.3": "GPIO",
                    "U2.2": "MISO",
                },
            }
        )
        target_rules = {
            "bus.i2c_unconnected_pin",
            "bus.spi_unconnected_chip_select",
            "bus.usb_c_unconnected_cc_pin",
        }
        original = evaluate("synthetic-interfaces", coach(source), DesignLintPolicy())
        reordered_source = source.model_copy(
            update={
                "nets": dict(reversed(tuple(source.nets.items()))),
                "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
                "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            }
        )
        reordered = evaluate("synthetic-interfaces", coach(reordered_source), DesignLintPolicy())

        def selected_findings(
            report: DesignLintReport,
        ) -> dict[str, tuple[str, str, dict[str, tuple[str, ...]]]]:
            return {
                item.subject: (item.rule_id, item.fingerprint, item.evidence)
                for item in report.findings
                if item.rule_id in target_rules
            }

        original_findings = selected_findings(original)
        self.assertEqual(len(original_findings), 5)
        self.assertEqual(selected_findings(reordered), original_findings)

        for subject, original_finding in original_findings.items():
            pin = subject.split(":", maxsplit=1)[0]
            assigned = source.model_copy(
                update={
                    "nets": {
                        **source.nets,
                        f"ASSIGNED_{pin.replace('.', '_')}": (pin,),
                    }
                }
            )
            assigned_report = evaluate("synthetic-interfaces", coach(assigned), DesignLintPolicy())
            expected = dict(original_findings)
            del expected[subject]
            self.assertEqual(selected_findings(assigned_report), expected, original_finding)

    def test_unconnected_can_lines_are_order_stable_and_each_assignment_clears_one(self) -> None:
        base = can_netlist()
        source = base.model_copy(
            update={
                "nets": {
                    "CAN_DIAGNOSTIC": ("U1.3",),
                    "CAN_ENABLE": ("U1.4",),
                },
                "pin_functions": {
                    **base.pin_functions,
                    "U1.3": "TXD",
                    "U1.4": "STATUS",
                },
            }
        )
        original = evaluate("synthetic-can", coach(source), DesignLintPolicy())
        rule_id = "bus.can_unconnected_line"
        original_findings = {
            item.subject: (item.fingerprint, item.evidence)
            for item in original.findings
            if item.rule_id == rule_id
        }
        reordered_source = source.model_copy(
            update={
                "components": dict(reversed(tuple(source.components.items()))),
                "nets": dict(reversed(tuple(source.nets.items()))),
                "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
                "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            }
        )
        reordered = evaluate("synthetic-can", coach(reordered_source), DesignLintPolicy())
        reordered_findings = {
            item.subject: (item.fingerprint, item.evidence)
            for item in reordered.findings
            if item.rule_id == rule_id
        }
        self.assertEqual(len(original_findings), 2)
        self.assertEqual(reordered_findings, original_findings)

        for subject, original_finding in original_findings.items():
            pin = subject.split(":", maxsplit=1)[0]
            assigned = source.model_copy(
                update={
                    "nets": {
                        **source.nets,
                        f"ASSIGNED_{pin.replace('.', '_')}": (pin,),
                    }
                }
            )
            assigned_report = evaluate("synthetic-can", coach(assigned), DesignLintPolicy())
            remaining_findings = {
                item.subject: (item.fingerprint, item.evidence)
                for item in assigned_report.findings
                if item.rule_id == rule_id
            }
            expected = dict(original_findings)
            del expected[subject]
            self.assertEqual(remaining_findings, expected, original_finding)

    def test_unconnected_reset_enable_and_boot_inputs_are_review_candidates(self) -> None:
        report = evaluate(
            "synthetic-control-inputs", coach(control_input_pins()), DesignLintPolicy()
        )
        findings = [
            item for item in report.findings if item.rule_id == "control.unconnected_control_input"
        ]
        self.assertEqual(report.status, "REVIEW")
        self.assertEqual(
            {item.subject for item in findings},
            {
                "U1.1: ~{RESET}",
                "U1.2: EN",
                "U1.3: BOOT0",
                "U1.8: RST#",
                "U1.9: BOOT_A",
                "U1.10: IOEXP_RST_N",
                "U1.11: JTAG_EN",
                "U1.12: nRPIBOOT",
                "U1.13: PERST",
            },
        )
        self.assertEqual(
            {item.evidence["family"] for item in findings},
            {("reset",), ("enable",), ("boot/strap",)},
        )
        self.assertTrue(all("no net assignment" in item.message for item in findings))

        connected = evaluate(
            "synthetic-control-inputs",
            coach(control_input_pins(connected=True)),
            DesignLintPolicy(),
        )
        self.assertEqual(connected.status, "PASS")
        self.assertFalse(connected.findings)

        dnp = evaluate(
            "synthetic-control-inputs",
            coach(control_input_pins(dnp=True)),
            DesignLintPolicy(),
        )
        self.assertEqual(dnp.status, "PASS")
        self.assertFalse(dnp.findings)

        blocked = evaluate(
            "synthetic-control-inputs",
            coach(control_input_pins()),
            DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id="control.unconnected_control_input",
                        mode="block",
                        reason="This project requires every reset and boot pin to be reviewed",
                    ),
                )
            ),
        )
        self.assertEqual(blocked.status, "FAIL")

        ignored = evaluate(
            "synthetic-control-inputs",
            coach(control_input_pins()),
            DesignLintPolicy(
                ignores=tuple(
                    DesignLintIgnore(
                        rule_id=item.rule_id,
                        fingerprint=item.fingerprint,
                        reason="Synthetic control intentionally leaves this optional input unused",
                    )
                    for item in findings
                )
            ),
        )
        self.assertEqual(ignored.status, "PASS")
        self.assertTrue(all(item.disposition == "IGNORED" for item in ignored.findings))

    def test_connected_control_input_without_visible_bias_is_review_only_and_configurable(
        self,
    ) -> None:
        source = control_input_pins(connected=True, visible_bias=False)
        report = evaluate("synthetic-control-bias", coach(source), DesignLintPolicy())
        rule_id = "control.connected_control_input_without_visible_bias"
        findings = [item for item in report.findings if item.rule_id == rule_id]

        self.assertEqual(report.status, "REVIEW")
        self.assertEqual(
            {item.evidence["net"][0] for item in findings},
            {"RESET_LINE", "ENABLE_LINE", "ENABLE_A", "BOOT_STRAP"},
        )
        self.assertTrue(all(item.mode == "review" for item in findings))
        self.assertTrue(all(item.evidence["output_capable_peers"] == () for item in findings))
        self.assertTrue(
            all(
                "does not establish that a resistor is required" in item.message
                for item in findings
            )
        )

        blocked = evaluate(
            "synthetic-control-bias",
            coach(source),
            DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id=rule_id,
                        mode="block",
                        reason="This project requires explicit control-input bias review",
                    ),
                )
            ),
        )
        self.assertEqual(blocked.status, "FAIL")

        disabled = evaluate(
            "synthetic-control-bias",
            coach(source),
            DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id=rule_id,
                        mode="off",
                        reason="Reviewed internal bias covers these controls",
                    ),
                )
            ),
        )
        self.assertEqual(disabled.status, "PASS")
        self.assertTrue(all(item.disposition == "RULE_OFF" for item in disabled.findings))

        ignored = evaluate(
            "synthetic-control-bias",
            coach(source),
            DesignLintPolicy(
                ignores=tuple(
                    DesignLintIgnore(
                        rule_id=item.rule_id,
                        fingerprint=item.fingerprint,
                        reason="Reviewed off-board bias for this control net",
                    )
                    for item in findings
                )
            ),
        )
        self.assertEqual(ignored.status, "PASS")
        self.assertTrue(all(item.disposition == "IGNORED" for item in ignored.findings))

    def test_connected_control_bias_prompt_checks_assignments_and_valid_controls(self) -> None:
        rule_id = "control.connected_control_input_without_visible_bias"
        locally_biased = evaluate(
            "synthetic-control-bias",
            coach(control_input_pins(connected=True)),
            DesignLintPolicy(),
        )
        self.assertNotIn(rule_id, {item.rule_id for item in locally_biased.findings})

        pull_down = with_control_resistor(
            control_input_pins(connected=True, visible_bias=False),
            signal_net="RESET_LINE",
            rail_net="GND",
        )
        pull_down_report = evaluate("synthetic-control-bias", coach(pull_down), DesignLintPolicy())
        self.assertNotIn(
            "RESET_LINE",
            {
                item.evidence["net"][0]
                for item in pull_down_report.findings
                if item.rule_id == rule_id
            },
        )

        dnp_bias = with_control_resistor(
            control_input_pins(connected=True, visible_bias=False),
            signal_net="RESET_LINE",
            rail_net="+3V3",
        ).model_copy(update={"dnp_components": ("R1",)})
        dnp_bias_report = evaluate("synthetic-control-bias", coach(dnp_bias), DesignLintPolicy())
        self.assertIn(
            "RESET_LINE",
            {
                item.evidence["net"][0]
                for item in dnp_bias_report.findings
                if item.rule_id == rule_id
            },
        )

        unrecognized_rail = with_control_resistor(
            control_input_pins(connected=True, visible_bias=False),
            signal_net="RESET_LINE",
            rail_net="CUSTOM_BIAS",
        )
        unrecognized_rail_report = evaluate(
            "synthetic-control-bias", coach(unrecognized_rail), DesignLintPolicy()
        )
        self.assertIn(
            "RESET_LINE",
            {
                item.evidence["net"][0]
                for item in unrecognized_rail_report.findings
                if item.rule_id == rule_id
            },
        )

        dnp = evaluate(
            "synthetic-control-bias",
            coach(control_input_pins(connected=True, dnp=True, visible_bias=False)),
            DesignLintPolicy(),
        )
        self.assertNotIn(rule_id, {item.rule_id for item in dnp.findings})

        source = control_input_pins(connected=True, visible_bias=False)
        with_driver = source.model_copy(
            update={
                "components": {
                    **source.components,
                    "U2": ComponentContract(value="Synthetic supervisor", footprint=""),
                },
                "component_symbols": {
                    **source.component_symbols,
                    "U2": "Synthetic:Supervisor",
                },
                "component_pin_numbers": {
                    **source.component_pin_numbers,
                    "U2": ("1",),
                },
                "pin_functions": {**source.pin_functions, "U2.1": "RESET_OUT"},
                "pin_electrical_types": {**source.pin_electrical_types, "U2.1": "open_collector"},
                "nets": {
                    **source.nets,
                    "RESET_LINE": (*source.nets["RESET_LINE"], "U2.1"),
                },
            }
        )
        driver_report = evaluate("synthetic-control-bias", coach(with_driver), DesignLintPolicy())
        reset_finding = next(
            item
            for item in driver_report.findings
            if item.rule_id == rule_id and item.evidence["net"] == ("RESET_LINE",)
        )
        self.assertEqual(
            reset_finding.evidence["output_capable_peers"], ("U2.1: RESET_OUT (open_collector)",)
        )

    def test_connected_control_bias_prompt_uses_exact_source_bound_contract_decisions(self) -> None:
        rule_id = "control.connected_control_input_without_visible_bias"
        source = control_netlist(fault="missing-resistor")
        for bias_mode in ("internal", "external", "not_required"):
            with self.subTest(bias_mode=bias_mode):
                coverage = control_input_bias_heuristic_coverage(
                    source,
                    netlist_sha256="a" * 64,
                    source_path="projects/synthetic/electrical.json",
                    source_sha256="b" * 64,
                    state="required",
                    spec=control_requirement(bias_mode=bias_mode),
                )
                self.assertEqual(coverage.status, "COMPLETE")
                self.assertEqual(len(coverage.entries), 1)
                self.assertEqual(coverage.entries[0].status, "COVERED")
                report = evaluate(
                    "synthetic-control-bias",
                    coach(source),
                    DesignLintPolicy(),
                    control_input_bias_coverage=coverage,
                )
                self.assertNotIn(rule_id, {item.rule_id for item in report.findings})
                self.assertEqual(report.control_input_bias_coverage, coverage)
                rendered = text_report(report)
                self.assertIn("Control-input bias heuristic coverage: COMPLETE", rendered)
                failed_summary = report.model_copy(update={"native_status": "FAIL"})
                self.assertIn(
                    "Validation summary status: FAIL",
                    text_report(failed_summary),
                )
                self.assertIn(f"bias={bias_mode}", rendered)
                self.assertIn("projects/synthetic/electrical.json", rendered)

        local_missing = control_input_bias_heuristic_coverage(
            source,
            netlist_sha256="a" * 64,
            source_path="projects/synthetic/electrical.json",
            source_sha256="b" * 64,
            state="required",
            spec=control_requirement(bias_mode="local"),
        )
        self.assertEqual(local_missing.status, "OPEN")
        self.assertTrue(any("bias:" in issue for issue in local_missing.entries[0].issues))
        local_report = evaluate(
            "synthetic-control-bias",
            coach(source),
            DesignLintPolicy(),
            control_input_bias_coverage=local_missing,
        )
        self.assertIn(rule_id, {item.rule_id for item in local_report.findings})

        no_bias_with_extra_output = control_netlist(fault="missing-resistor")
        no_bias_with_extra_output = no_bias_with_extra_output.model_copy(
            update={
                "components": {
                    **no_bias_with_extra_output.components,
                    "U4": ComponentContract(
                        value="Synthetic unreviewed driver", footprint="Package_SO:SOIC-8"
                    ),
                },
                "component_symbols": {
                    **no_bias_with_extra_output.component_symbols,
                    "U4": "Synthetic:PushPullOutput",
                },
                "component_pin_numbers": {
                    **no_bias_with_extra_output.component_pin_numbers,
                    "U4": ("1",),
                },
                "pin_functions": {
                    **no_bias_with_extra_output.pin_functions,
                    "U4.1": "RESET_N",
                },
                "pin_electrical_types": {
                    **no_bias_with_extra_output.pin_electrical_types,
                    "U4.1": "output",
                },
                "nets": {
                    **no_bias_with_extra_output.nets,
                    "RESET_N": (*no_bias_with_extra_output.nets["RESET_N"], "U4.1"),
                },
            }
        )
        undisclosed_driver = control_input_bias_heuristic_coverage(
            no_bias_with_extra_output,
            netlist_sha256="a" * 64,
            source_path="projects/synthetic/electrical.json",
            source_sha256="b" * 64,
            state="required",
            spec=control_requirement(bias_mode="external"),
        )
        self.assertEqual(undisclosed_driver.status, "OPEN")
        self.assertTrue(any("drivers:" in issue for issue in undisclosed_driver.entries[0].issues))
        driver_report = evaluate(
            "synthetic-control-bias",
            coach(no_bias_with_extra_output),
            DesignLintPolicy(),
            control_input_bias_coverage=undisclosed_driver,
        )
        self.assertIn(rule_id, {item.rule_id for item in driver_report.findings})

        partial_source = source.model_copy(
            update={
                "nets": {
                    **source.nets,
                    "RESET_N": (*source.nets["RESET_N"], "U1.8"),
                },
                "pin_functions": {
                    **source.pin_functions,
                    "U1.8": "RST#",
                },
                "pin_electrical_types": {
                    **source.pin_electrical_types,
                    "U1.8": "input",
                },
                "component_pin_numbers": {
                    **source.component_pin_numbers,
                    "U1": (*source.component_pin_numbers["U1"], "8"),
                },
            }
        )
        partial_coverage = control_input_bias_heuristic_coverage(
            partial_source,
            netlist_sha256="a" * 64,
            source_path="projects/synthetic/electrical.json",
            source_sha256="b" * 64,
            state="required",
            spec=control_requirement(bias_mode="external"),
        )
        self.assertEqual(partial_coverage.status, "OPEN")
        self.assertIn("U1.8", partial_coverage.entries[0].control_pins)
        self.assertIsNone(partial_coverage.entries[0].signal_id)
        partial_report = evaluate(
            "synthetic-control-bias",
            coach(partial_source),
            DesignLintPolicy(),
            control_input_bias_coverage=partial_coverage,
        )
        self.assertIn(rule_id, {item.rule_id for item in partial_report.findings})

    def test_connected_control_bias_finding_is_order_stable_and_direct_resistor_clears_it(
        self,
    ) -> None:
        source = control_input_pins(connected=True, visible_bias=False)
        original = evaluate("synthetic-control-bias", coach(source), DesignLintPolicy())
        rule_id = "control.connected_control_input_without_visible_bias"
        original_findings = {
            item.evidence["net"][0]: (item.fingerprint, item.evidence)
            for item in original.findings
            if item.rule_id == rule_id
        }
        reordered_source = source.model_copy(
            update={
                "components": dict(reversed(tuple(source.components.items()))),
                "nets": dict(reversed(tuple(source.nets.items()))),
                "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
                "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
                "pin_electrical_types": dict(reversed(tuple(source.pin_electrical_types.items()))),
                "component_pin_numbers": dict(
                    reversed(tuple(source.component_pin_numbers.items()))
                ),
            }
        )
        reordered = evaluate("synthetic-control-bias", coach(reordered_source), DesignLintPolicy())
        reordered_findings = {
            item.evidence["net"][0]: (item.fingerprint, item.evidence)
            for item in reordered.findings
            if item.rule_id == rule_id
        }
        self.assertEqual(reordered_findings, original_findings)

        repaired = with_control_resistor(
            source,
            signal_net="RESET_LINE",
            rail_net="+3V3",
        )
        repaired_report = evaluate("synthetic-control-bias", coach(repaired), DesignLintPolicy())
        repaired_findings = {
            item.evidence["net"][0]: (item.fingerprint, item.evidence)
            for item in repaired_report.findings
            if item.rule_id == rule_id
        }
        expected = dict(original_findings)
        del expected["RESET_LINE"]
        self.assertEqual(repaired_findings, expected)

    def test_control_input_candidates_are_order_stable_and_each_assignment_clears_one(self) -> None:
        base = control_input_pins()
        source = base.model_copy(
            update={
                "nets": {
                    "GPIO_CONTROL": ("U1.4",),
                    "RESET_OUTPUT": ("U1.7",),
                }
            }
        )
        original = evaluate("synthetic-control-inputs", coach(source), DesignLintPolicy())
        reordered_source = source.model_copy(
            update={
                "components": dict(reversed(tuple(source.components.items()))),
                "nets": dict(reversed(tuple(source.nets.items()))),
                "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
                "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
                "pin_electrical_types": dict(reversed(tuple(source.pin_electrical_types.items()))),
                "component_pin_numbers": dict(
                    reversed(tuple(source.component_pin_numbers.items()))
                ),
                "unconnected_nets": dict(reversed(tuple(source.unconnected_nets.items()))),
            }
        )
        reordered = evaluate(
            "synthetic-control-inputs", coach(reordered_source), DesignLintPolicy()
        )

        rule_id = "control.unconnected_control_input"
        original_findings = {
            item.subject: (item.fingerprint, item.evidence)
            for item in original.findings
            if item.rule_id == rule_id
        }
        reordered_findings = {
            item.subject: (item.fingerprint, item.evidence)
            for item in reordered.findings
            if item.rule_id == rule_id
        }
        self.assertEqual(len(original_findings), 9)
        self.assertEqual(reordered_findings, original_findings)

        for subject, finding in original_findings.items():
            pin = subject.split(":", maxsplit=1)[0]
            remaining_unconnected: dict[str, tuple[str, ...]] = {}
            found_unconnected_pin = False
            for net_name, pins in source.unconnected_nets.items():
                remaining = tuple(candidate for candidate in pins if candidate != pin)
                found_unconnected_pin |= len(remaining) != len(pins)
                if remaining:
                    remaining_unconnected[net_name] = remaining
            self.assertTrue(found_unconnected_pin, pin)
            assigned = source.model_copy(
                update={
                    "nets": {
                        **source.nets,
                        f"ASSIGNED_{pin.replace('.', '_')}": (pin,),
                    },
                    "unconnected_nets": remaining_unconnected,
                }
            )
            assigned_report = evaluate(
                "synthetic-control-inputs", coach(assigned), DesignLintPolicy()
            )
            remaining_findings = {
                item.subject: (item.fingerprint, item.evidence)
                for item in assigned_report.findings
                if item.rule_id == rule_id
            }
            expected = dict(original_findings)
            del expected[subject]
            self.assertEqual(remaining_findings, expected, finding)

    def test_multiconductor_connector_without_connected_return_needs_review(self) -> None:
        report = evaluate("synthetic-ports", coach(multiconductor_connector()), DesignLintPolicy())
        self.assertEqual(report.status, "REVIEW")
        self.assertEqual(len(report.findings), 1)
        finding = report.findings[0]
        self.assertEqual(finding.rule_id, "connector.unconnected_return_pin")
        self.assertEqual(finding.subject, "J1.4: GND")
        self.assertEqual(finding.evidence, {"J1.4": ()})
        self.assertIn("no net assignment", finding.message)

        unnamed = evaluate(
            "synthetic-ports",
            coach(multiconductor_connector(return_named=False)),
            DesignLintPolicy(),
        )
        self.assertEqual(len(unnamed.findings), 1)
        self.assertEqual(unnamed.findings[0].rule_id, "connector.no_connected_return")
        self.assertIn("3 connected non-shield pins", unnamed.findings[0].message)

    def test_connector_without_return_is_order_stable_and_connected_return_clears_candidate(
        self,
    ) -> None:
        rule_id = "connector.no_connected_return"
        source = multiconductor_connector(return_named=False)

        def lint(netlist: NetlistContract) -> tuple[str, DesignLintReport]:
            source_hash = hashlib.sha256(netlist.model_dump_json().encode("utf-8")).hexdigest()
            report = evaluate(
                "synthetic-ports",
                coach(netlist).model_copy(update={"netlist_sha256": source_hash}),
                DesignLintPolicy(),
            )
            return source_hash, report

        source_hash, original = lint(source)
        original_findings = {
            item.subject: (item.fingerprint, item.evidence)
            for item in original.findings
            if item.rule_id == rule_id
        }
        self.assertEqual(len(original_findings), 1)

        reordered_source = source.model_copy(
            update={
                "nets": dict(reversed(tuple(source.nets.items()))),
                "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
                "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            }
        )
        reordered_hash, reordered = lint(reordered_source)
        self.assertNotEqual(source_hash, reordered_hash)
        reordered_findings = {
            item.subject: (item.fingerprint, item.evidence)
            for item in reordered.findings
            if item.rule_id == rule_id
        }
        self.assertEqual(reordered_findings, original_findings)

        repaired_hash, repaired = lint(multiconductor_connector(return_connected=True))
        self.assertNotEqual(source_hash, repaired_hash)
        self.assertNotIn(rule_id, {item.rule_id for item in repaired.findings})

    def test_return_named_net_is_context_not_proof_of_connector_pin_role(self) -> None:
        observed_without_roles = multiconductor_connector(return_named=False)
        nets = dict(observed_without_roles.nets)
        nets["0V IFACE 1"] = ("J1.4",)
        observed_with_return_label = observed_without_roles.model_copy(update={"nets": nets})

        report = evaluate(
            "synthetic-ports",
            coach(observed_with_return_label),
            DesignLintPolicy(),
        )
        findings = [
            item for item in report.findings if item.rule_id == "connector.no_connected_return"
        ]
        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertIn(
            "no native symbol function or a source-matched project interface role identifies",
            finding.message,
        )
        self.assertIn("net labels look return-related", finding.message)
        self.assertEqual(finding.subject, "J1: return pin role not identified")
        self.assertEqual(
            finding.evidence["return_named_net_candidates"],
            ("J1.4: 0V IFACE 1",),
        )

    def test_return_coverage_excludes_shields_and_small_connectors(self) -> None:
        connected = evaluate(
            "synthetic-ports",
            coach(multiconductor_connector(return_connected=True)),
            DesignLintPolicy(),
        )
        self.assertEqual(connected.status, "PASS")

        shield_connected = evaluate(
            "synthetic-ports",
            coach(multiconductor_connector(with_shield=True, return_named=False)),
            DesignLintPolicy(),
        )
        self.assertTrue(
            any(
                item.rule_id == "connector.no_connected_return"
                for item in shield_connected.findings
            )
        )

        two_pins = NetlistContract(
            components={},
            nets={"DATA_A": ("J1.1",), "DATA_B": ("J1.2",)},
            component_symbols={"J1": "Synthetic:DifferentialPort"},
            pin_functions={"J1.1": "D+", "J1.2": "D-", "J1.3": "GND"},
        )
        small = evaluate("synthetic-ports", coach(two_pins), DesignLintPolicy())
        self.assertFalse(
            any(item.rule_id == "connector.no_connected_return" for item in small.findings)
        )

    def test_common_supply_aliases_pass_and_distinct_rails_stay_separate(self) -> None:
        common = evaluate(
            "synthetic-ports", coach(cross_symbol_power(common=True)), DesignLintPolicy()
        )
        self.assertEqual(common.status, "PASS")
        self.assertFalse(common.findings)

        voltage_alias = evaluate(
            "synthetic-ports",
            coach(cross_symbol_power(common=True, usb_function="+3.3V", serial_function="3V3")),
            DesignLintPolicy(),
        )
        self.assertEqual(voltage_alias.status, "PASS")
        self.assertFalse(voltage_alias.findings)

        distinct = evaluate(
            "synthetic-ports",
            coach(cross_symbol_power(usb_function="VBUS", serial_function="VCC")),
            DesignLintPolicy(),
        )
        self.assertEqual(distinct.status, "PASS")
        self.assertFalse(distinct.findings)

        different_voltage = evaluate(
            "synthetic-ports",
            coach(cross_symbol_power(usb_function="3.3V", serial_function="33V")),
            DesignLintPolicy(),
        )
        self.assertEqual(different_voltage.status, "PASS")
        self.assertFalse(different_voltage.findings)

        opposite = evaluate(
            "synthetic-ports",
            coach(cross_symbol_power(usb_function="+5V", serial_function="-5V")),
            DesignLintPolicy(),
        )
        self.assertEqual(opposite.status, "PASS")
        self.assertFalse(opposite.findings)

    def test_return_pin_disagreement_within_one_connector_needs_review(self) -> None:
        observed_connector = NetlistContract(
            components={},
            nets={"SIGNAL_RETURN": ("J1.7",), "LOGIC_RETURN": ("J1.9",)},
            component_symbols={"J1": "Synthetic:DB9"},
            pin_functions={"J1.7": "GND", "J1.9": "GND"},
        )
        report = evaluate("synthetic-single-port", coach(observed_connector), DesignLintPolicy())
        self.assertEqual(report.status, "REVIEW")
        self.assertEqual(len(report.findings), 1)
        self.assertEqual(report.findings[0].subject, "Synthetic:DB9: ground/return")
        self.assertEqual(
            report.findings[0].evidence,
            {"J1.7": ("SIGNAL_RETURN",), "J1.9": ("LOGIC_RETURN",)},
        )

    def test_unindexed_return_labels_without_pin_roles_need_review(self) -> None:
        observed_returns = NetlistContract(
            components={},
            nets={
                "USB_GND": ("J1.7",),
                "SERIAL_RETURN": ("J2.7",),
            },
            component_symbols={"J1": "Synthetic:DB9-A", "J2": "Synthetic:DB9-B"},
            pin_functions={"J1.7": "7", "J2.7": "7"},
        )
        report = evaluate("synthetic-return-labels", coach(observed_returns), DesignLintPolicy())
        self.assertEqual(report.status, "REVIEW")
        finding = next(
            item
            for item in report.findings
            if item.rule_id == "net.return_labels_without_pin_roles"
        )
        self.assertEqual(
            finding.evidence,
            {"SERIAL_RETURN": ("J2.7",), "USB_GND": ("J1.7",)},
        )
        self.assertIn("labels alone do not establish", finding.message)

        blocked = evaluate(
            "synthetic-return-labels",
            coach(observed_returns),
            DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id="net.return_labels_without_pin_roles",
                        mode="block",
                        reason="Unnamed return relationships need explicit review",
                    ),
                )
            ),
        )
        self.assertEqual(blocked.status, "FAIL")
        ignored_by_rule = evaluate(
            "synthetic-return-labels",
            coach(observed_returns),
            DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id="net.return_labels_without_pin_roles",
                        mode="off",
                        reason="A separate contract governs this isolated interface",
                    ),
                )
            ),
        )
        self.assertEqual(ignored_by_rule.status, "PASS")
        self.assertEqual(ignored_by_rule.findings[0].disposition, "RULE_OFF")

        ignore_policy = DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id="net.return_labels_without_pin_roles",
                    fingerprint=finding.fingerprint,
                    reason="Approved synthetic isolated returns",
                ),
            ),
        )
        ignored = evaluate(
            "synthetic-return-labels",
            coach(observed_returns),
            ignore_policy,
        )
        self.assertEqual(ignored.status, "PASS")
        changed = observed_returns.model_copy(
            update={
                "nets": {
                    **observed_returns.nets,
                    "SERIAL_RTN": observed_returns.nets["SERIAL_RETURN"],
                    "SERIAL_RETURN": (),
                }
            }
        )
        changed_report = evaluate("synthetic-return-labels", coach(changed), ignore_policy)
        changed_finding = next(
            item
            for item in changed_report.findings
            if item.rule_id == "net.return_labels_without_pin_roles"
        )
        self.assertEqual(changed_finding.disposition, "OPEN")
        self.assertEqual(changed_report.stale_ignores, ignore_policy.ignores)

        named_pin_roles = NetlistContract(
            components={},
            nets={"USB_RETURN": ("J1.7",), "SERIAL_GND": ("J2.7",)},
            component_symbols={"J1": "Synthetic:USB", "J2": "Synthetic:Serial"},
            pin_functions={"J1.7": "GND", "J2.7": "RTN"},
        )
        named_report = evaluate(
            "synthetic-return-labels", coach(named_pin_roles), DesignLintPolicy()
        )
        self.assertNotIn(
            "net.return_labels_without_pin_roles",
            {item.rule_id for item in named_report.findings},
        )

        numbered = NetlistContract(
            components={},
            nets={"0V PWM 1": ("J1.7",), "0V PWM 2": ("J2.7",)},
            component_symbols={"J1": "Synthetic:DB9-A", "J2": "Synthetic:DB9-B"},
            pin_functions={"J1.7": "7", "J2.7": "7"},
        )
        numbered_report = evaluate(
            "synthetic-numbered-returns", coach(numbered), DesignLintPolicy()
        )
        numbered_rules = {item.rule_id for item in numbered_report.findings}
        self.assertIn("net.numbered_returns", numbered_rules)
        self.assertNotIn("net.return_labels_without_pin_roles", numbered_rules)

        mixed = numbered.model_copy(
            update={
                "nets": {
                    **numbered.nets,
                    "USB_GND": ("J3.7",),
                    "SERIAL_RETURN": ("J4.7",),
                },
                "component_symbols": {
                    **numbered.component_symbols,
                    "J3": "Synthetic:USB",
                    "J4": "Synthetic:Serial",
                },
                "pin_functions": {
                    **numbered.pin_functions,
                    "J3.7": "7",
                    "J4.7": "7",
                },
            }
        )
        mixed_report = evaluate("synthetic-mixed-return-patterns", coach(mixed), DesignLintPolicy())
        mixed_rules = {item.rule_id for item in mixed_report.findings}
        self.assertIn("net.numbered_returns", mixed_rules)
        self.assertIn("net.return_labels_without_pin_roles", mixed_rules)
        mixed_unindexed_finding = next(
            item
            for item in mixed_report.findings
            if item.rule_id == "net.return_labels_without_pin_roles"
        )
        self.assertEqual(
            mixed_unindexed_finding.evidence,
            {"SERIAL_RETURN": ("J4.7",), "USB_GND": ("J3.7",)},
        )

        single = NetlistContract(
            components={},
            nets={"USB_GND": ("J1.7",), "DATA": ("J2.1",)},
            component_symbols={"J1": "Synthetic:DB9-A", "J2": "Synthetic:DB9-B"},
            pin_functions={"J1.7": "7", "J2.1": "1"},
        )
        single_report = evaluate("synthetic-single-return", coach(single), DesignLintPolicy())
        self.assertNotIn(
            "net.return_labels_without_pin_roles",
            {item.rule_id for item in single_report.findings},
        )

    def test_unindexed_return_label_order_is_stable_and_single_label_clears_the_hint(self) -> None:
        source = NetlistContract(
            components={},
            nets={"USB_GND": ("J1.7",), "SERIAL_RETURN": ("J2.7",)},
            component_symbols={"J1": "Synthetic:DB9-A", "J2": "Synthetic:DB9-B"},
            pin_functions={"J1.7": "7", "J2.7": "7"},
        )
        reordered = source.model_copy(
            update={
                "nets": dict(reversed(tuple(source.nets.items()))),
                "component_symbols": dict(reversed(tuple(source.component_symbols.items()))),
                "pin_functions": dict(reversed(tuple(source.pin_functions.items()))),
            }
        )
        original_report = evaluate("synthetic-return-labels", coach(source), DesignLintPolicy())
        reordered_report = evaluate("synthetic-return-labels", coach(reordered), DesignLintPolicy())
        original_finding = next(
            item
            for item in original_report.findings
            if item.rule_id == "net.return_labels_without_pin_roles"
        )
        reordered_finding = next(
            item
            for item in reordered_report.findings
            if item.rule_id == "net.return_labels_without_pin_roles"
        )
        self.assertEqual(
            (reordered_finding.fingerprint, reordered_finding.evidence),
            (original_finding.fingerprint, original_finding.evidence),
        )

        one_label = source.model_copy(
            update={
                "nets": {
                    "USB_GND": source.nets["USB_GND"],
                    "SERIAL_SIGNAL": source.nets["SERIAL_RETURN"],
                }
            }
        )
        one_label_report = evaluate(
            "synthetic-one-return-label", coach(one_label), DesignLintPolicy()
        )
        self.assertNotIn(
            "net.return_labels_without_pin_roles",
            {item.rule_id for item in one_label_report.findings},
        )

    def test_four_db9_return_domains_surface_review_and_keep_common_control(self) -> None:
        isolated = four_db9_return_domains()
        report = evaluate("synthetic-four-db9", coach(isolated), DesignLintPolicy())
        self.assertEqual(report.status, "REVIEW")

        repeated_pin_findings = [
            item for item in report.findings if item.rule_id == "connector.repeated_pin_function"
        ]
        self.assertEqual(len(repeated_pin_findings), 2)
        self.assertEqual(
            {pin for item in repeated_pin_findings for pin in item.evidence},
            {f"J{reference}.{pin}" for reference in range(1, 5) for pin in (7, 9)},
        )

        return_finding = next(
            item for item in report.findings if item.rule_id == "net.numbered_returns"
        )
        self.assertEqual(
            return_finding.evidence,
            {
                f"0V PWM {reference}": (f"J{reference}.7", f"J{reference}.9")
                for reference in range(1, 5)
            },
        )
        self.assertIn("intentionally isolated", return_finding.message)

        common = evaluate(
            "synthetic-four-db9-common",
            coach(four_db9_return_domains(common=True)),
            DesignLintPolicy(),
        )
        self.assertEqual(common.status, "PASS")
        self.assertFalse(common.findings)

        intentionally_isolated = evaluate(
            "synthetic-four-db9-isolated",
            coach(isolated),
            DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id="connector.repeated_pin_function",
                        mode="off",
                        reason="Synthetic isolation control reviewed as intentional",
                    ),
                    DesignLintRuleOverride(
                        rule_id="net.numbered_returns",
                        mode="off",
                        reason="Synthetic isolation control reviewed as intentional",
                    ),
                ),
            ),
        )
        self.assertEqual(intentionally_isolated.status, "PASS")
        self.assertTrue(
            all(item.disposition == "RULE_OFF" for item in intentionally_isolated.findings)
        )

    def test_repeated_db9_pin_review_survives_neutral_net_renaming(self) -> None:
        isolated = four_db9_return_domains()
        renamed = isolated.model_copy(
            update={
                "nets": {
                    f"NET_{index}": pins
                    for index, pins in enumerate(isolated.nets.values(), start=1)
                }
            }
        )

        report = evaluate("synthetic-four-db9-neutral-nets", coach(renamed), DesignLintPolicy())
        repeated_pin_findings = [
            item for item in report.findings if item.rule_id == "connector.repeated_pin_function"
        ]
        self.assertEqual(report.status, "REVIEW")
        self.assertEqual(len(repeated_pin_findings), 2)
        self.assertEqual(
            {pin for item in repeated_pin_findings for pin in item.evidence},
            {f"J{reference}.{pin}" for reference in range(1, 5) for pin in (7, 9)},
        )
        self.assertNotIn("net.numbered_returns", {item.rule_id for item in report.findings})
        self.assertNotIn(
            "net.return_labels_without_pin_roles",
            {item.rule_id for item in report.findings},
        )

        common = evaluate(
            "synthetic-four-db9-neutral-common",
            coach(four_db9_return_domains(common=True)),
            DesignLintPolicy(),
        )
        self.assertNotIn(
            "connector.repeated_pin_function",
            {item.rule_id for item in common.findings},
        )

    def test_numbered_return_order_is_stable_and_commoning_changes_the_hint(self) -> None:
        def source_bound_report(
            netlist: NetlistContract, policy: DesignLintPolicy | None = None
        ) -> DesignLintReport:
            netlist_sha256 = hashlib.sha256(netlist.model_dump_json().encode("utf-8")).hexdigest()
            return evaluate(
                "synthetic-four-db9",
                coach(netlist, netlist_sha256),
                policy or DesignLintPolicy(),
            )

        isolated = four_db9_return_domains()
        reordered = isolated.model_copy(
            update={
                "nets": dict(reversed(tuple(isolated.nets.items()))),
                "component_symbols": dict(reversed(tuple(isolated.component_symbols.items()))),
                "pin_functions": dict(reversed(tuple(isolated.pin_functions.items()))),
            }
        )
        original_report = source_bound_report(isolated)
        reordered_report = source_bound_report(reordered)
        original_finding = next(
            item for item in original_report.findings if item.rule_id == "net.numbered_returns"
        )
        reordered_finding = next(
            item for item in reordered_report.findings if item.rule_id == "net.numbered_returns"
        )
        self.assertEqual(
            (reordered_finding.fingerprint, reordered_finding.evidence),
            (original_finding.fingerprint, original_finding.evidence),
        )
        self.assertNotEqual(reordered_report.netlist_sha256, original_report.netlist_sha256)

        unrelated = isolated.model_copy(
            update={
                "components": {
                    **isolated.components,
                    "R9": ComponentContract(value="10k", footprint="Synthetic:R_0603"),
                },
                "nets": {
                    **isolated.nets,
                    "UNRELATED_A": ("R9.1",),
                    "UNRELATED_B": ("R9.2",),
                },
                "component_symbols": {**isolated.component_symbols, "R9": "Device:R"},
                "component_pin_numbers": {
                    **isolated.component_pin_numbers,
                    "R9": ("1", "2"),
                },
            }
        )
        unrelated_report = source_bound_report(unrelated)
        unrelated_finding = next(
            item for item in unrelated_report.findings if item.rule_id == "net.numbered_returns"
        )
        self.assertNotEqual(unrelated_report.netlist_sha256, original_report.netlist_sha256)
        self.assertEqual(
            (unrelated_finding.fingerprint, unrelated_finding.evidence),
            (original_finding.fingerprint, original_finding.evidence),
        )

        exact_ignore = DesignLintIgnore(
            rule_id="net.numbered_returns",
            fingerprint=original_finding.fingerprint,
            reason="Synthetic review accepts this explicit return-domain arrangement",
        )
        ignore_policy = DesignLintPolicy(ignores=(exact_ignore,))
        for candidate in (isolated, unrelated):
            ignored_report = source_bound_report(candidate, ignore_policy)
            ignored_numbered_return = next(
                item for item in ignored_report.findings if item.rule_id == "net.numbered_returns"
            )
            self.assertEqual(ignored_numbered_return.fingerprint, original_finding.fingerprint)
            self.assertEqual(ignored_numbered_return.disposition, "IGNORED")
            self.assertIn(
                "connector.repeated_pin_function",
                {item.rule_id for item in ignored_report.findings if item.disposition == "OPEN"},
            )

        repeated_pin_findings = sorted(
            (
                item
                for item in original_report.findings
                if item.rule_id == "connector.repeated_pin_function"
            ),
            key=lambda item: item.subject,
        )
        self.assertEqual(len(repeated_pin_findings), 2)
        ignored_peer = repeated_pin_findings[0]
        remaining_peer = repeated_pin_findings[1]
        peer_ignore_policy = DesignLintPolicy(
            ignores=(
                DesignLintIgnore(
                    rule_id=ignored_peer.rule_id,
                    fingerprint=ignored_peer.fingerprint,
                    reason="Synthetic review accepts this one connector return-group difference",
                ),
            )
        )
        for candidate in (isolated, unrelated):
            peer_ignore_report = source_bound_report(candidate, peer_ignore_policy)
            peer_findings = {
                item.fingerprint: item
                for item in peer_ignore_report.findings
                if item.rule_id == "connector.repeated_pin_function"
            }
            self.assertEqual(
                peer_findings[ignored_peer.fingerprint].disposition,
                "IGNORED",
            )
            self.assertEqual(
                peer_findings[remaining_peer.fingerprint].disposition,
                "OPEN",
            )
            self.assertEqual(
                next(
                    item
                    for item in peer_ignore_report.findings
                    if item.rule_id == "net.numbered_returns"
                ).disposition,
                "OPEN",
            )

        common_report = source_bound_report(four_db9_return_domains(common=True))
        self.assertEqual(common_report.status, "PASS")
        self.assertNotIn("net.numbered_returns", {item.rule_id for item in common_report.findings})

    def test_common_return_across_symbols_passes_and_shield_stays_separate(self) -> None:
        report = evaluate(
            "synthetic-ports", coach(cross_symbol_returns(common=True)), DesignLintPolicy()
        )
        self.assertEqual(report.status, "PASS")
        self.assertFalse(report.findings)

    def test_rule_overrides_block_or_turn_off_with_reason(self) -> None:
        blocked = evaluate(
            "synthetic-ports",
            coach(observed()),
            DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id="connector.repeated_pin_function",
                        mode="block",
                        reason="Port pin discrepancies require release review",
                    ),
                ),
            ),
        )
        self.assertEqual(blocked.status, "FAIL")
        off = evaluate(
            "synthetic-ports",
            coach(observed()),
            DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id="connector.repeated_pin_function",
                        mode="off",
                        reason="This synthetic board uses independent port rails",
                    ),
                    DesignLintRuleOverride(
                        rule_id="net.numbered_returns",
                        mode="off",
                        reason="This synthetic board uses isolated returns",
                    ),
                ),
            ),
        )
        self.assertEqual(off.status, "PASS")
        self.assertTrue(all(item.disposition == "RULE_OFF" for item in off.findings))
        self.assertTrue(all(item.reason for item in off.findings))

    def test_connector_return_coverage_rule_can_be_configured(self) -> None:
        observed_connector = multiconductor_connector(return_named=False)
        blocked = evaluate(
            "synthetic-ports",
            coach(observed_connector),
            DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id="connector.no_connected_return",
                        mode="block",
                        reason="Port pinout requires a signal return decision",
                    ),
                ),
            ),
        )
        self.assertEqual(blocked.status, "FAIL")

        ignored_by_rule = evaluate(
            "synthetic-ports",
            coach(observed_connector),
            DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id="connector.no_connected_return",
                        mode="off",
                        reason="All ports use a reviewed isolated interface",
                    ),
                ),
            ),
        )
        self.assertEqual(ignored_by_rule.status, "PASS")
        self.assertEqual(ignored_by_rule.findings[0].disposition, "RULE_OFF")

    def test_invalid_or_duplicate_decisions_fail_schema(self) -> None:
        with self.assertRaises(ValidationError):
            DesignLintPolicy(
                rules=(
                    DesignLintRuleOverride(
                        rule_id="net.numbered_returns", mode="off", reason="first"
                    ),
                    DesignLintRuleOverride(
                        rule_id="net.numbered_returns", mode="block", reason="second"
                    ),
                )
            )
        with self.assertRaises(ValidationError):
            DesignLintRuleOverride.model_validate(
                {"rule_id": "net.numbered_returns", "mode": "off", "reason": ""}
            )


if __name__ == "__main__":
    unittest.main()
