"""Synthetic connector coverage inputs shared by focused test themes."""

from __future__ import annotations

from kicad_tooling.hwrepo.connector_coverage import evaluate
from kicad_tooling.hwrepo.models import (
    ConnectorCoverageReport,
    ConnectorInterfaceReview,
    ConnectorInventoryReview,
    InterfacePin,
    InterfaceRecord,
    NetlistContract,
)


def inventory_review() -> ConnectorInventoryReview:
    return ConnectorInventoryReview(
        basis="Synthetic review covered the complete schematic symbol inventory"
    )


def interface_record() -> InterfaceRecord:
    return InterfaceRecord(
        id="debug-port",
        revision="synthetic-1",
        pins=(
            InterfacePin(
                number="1",
                signal="TX",
                direction="output",
                voltage_domain="logic-3v3",
                mating="RX",
                orientation="straight",
                mechanical_clearance="synthetic",
            ),
            InterfacePin(
                number="2",
                signal="RX",
                direction="input",
                voltage_domain="logic-3v3",
                mating="TX",
                orientation="straight",
                mechanical_clearance="synthetic",
            ),
        ),
    )


def observed_connector(*, candidate: bool = True) -> NetlistContract:
    return NetlistContract(
        components={},
        nets={"TX": ("J1.1",)},
        component_symbols={"J1": "Synthetic:DebugConnector"} if candidate else {},
        component_pin_numbers={"J1": ("1", "2", "3")} if candidate else {},
    )


def connector_return_role_netlist(
    *,
    common_return: bool = False,
    open_return: bool = False,
    open_supply: bool = False,
) -> NetlistContract:
    return_nets = {"USB_RETURN": ("J1.3",), "SERIAL_RETURN": ("J2.3",)}
    if common_return:
        return_nets = {"COMMON_RETURN": ("J1.3",) if open_return else ("J1.3", "J2.3")}
    elif open_return:
        return_nets = {"USB_RETURN": ("J1.3",)}
    return NetlistContract(
        components={},
        nets={
            **return_nets,
            "USB_DATA_1": ("J1.1",),
            "USB_DATA_2": ("J1.2",),
            "SERIAL_TX": ("J2.1",),
            "SERIAL_RX": ("J2.2",),
            **({} if open_supply else {"SERIAL_SUPPLY": ("J2.4",)}),
        },
        component_symbols={"J1": "Connector:USB_C_Receptacle_USB2.0_16P", "J2": "Connector:DB9"},
        component_pin_numbers={"J1": ("1", "2", "3"), "J2": ("1", "2", "3", "4")},
        pin_functions={
            "J1.1": "D+",
            "J1.2": "D-",
            "J1.3": "GND",
            "J2.1": "TX",
            "J2.2": "RX",
            "J2.3": "Pin_3",
            "J2.4": "Pin_4",
        },
    )


def uart_peer_netlist(*, split_return: bool = False) -> NetlistContract:
    return_nets = (
        {"UART1_RETURN": ("J1.3",), "UART2_RETURN": ("J2.3",)}
        if split_return
        else {"GND": ("J1.3", "J2.3")}
    )
    return NetlistContract(
        components={},
        nets={
            **return_nets,
            "UART1_TX": ("J1.1",),
            "UART1_RX": ("J1.2",),
            "UART2_TX": ("J2.1",),
            "UART2_RX": ("J2.2",),
        },
        component_symbols={
            "J1": "Connector_Generic:Conn_01x03",
            "J2": "Connector_Generic:Conn_01x03",
        },
        component_pin_numbers={"J1": ("1", "2", "3"), "J2": ("1", "2", "3")},
        pin_functions={
            f"{reference}.{pin}": f"Pin_{pin}"
            for reference in ("J1", "J2")
            for pin in ("1", "2", "3")
        },
    )


def uart_header_interface(identifier: str) -> InterfaceRecord:
    return InterfaceRecord(
        id=identifier,
        revision="synthetic-1",
        pins=(
            InterfacePin(
                number="1",
                signal="TX",
                role="signal",
                direction="output",
                voltage_domain="logic-3v3",
                mating="RX",
                orientation="straight",
                mechanical_clearance="synthetic",
            ),
            InterfacePin(
                number="2",
                signal="RX",
                role="signal",
                direction="input",
                voltage_domain="logic-3v3",
                mating="TX",
                orientation="straight",
                mechanical_clearance="synthetic",
            ),
            InterfacePin(
                number="3",
                signal="GND",
                role="return",
                direction="passive",
                voltage_domain="signal-return",
                mating="GND",
                orientation="straight",
                mechanical_clearance="synthetic",
            ),
        ),
    )


def uart_header_coverage(
    observed: NetlistContract,
    *,
    groups: tuple[str, str],
    reverse_inputs: bool = False,
) -> ConnectorCoverageReport:
    identifiers = ("uart-header-1", "uart-header-2")
    interfaces = {identifier: uart_header_interface(identifier) for identifier in identifiers}
    review_pairs = tuple(zip(("J1", "J2"), identifiers, groups, strict=True))
    if reverse_inputs:
        identifiers = tuple(reversed(identifiers))
        interfaces = dict(reversed(tuple(interfaces.items())))
        review_pairs = tuple(reversed(review_pairs))
    reviews = tuple(
        ConnectorInterfaceReview(
            reference=reference,
            disposition="interface",
            basis=f"Reviewed {reference} as a separate 3.3 V UART interface",
            interface_id=interface_id,
            pin_map={"1": "1", "2": "2", "3": "3"},
            peer_assignment_group=group,
            peer_assignment_basis=(
                f"Reviewed {reference} as a member of peer-assignment group {group}"
            ),
        )
        for reference, interface_id, group in review_pairs
    )
    return evaluate(
        observed,
        identifiers,
        reviews,
        interfaces=interfaces,
        interface_catalog_path="catalog/interfaces.json",
        interface_catalog_sha256="a" * 64,
        inventory_review=inventory_review(),
    )


def connector_return_role_catalog() -> dict[str, InterfaceRecord]:
    return {
        "usb-interface": InterfaceRecord(
            id="usb-interface",
            revision="synthetic-1",
            pins=(
                InterfacePin(
                    number="1",
                    signal="D+",
                    role="signal",
                    direction="bidirectional",
                    voltage_domain="logic",
                    mating="D+",
                    orientation="straight",
                    mechanical_clearance="synthetic",
                ),
                InterfacePin(
                    number="2",
                    signal="D-",
                    role="signal",
                    direction="bidirectional",
                    voltage_domain="logic",
                    mating="D-",
                    orientation="straight",
                    mechanical_clearance="synthetic",
                ),
                InterfacePin(
                    number="3",
                    signal="GND",
                    role="return",
                    direction="passive",
                    voltage_domain="return",
                    mating="GND",
                    orientation="straight",
                    mechanical_clearance="synthetic",
                ),
            ),
        ),
        "serial-interface": InterfaceRecord(
            id="serial-interface",
            revision="synthetic-1",
            pins=(
                InterfacePin(
                    number="1",
                    signal="TX",
                    role="signal",
                    direction="output",
                    voltage_domain="logic",
                    mating="RX",
                    orientation="straight",
                    mechanical_clearance="synthetic",
                ),
                InterfacePin(
                    number="2",
                    signal="RX",
                    role="signal",
                    direction="input",
                    voltage_domain="logic",
                    mating="TX",
                    orientation="straight",
                    mechanical_clearance="synthetic",
                ),
                InterfacePin(
                    number="3",
                    signal="RETURN",
                    role="return",
                    direction="passive",
                    voltage_domain="return",
                    mating="RETURN",
                    orientation="straight",
                    mechanical_clearance="synthetic",
                ),
                InterfacePin(
                    number="4",
                    signal="V+",
                    role="supply",
                    direction="passive",
                    voltage_domain="power",
                    mating="V+",
                    orientation="straight",
                    mechanical_clearance="synthetic",
                ),
            ),
        ),
    }


def connector_return_role_reviews() -> tuple[ConnectorInterfaceReview, ...]:
    return (
        ConnectorInterfaceReview(
            reference="J1",
            disposition="interface",
            basis="Synthetic USB interface map reviewed",
            interface_id="usb-interface",
            pin_map={"1": "1", "2": "2", "3": "3"},
        ),
        ConnectorInterfaceReview(
            reference="J2",
            disposition="interface",
            basis="Synthetic serial interface map reviewed",
            interface_id="serial-interface",
            pin_map={"1": "1", "2": "2", "3": "3", "4": "4"},
        ),
    )


def connector_supply_role_netlist(
    *, common_supply: bool = False, open_supply: bool = False
) -> NetlistContract:
    if open_supply:
        supply_nets = {"NODE_ALPHA": ("J1.2",)}
    elif common_supply:
        supply_nets = {"SHARED_SUPPLY": ("J1.2", "J2.5")}
    else:
        supply_nets = {"NODE_ALPHA": ("J1.2",), "NODE_BETA": ("J2.5",)}
    return NetlistContract(
        components={},
        nets=supply_nets,
        component_symbols={"J1": "Synthetic:UsbPort", "J2": "Synthetic:SerialPort"},
        component_pin_numbers={"J1": ("2",), "J2": ("5",)},
        pin_functions={"J1.2": "2", "J2.5": "Pin_5"},
    )


def connector_supply_role_catalog(
    *, serial_voltage_domain: str = "external-5v"
) -> dict[str, InterfaceRecord]:
    return {
        interface_id: InterfaceRecord(
            id=interface_id,
            revision="synthetic-1",
            pins=(
                InterfacePin(
                    number=pin_number,
                    signal="POWER",
                    role="supply",
                    direction="passive",
                    voltage_domain=(
                        serial_voltage_domain if interface_id == "serial-power" else "external-5v"
                    ),
                    mating="POWER",
                    orientation="straight",
                    mechanical_clearance="synthetic",
                ),
            ),
        )
        for interface_id, pin_number in (("usb-power", "2"), ("serial-power", "5"))
    }


def connector_supply_role_reviews() -> tuple[ConnectorInterfaceReview, ...]:
    return (
        ConnectorInterfaceReview(
            reference="J1",
            disposition="interface",
            basis="Synthetic USB power contact reviewed",
            interface_id="usb-power",
            pin_map={"2": "2"},
        ),
        ConnectorInterfaceReview(
            reference="J2",
            disposition="interface",
            basis="Synthetic serial power contact reviewed",
            interface_id="serial-power",
            pin_map={"5": "5"},
        ),
    )


def three_connector_supply_role_netlist(*, all_common: bool = False) -> NetlistContract:
    nets = (
        {"SHARED_SUPPLY": ("J1.2", "J2.5", "J3.9")}
        if all_common
        else {"SUPPLY_A": ("J1.2", "J2.5"), "SUPPLY_B": ("J3.9",)}
    )
    return NetlistContract(
        components={},
        nets=nets,
        component_symbols={
            "J1": "Synthetic:UsbPort",
            "J2": "Synthetic:SerialPort",
            "J3": "Synthetic:SensorPort",
        },
        component_pin_numbers={"J1": ("2",), "J2": ("5",), "J3": ("9",)},
        pin_functions={"J1.2": "2", "J2.5": "Pin_5", "J3.9": "9"},
    )


def three_connector_supply_role_catalog(
    *, sensor_voltage_domain: str = "external-5v"
) -> dict[str, InterfaceRecord]:
    return {
        **connector_supply_role_catalog(),
        "sensor-power": InterfaceRecord(
            id="sensor-power",
            revision="synthetic-1",
            pins=(
                InterfacePin(
                    number="9",
                    signal="POWER",
                    role="supply",
                    direction="passive",
                    voltage_domain=sensor_voltage_domain,
                    mating="POWER",
                    orientation="straight",
                    mechanical_clearance="synthetic",
                ),
            ),
        ),
    }


def three_connector_supply_role_reviews() -> tuple[ConnectorInterfaceReview, ...]:
    return (
        *connector_supply_role_reviews(),
        ConnectorInterfaceReview(
            reference="J3",
            disposition="interface",
            basis="Synthetic sensor power contact reviewed",
            interface_id="sensor-power",
            pin_map={"9": "9"},
        ),
    )
