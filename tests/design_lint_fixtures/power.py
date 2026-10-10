"""Synthetic design-lint inputs for focused regression suites."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import (
    ComponentContract,
    ComponentRoleBinding,
    ComponentRoleMap,
    ComponentRolePin,
    ContractCoachReport,
    NetlistContract,
)


def generic_component_power_input_netlist(
    *,
    reference: str = "U1",
    connected: bool = False,
    function: str | None = "1",
    electrical_type: str = "power_in",
    dnp_references: tuple[str, ...] = (),
    symbol: str = "Synthetic:GenericPowerInputComponent",
) -> NetlistContract:
    pin = f"{reference}.1"
    pin_functions = {pin: function} if function is not None else {}
    pin_functions[f"{reference}.2"] = "2"
    return NetlistContract(
        components={
            reference: ComponentContract(value="Synthetic component", footprint="Synthetic:Part")
        },
        nets={"POWER_INPUT_TEST": (pin,)} if connected else {"SIGNAL": (f"{reference}.2",)},
        dnp_components=dnp_references,
        component_symbols={reference: symbol},
        component_pin_numbers={reference: ("1", "2")},
        pin_functions=pin_functions,
        pin_electrical_types={pin: electrical_type, f"{reference}.2": "passive"},
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


def custom_ic_decoupling_capacitor_fixture(
    *, capacitor_reference_net: str | None = "GND", dnp_capacitor: bool = False
) -> NetlistContract:
    """Use an opaque exact symbol identity requiring project role classification."""
    source = ic_power_decoupling_fixture(
        capacitor_net="+3V3",
        capacitor_reference_net=capacitor_reference_net,
        dnp_capacitor=dnp_capacitor,
    )
    return source.model_copy(
        update={
            "components": {
                **source.components,
                "C1": ComponentContract(
                    value="100n",
                    footprint="Synthetic:CAP123_0603",
                    part_id="synthetic-decoupling-capacitor",
                ),
            },
            "component_symbols": {**source.component_symbols, "C1": "Vendor:CAP123"},
            "component_pin_numbers": {**source.component_pin_numbers, "C1": ("1", "2")},
            "pin_functions": {
                **source.pin_functions,
                "C1.1": "1",
                "C1.2": "2",
            },
            "pin_electrical_types": {
                **source.pin_electrical_types,
                "C1.1": "passive",
                "C1.2": "passive",
            },
        }
    )


def custom_decoupling_capacitor_role_map(
    *, basis: str = "Synthetic fixture reviewed this exact two-pin capacitor identity"
) -> ComponentRoleMap:
    return ComponentRoleMap(
        entries=(
            ComponentRoleBinding(
                part_id="synthetic-decoupling-capacitor",
                symbol="Vendor:CAP123",
                footprint="Synthetic:CAP123_0603",
                role="capacitor",
                pins=(
                    ComponentRolePin(number="1", function="1", electrical_type="passive"),
                    ComponentRolePin(number="2", function="2", electrical_type="passive"),
                ),
                basis=basis,
            ),
        )
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
