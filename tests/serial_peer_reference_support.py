"""Synthetic serial endpoints, reference maps, and lint report builders."""

from __future__ import annotations

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    ContractCoachReport,
    DesignLintPolicy,
    NetlistContract,
    ReferenceBondRequirement,
    SerialDirectPeerRequirement,
    SerialEndpointRequirement,
    SerialPeerAnalysis,
    SerialPeerLinkRequirement,
    SerialPinNetRequirement,
)
from kicad_tooling.hwrepo.serial_participants import SerialPeerRosterContext

RULE_ID = "bus.serial_peer_reference_review"


def serial_reference_netlist(
    *,
    output_reference_net: str = "GND_A",
    input_reference_net: str = "GND_B",
    dnp: tuple[str, ...] = (),
) -> NetlistContract:
    reference_nets: dict[str, list[str]] = {output_reference_net: ["U1.9"]}
    reference_nets.setdefault(input_reference_net, []).append("U2.9")
    return NetlistContract(
        components={
            "U1": ComponentContract(
                value="Synthetic UART transmitter", footprint="Package:UART-TX"
            ),
            "U2": ComponentContract(value="Synthetic UART receiver", footprint="Package:UART-RX"),
        },
        nets={
            "UART_A": ("U1.1", "U2.1"),
            "UART_B": ("U1.2", "U2.2"),
            "+3V3": ("U1.8", "U2.8"),
            **{net: tuple(pins) for net, pins in reference_nets.items()},
        },
        dnp_components=dnp,
        component_symbols={
            "U1": "Synthetic:UartTransmitter",
            "U2": "Synthetic:UartReceiver",
        },
        pin_functions={
            "U1.1": "UART1_TX",
            "U1.2": "UART1_RX",
            "U1.8": "VDD",
            "U1.9": "GND",
            "U2.1": "UART1_RX",
            "U2.2": "UART1_TX",
            "U2.8": "VDD",
            "U2.9": "GND",
        },
        pin_electrical_types={
            "U1.1": "output",
            "U1.2": "input",
            "U1.8": "power_in",
            "U1.9": "power_in",
            "U2.1": "input",
            "U2.2": "output",
            "U2.8": "power_in",
            "U2.9": "power_in",
        },
        component_pin_numbers={
            "U1": ("1", "2", "8", "9"),
            "U2": ("1", "2", "8", "9"),
        },
    )


def labelled_serial_reference_netlist(
    *,
    first_reference_net: str = "GND_A",
    second_reference_net: str = "GND_B",
    dnp: tuple[str, ...] = (),
) -> NetlistContract:
    """Use exact UART channel labels with generic signal pin functions."""
    return NetlistContract(
        components={
            "U1": ComponentContract(value="Synthetic translator", footprint="Package:UART-TX"),
            "U2": ComponentContract(value="Synthetic serial bridge", footprint="Package:UART-RX"),
        },
        nets={
            "Compute module/UART.0.TX": ("U1.1", "U2.2"),
            "Compute module/UART.0.RX": ("U1.2", "U2.1"),
            "+3V3": ("U1.8", "U2.8"),
            first_reference_net: ("U1.9",),
            second_reference_net: ("U2.9",),
        },
        dnp_components=dnp,
        component_symbols={
            "U1": "Synthetic:UartTransmitter",
            "U2": "Synthetic:UartReceiver",
        },
        pin_functions={
            "U1.1": "B2",
            "U1.2": "B1",
            "U1.8": "VDD",
            "U1.9": "GND",
            "U2.1": "ADBUS0",
            "U2.2": "ADBUS1",
            "U2.8": "VDD",
            "U2.9": "GND",
        },
        pin_electrical_types={
            "U1.1": "tri_state",
            "U1.2": "tri_state",
            "U1.8": "power_in",
            "U1.9": "power_in",
            "U2.1": "bidirectional",
            "U2.2": "bidirectional",
            "U2.8": "power_in",
            "U2.9": "power_in",
        },
        component_pin_numbers={
            "U1": ("1", "2", "8", "9"),
            "U2": ("1", "2", "8", "9"),
        },
    )


def serial_peer_map(
    *,
    reference_policy: str,
    output_reference_net: str,
    input_reference_net: str,
    output_reference_pin: str = "U1.9",
    input_reference_pin: str = "U2.9",
    reference_bond: ReferenceBondRequirement | None = None,
) -> SerialPeerAnalysis:
    left = SerialEndpointRequirement(
        id="controller",
        reference="U1",
        symbol="Synthetic:UartTransmitter",
        footprint="Package:UART-TX",
        logic_domain="3V3",
        tx=SerialPinNetRequirement(pin="U1.1", net="UART_A"),
        rx=SerialPinNetRequirement(pin="U1.2", net="UART_B"),
        reference_pins=(
            SerialPinNetRequirement(pin=output_reference_pin, net=output_reference_net),
        ),
    )
    right = SerialEndpointRequirement(
        id="peripheral",
        reference="U2",
        symbol="Synthetic:UartReceiver",
        footprint="Package:UART-RX",
        logic_domain="3V3",
        tx=SerialPinNetRequirement(pin="U2.2", net="UART_B"),
        rx=SerialPinNetRequirement(pin="U2.1", net="UART_A"),
        reference_pins=(SerialPinNetRequirement(pin=input_reference_pin, net=input_reference_net),),
    )
    return SerialPeerAnalysis(
        basis="Synthetic reviewed direct serial peer and reference policy",
        links=(
            SerialPeerLinkRequirement(
                id="controller-peripheral",
                basis="Synthetic direct UART TX/RX link",
                endpoint=left,
                peer=SerialDirectPeerRequirement(mode="direct", endpoint=right),
                reference_policy=reference_policy,
                reference_bond=reference_bond,
            ),
        ),
    )


def bonded_serial_reference_netlist(*, fault: bool = False) -> NetlistContract:
    source = serial_reference_netlist()
    floating_net = "FLOATING_GND" if fault else "GND_B"
    return source.model_copy(
        update={
            "components": {
                **source.components,
                "R3": ComponentContract(value="0R", footprint="Synthetic:0603"),
            },
            "nets": {
                **source.nets,
                "GND_A": ("U1.9", "R3.1"),
                "GND_B": ("U2.9",) if fault else ("U2.9", "R3.2"),
                **({floating_net: ("R3.2",)} if fault else {}),
            },
            "component_symbols": {**source.component_symbols, "R3": "Device:R"},
            "component_pin_numbers": {
                **source.component_pin_numbers,
                "R3": ("1", "2"),
            },
            "pin_functions": {
                **source.pin_functions,
                "R3.1": "~",
                "R3.2": "~",
            },
            "pin_electrical_types": {
                **source.pin_electrical_types,
                "R3.1": "passive",
                "R3.2": "passive",
            },
        }
    )


def ferrite_bonded_serial_reference_netlist(*, fault: bool = False) -> NetlistContract:
    """Represent an exact two-pin ferrite bead between reviewed reference nets."""
    source = serial_reference_netlist()
    floating_net = "FLOATING_GND" if fault else "GND_B"
    return source.model_copy(
        update={
            "components": {
                **source.components,
                "FB1": ComponentContract(value="600R @100MHz", footprint="Synthetic:0603Ferrite"),
            },
            "nets": {
                **source.nets,
                "GND_A": ("U1.9", "FB1.1"),
                "GND_B": ("U2.9",) if fault else ("U2.9", "FB1.2"),
                **({floating_net: ("FB1.2",)} if fault else {}),
            },
            "component_symbols": {**source.component_symbols, "FB1": "Device:FerriteBead"},
            "component_pin_numbers": {
                **source.component_pin_numbers,
                "FB1": ("1", "2"),
            },
            "pin_functions": {
                **source.pin_functions,
                "FB1.1": "~",
                "FB1.2": "~",
            },
            "pin_electrical_types": {
                **source.pin_electrical_types,
                "FB1.1": "passive",
                "FB1.2": "passive",
            },
        }
    )


def bonded_label_serial_reference_netlist(*, fault: bool = False) -> NetlistContract:
    source = bonded_serial_reference_netlist(fault=fault)
    nets = {name: pins for name, pins in source.nets.items() if name not in {"UART_A", "UART_B"}}
    nets.update(
        {
            "Compute module/UART.0.TX": ("U1.1", "U2.2"),
            "Compute module/UART.0.RX": ("U1.2", "U2.1"),
        }
    )
    return source.model_copy(
        update={
            "nets": nets,
            "pin_functions": {
                **source.pin_functions,
                "U1.1": "B2",
                "U1.2": "B1",
                "U2.1": "ADBUS0",
                "U2.2": "ADBUS1",
            },
            "pin_electrical_types": {
                **source.pin_electrical_types,
                "U1.1": "tri_state",
                "U1.2": "tri_state",
                "U2.1": "bidirectional",
                "U2.2": "bidirectional",
            },
        }
    )


def labelled_serial_peer_map(
    *,
    reference_policy: str,
    first_reference_net: str,
    second_reference_net: str,
    reference_bond: ReferenceBondRequirement | None = None,
) -> SerialPeerAnalysis:
    left = SerialEndpointRequirement(
        id="translator-side",
        reference="U1",
        symbol="Synthetic:UartTransmitter",
        footprint="Package:UART-TX",
        logic_domain="3V3",
        tx=SerialPinNetRequirement(pin="U1.1", net="Compute module/UART.0.TX"),
        rx=SerialPinNetRequirement(pin="U1.2", net="Compute module/UART.0.RX"),
        reference_pins=(SerialPinNetRequirement(pin="U1.9", net=first_reference_net),),
    )
    right = SerialEndpointRequirement(
        id="bridge-side",
        reference="U2",
        symbol="Synthetic:UartReceiver",
        footprint="Package:UART-RX",
        logic_domain="3V3",
        tx=SerialPinNetRequirement(pin="U2.1", net="Compute module/UART.0.RX"),
        rx=SerialPinNetRequirement(pin="U2.2", net="Compute module/UART.0.TX"),
        reference_pins=(SerialPinNetRequirement(pin="U2.9", net=second_reference_net),),
    )
    return SerialPeerAnalysis(
        basis="Synthetic reviewed label-identified serial segment and reference policy",
        links=(
            SerialPeerLinkRequirement(
                id="translator-bridge",
                basis="Synthetic direct TX/RX net-label pair",
                endpoint=left,
                peer=SerialDirectPeerRequirement(mode="direct", endpoint=right),
                reference_policy=reference_policy,
                reference_bond=reference_bond,
            ),
        ),
    )


def serial_connector_reference_netlist(
    *, output_reference_net: str = "GND_A", input_reference_net: str = "GND_B"
) -> NetlistContract:
    references: dict[str, list[str]] = {output_reference_net: ["U1.4"]}
    references.setdefault(input_reference_net, []).append("J1.4")
    return NetlistContract(
        components={
            "U1": ComponentContract(
                value="Synthetic UART controller", footprint="Package:UART-CONTROLLER"
            ),
            "J1": ComponentContract(value="Synthetic UART header", footprint="Package:UART-HEADER"),
        },
        nets={
            "UART_TX": ("J1.1", "U1.1"),
            "UART_RX": ("J1.2", "U1.2"),
            "+3V3": ("J1.3", "U1.3"),
            **{net: tuple(sorted(pins)) for net, pins in references.items()},
        },
        component_symbols={
            "U1": "Synthetic:UartController",
            "J1": "Synthetic:UartHeader",
        },
        pin_functions={
            "U1.1": "UART1_TX",
            "U1.2": "UART1_RX",
            "U1.3": "VDD",
            "U1.4": "GND",
            "J1.1": "UART1_RX",
            "J1.2": "UART1_TX",
            "J1.3": "VDD",
            "J1.4": "GND",
        },
        pin_electrical_types={
            "U1.1": "output",
            "U1.2": "input",
            "U1.3": "power_in",
            "U1.4": "power_in",
            "J1.1": "input",
            "J1.2": "output",
            "J1.3": "passive",
            "J1.4": "passive",
        },
        component_pin_numbers={"U1": ("1", "2", "3", "4"), "J1": ("1", "2", "3", "4")},
    )


def multi_uart_connector_reference_netlist(*, common_first_return: bool = False) -> NetlistContract:
    """One MCU with two UART headers: one split-reference fault and one control."""
    source = serial_connector_reference_netlist()
    nets = {net: tuple(pins) for net, pins in source.nets.items()}
    nets["+3V3"] = (*nets["+3V3"], "J2.3")
    nets["GND_A"] = (*nets["GND_A"], "J2.4")
    nets["UART2_TX"] = ("U1.5", "J2.1")
    nets["UART2_RX"] = ("U1.6", "J2.2")
    if common_first_return:
        nets["GND_A"] = (*nets["GND_A"], "J1.4")
        nets.pop("GND_B")

    return source.model_copy(
        update={
            "components": {
                **source.components,
                "J2": ComponentContract(
                    value="Synthetic second UART header", footprint="Package:UART-HEADER"
                ),
            },
            "nets": nets,
            "component_symbols": {
                **source.component_symbols,
                "J2": "Synthetic:UartHeader",
            },
            "pin_functions": {
                **source.pin_functions,
                "U1.5": "UART2_TX",
                "U1.6": "UART2_RX",
                "J2.1": "UART2_RX",
                "J2.2": "UART2_TX",
                "J2.3": "VDD",
                "J2.4": "GND",
            },
            "pin_electrical_types": {
                **source.pin_electrical_types,
                "U1.5": "output",
                "U1.6": "input",
                "J2.1": "input",
                "J2.2": "output",
                "J2.3": "passive",
                "J2.4": "passive",
            },
            "component_pin_numbers": {
                **source.component_pin_numbers,
                "U1": (*source.component_pin_numbers["U1"], "5", "6"),
                "J2": ("1", "2", "3", "4"),
            },
        }
    )


def serial_connector_peer_map(
    *, reference_policy: str, output_reference_net: str, input_reference_net: str
) -> SerialPeerAnalysis:
    return SerialPeerAnalysis(
        basis="Synthetic reviewed MCU-to-header UART link and reference policy",
        links=(
            SerialPeerLinkRequirement(
                id="controller-header",
                basis="Synthetic direct UART header link",
                endpoint=SerialEndpointRequirement(
                    id="controller",
                    reference="U1",
                    symbol="Synthetic:UartController",
                    footprint="Package:UART-CONTROLLER",
                    logic_domain="3V3",
                    tx=SerialPinNetRequirement(pin="U1.1", net="UART_TX"),
                    rx=SerialPinNetRequirement(pin="U1.2", net="UART_RX"),
                    reference_pins=(SerialPinNetRequirement(pin="U1.4", net=output_reference_net),),
                ),
                peer=SerialDirectPeerRequirement(
                    mode="direct",
                    endpoint=SerialEndpointRequirement(
                        id="header",
                        reference="J1",
                        symbol="Synthetic:UartHeader",
                        footprint="Package:UART-HEADER",
                        logic_domain="3V3",
                        tx=SerialPinNetRequirement(pin="J1.2", net="UART_RX"),
                        rx=SerialPinNetRequirement(pin="J1.1", net="UART_TX"),
                        reference_pins=(
                            SerialPinNetRequirement(pin="J1.4", net=input_reference_net),
                        ),
                    ),
                ),
                reference_policy=reference_policy,
            ),
        ),
    )


def report(
    source: NetlistContract,
    *,
    policy: DesignLintPolicy | None = None,
    serial_peers: SerialPeerAnalysis | None = None,
):
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-serial-reference",
        observed=source,
        netlist_sha256="a" * 64,
    )
    return evaluate(
        "synthetic-serial-reference",
        coach,
        policy or DesignLintPolicy(),
        serial_peer_roster=(
            SerialPeerRosterContext(state="required", analysis=serial_peers)
            if serial_peers is not None
            else SerialPeerRosterContext(state="not_configured")
        ),
    )
