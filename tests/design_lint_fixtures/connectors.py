"""Synthetic design-lint inputs for focused regression suites."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import (
    ComponentContract,
    NetlistContract,
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
        nets = {"COMMON_RETURN": return_pins}
    else:
        nets = {
            f"RETURN_PORT_{reference}": (f"J{reference}.7", f"J{reference}.9")
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


def generic_connector_power_input_netlist(
    *,
    connected: bool = False,
    function: str | None = "1",
    electrical_type: str = "power_in",
    dnp_references: tuple[str, ...] = (),
    references: tuple[str, ...] = ("J1", "J2"),
) -> NetlistContract:
    pins = tuple(f"{reference}.1" for reference in references)
    nets = {"+5V": pins} if connected else {}
    pin_functions = {pin: function for pin in pins} if function is not None else {}
    return NetlistContract(
        components={
            reference: ComponentContract(value="Synthetic port", footprint="Synthetic:Port")
            for reference in references
        },
        nets=nets,
        dnp_components=dnp_references,
        component_symbols={
            reference: "Synthetic:GenericPowerInputPort" for reference in references
        },
        component_pin_numbers={reference: ("1",) for reference in references},
        pin_functions=pin_functions,
        pin_electrical_types={pin: electrical_type for pin in pins},
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
