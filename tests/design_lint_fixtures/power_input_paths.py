"""Synthetic builders for power-input source-path lint regressions."""

from __future__ import annotations

import hashlib

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    ContractCoachReport,
    DesignLintPolicy,
    NetlistContract,
    PowerPathElementRequirement,
    PowerPathEndpointRequirement,
    PowerPathMap,
    PowerPathRequirement,
)

RULE_ID = "power.input_without_supported_source_path"


def source_path_netlist(
    *,
    wrong_rail: bool = False,
    source_present: bool = True,
    capacitor_present: bool = True,
    capacitor_dnp: bool = False,
    series_symbol: str = "Device:FerriteBead",
    series_value: str = "Ferrite bead",
    series_dnp: bool = False,
    source_less_name_only: bool = False,
    capacitor_symbol: str = "Device:C",
) -> NetlistContract:
    supply_net = "+3V3" if source_less_name_only else "VLOAD"
    source_net = "VIN" if source_present else "LOCAL_SOURCE"
    components = {
        "FB1": ComponentContract(value=series_value, footprint="Synthetic:0603"),
        "U2": ComponentContract(value="Synthetic load", footprint="Synthetic:PowerLoad"),
    }
    symbols = {"FB1": series_symbol, "U2": "Synthetic:PowerLoad"}
    pin_numbers = {"FB1": ("1", "2"), "U2": ("1",)}
    dnp: list[str] = []
    nets: dict[str, tuple[str, ...]] = {
        source_net: ("FB1.1",),
        supply_net: ("FB1.2", "U2.1"),
        "GND": (),
    }
    if source_present:
        components["U1"] = ComponentContract(
            value="Synthetic source", footprint="Synthetic:PowerSource"
        )
        symbols["U1"] = "Synthetic:PowerSource"
        pin_numbers["U1"] = ("1",)
        nets[source_net] = ("U1.1", "FB1.1")
    if wrong_rail:
        nets[source_net] = ("U1.1",) if source_present else ()
        nets["GND"] = ("FB1.1",)
    if capacitor_present:
        components["C1"] = ComponentContract(value="100nF", footprint="Synthetic:0603")
        symbols["C1"] = capacitor_symbol
        pin_numbers["C1"] = ("1", "2")
        nets[supply_net] = (*nets[supply_net], "C1.1")
        nets["GND"] = (*nets["GND"], "C1.2")
        if capacitor_dnp:
            dnp.append("C1")
    if series_dnp:
        dnp.append("FB1")
    nets = {net: pins for net, pins in nets.items() if pins}
    return NetlistContract(
        components=components,
        nets=nets,
        dnp_components=tuple(dnp),
        component_symbols=symbols,
        pin_functions={"U1.1": "VOUT", "U2.1": "VIN"},
        pin_electrical_types={
            **({"U1.1": "power_out"} if source_present else {}),
            "U2.1": "power_in",
        },
        component_pin_numbers=pin_numbers,
    )


def series_diode_netlist(
    *,
    reverse: bool = False,
    dnp: bool = False,
    symbol: str = "Device:D",
    pin_functions: tuple[str, str] = ("K", "A"),
) -> NetlistContract:
    """Use the native Device:D pin functions: pin 1 K, pin 2 A."""
    source = source_path_netlist()
    if reverse:
        nets = dict(source.nets)
        nets["VIN"] = ("U1.1", "FB1.1")
        nets["VLOAD"] = ("FB1.2", "U2.1", "C1.1")
    else:
        nets = dict(source.nets)
        nets["VIN"] = ("U1.1", "FB1.2")
        nets["VLOAD"] = ("FB1.1", "U2.1", "C1.1")
    components = dict(source.components)
    components["D1"] = components.pop("FB1")
    component_symbols = dict(source.component_symbols)
    component_symbols.pop("FB1")
    component_symbols["D1"] = symbol
    component_pin_numbers = dict(source.component_pin_numbers)
    component_pin_numbers.pop("FB1")
    component_pin_numbers["D1"] = ("1", "2")
    nets = {net: tuple(pin.replace("FB1.", "D1.") for pin in pins) for net, pins in nets.items()}
    pin_function_map = dict(source.pin_functions)
    pin_function_map.pop("FB1.1", None)
    pin_function_map.pop("FB1.2", None)
    pin_function_map["D1.1"] = pin_functions[0]
    pin_function_map["D1.2"] = pin_functions[1]
    dnp_components = ("D1",) if dnp else ()
    return source.model_copy(
        update={
            "components": components,
            "nets": nets,
            "component_symbols": component_symbols,
            "component_pin_numbers": component_pin_numbers,
            "dnp_components": dnp_components,
            "pin_functions": pin_function_map,
        }
    )


def series_jumper_netlist(
    *,
    symbol: str = "Jumper:SolderJumper_2_Bridged",
    dnp: bool = False,
    pin_functions: tuple[str, str] = ("A", "B"),
    pin_numbers: tuple[str, str] = ("1", "2"),
) -> NetlistContract:
    """Use the native two-pole bridged solder-jumper identity and pin roles."""
    source = source_path_netlist()
    components = dict(source.components)
    components["JP1"] = components.pop("FB1")
    component_symbols = dict(source.component_symbols)
    component_symbols.pop("FB1")
    component_symbols["JP1"] = symbol
    component_pin_numbers = dict(source.component_pin_numbers)
    component_pin_numbers.pop("FB1")
    component_pin_numbers["JP1"] = pin_numbers
    nets = {
        net: tuple(pin.replace("FB1.", "JP1.") for pin in pins) for net, pins in source.nets.items()
    }
    pin_function_map = dict(source.pin_functions)
    pin_function_map.pop("FB1.1", None)
    pin_function_map.pop("FB1.2", None)
    pin_function_map["JP1.1"] = pin_functions[0]
    pin_function_map["JP1.2"] = pin_functions[1]
    return source.model_copy(
        update={
            "components": components,
            "component_symbols": component_symbols,
            "component_pin_numbers": component_pin_numbers,
            "dnp_components": ("JP1",) if dnp else (),
            "nets": nets,
            "pin_functions": pin_function_map,
        }
    )


def series_three_pin_jumper_netlist(
    *,
    symbol: str = "Jumper:SolderJumper_3_Bridged12",
    dnp: bool = False,
    pin_functions: tuple[str, ...] = ("A", "C", "B"),
    pin_numbers: tuple[str, ...] = ("1", "2", "3"),
    source_pin: str = "1",
    load_pin: str = "2",
    unassigned_pins: frozenset[str] = frozenset(),
) -> NetlistContract:
    """Use the native three-terminal jumper roles and selected bridge topology."""
    source = source_path_netlist()
    components = dict(source.components)
    components["JP1"] = components.pop("FB1")
    component_symbols = dict(source.component_symbols)
    component_symbols.pop("FB1")
    component_symbols["JP1"] = symbol
    component_pin_numbers = dict(source.component_pin_numbers)
    component_pin_numbers.pop("FB1")
    component_pin_numbers["JP1"] = pin_numbers

    jumper_nets = {number: f"JP_UNUSED_{number}" for number in pin_numbers}
    jumper_nets[source_pin] = "VIN"
    jumper_nets[load_pin] = "VLOAD"
    nets = {
        net: tuple(pin for pin in pins if not pin.startswith("FB1."))
        for net, pins in source.nets.items()
    }
    for number, net in jumper_nets.items():
        if number not in unassigned_pins:
            nets[net] = (*nets.get(net, ()), f"JP1.{number}")
    nets = {net: pins for net, pins in nets.items() if pins}

    pin_function_map = dict(source.pin_functions)
    pin_function_map.pop("FB1.1", None)
    pin_function_map.pop("FB1.2", None)
    pin_function_map.update(
        {f"JP1.{number}": function for number, function in zip(pin_numbers, pin_functions)}
    )
    return source.model_copy(
        update={
            "components": components,
            "component_symbols": component_symbols,
            "component_pin_numbers": component_pin_numbers,
            "dnp_components": ("JP1",) if dnp else (),
            "nets": nets,
            "pin_functions": pin_function_map,
        }
    )


def power_path_map() -> PowerPathMap:
    return PowerPathMap(
        basis="Synthetic source-to-load path requirement",
        paths=(
            PowerPathRequirement(
                id="source-to-load",
                basis="Synthetic load is powered through the fitted ferrite bead",
                start=PowerPathEndpointRequirement(
                    reference="U1",
                    pin="U1.1",
                    symbol="Synthetic:PowerSource",
                    footprint="Synthetic:PowerSource",
                    net="VIN",
                ),
                end=PowerPathEndpointRequirement(
                    reference="U2",
                    pin="U2.1",
                    symbol="Synthetic:PowerLoad",
                    footprint="Synthetic:PowerLoad",
                    net="VLOAD",
                ),
                elements=(
                    PowerPathElementRequirement(
                        reference="FB1",
                        symbol="Device:FerriteBead",
                        footprint="Synthetic:0603",
                        side_a_pin="FB1.1",
                        side_b_pin="FB1.2",
                        side_a_net="VIN",
                        side_b_net="VLOAD",
                    ),
                ),
            ),
        ),
    )


def external_source_netlist(
    *, power_out: bool, source_dnp: bool = False, isolated_return: bool = False
) -> NetlistContract:
    """Return a fitted connector-fed rail with an unrecognized custom net name."""
    source = source_path_netlist()
    components = dict(source.components)
    components.pop("U1")
    components["J1"] = ComponentContract(value="External supply", footprint="Synthetic:2Pin")
    symbols = dict(source.component_symbols)
    symbols.pop("U1")
    symbols["J1"] = "Connector_Generic:Conn_01x02"
    pin_numbers = dict(source.component_pin_numbers)
    pin_numbers.pop("U1")
    pin_numbers["J1"] = ("1", "2")
    pin_types = {"U2.1": "power_in"}
    if power_out:
        pin_types["J1.1"] = "power_out"
    nets = {
        "AUX_INPUT": ("J1.1", "FB1.1"),
        "VLOAD": ("FB1.2", "U2.1", "C1.1"),
        "GND": ("C1.2",),
    }
    pin_functions = {"J1.1": "PWR", "U2.1": "VIN"}
    if isolated_return:
        nets = {
            "AUX_INPUT": ("J1.1", "FB1.1"),
            "ISO_SUPPLY": ("FB1.2", "U2.1", "C1.1"),
            "ISO_RETURN": ("C1.2", "J1.2"),
        }
        pin_functions["J1.2"] = "RTN"
    dnp_components = source.dnp_components + (("J1",) if source_dnp else ())
    return source.model_copy(
        update={
            "components": components,
            "component_symbols": symbols,
            "component_pin_numbers": pin_numbers,
            "dnp_components": dnp_components,
            "nets": nets,
            "pin_functions": pin_functions,
            "pin_electrical_types": pin_types,
        }
    )


def regulator_source_netlist(*, regulator_dnp: bool) -> NetlistContract:
    """Return an explicit regulator input/output anchor with selectable DNP state."""
    source = source_path_netlist()
    components = dict(source.components)
    components.pop("FB1")
    components["U3"] = ComponentContract(value="Synthetic regulator", footprint="Synthetic:SOT23")
    symbols = dict(source.component_symbols)
    symbols.pop("FB1")
    symbols["U3"] = "Synthetic:Regulator"
    pin_numbers = dict(source.component_pin_numbers)
    pin_numbers.pop("FB1")
    pin_numbers["U3"] = ("1", "2", "3")
    dnp = (*source.dnp_components, *(("U3",) if regulator_dnp else ()))
    return source.model_copy(
        update={
            "components": components,
            "component_symbols": symbols,
            "component_pin_numbers": pin_numbers,
            "dnp_components": dnp,
            "nets": {
                "VIN": ("U1.1", "U3.1"),
                "VLOAD": ("U3.2", "U2.1", "C1.1"),
                "GND": ("U3.3", "C1.2"),
            },
            "pin_functions": {
                "U1.1": "VOUT",
                "U2.1": "VIN",
                "U3.1": "VIN",
                "U3.2": "VOUT",
                "U3.3": "GND",
            },
            "pin_electrical_types": {
                "U1.1": "power_out",
                "U2.1": "power_in",
                "U3.1": "power_in",
                "U3.2": "power_out",
            },
        }
    )


def lint_report(netlist: NetlistContract, policy: DesignLintPolicy | None = None):
    netlist_sha256 = hashlib.sha256(netlist.model_dump_json().encode("utf-8")).hexdigest()
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-power-input-path",
        observed=netlist,
        netlist_sha256=netlist_sha256,
    )
    return evaluate("synthetic-power-input-path", coach, policy or DesignLintPolicy())
