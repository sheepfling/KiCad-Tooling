"""Synthetic serial-roster netlists and report builders shared by focused tests."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import (
    ComponentContract,
    ContractCoachReport,
    NetlistContract,
    SerialDirectPeerRequirement,
    SerialEndpointRequirement,
    SerialPeerAnalysis,
    SerialPeerLinkRequirement,
    SerialPinNetRequirement,
)

_NETLIST_SHA256 = "a" * 64


def serial_netlist(*, dnp: tuple[str, ...] = ()) -> NetlistContract:
    components = {
        reference: ComponentContract(value=f"Synthetic {reference}", footprint="Synthetic:Header")
        for reference in ("J1", "J2", "J3", "J4", "U1")
    }
    functions = {
        "J1.1": "TX",
        "J1.2": "RX",
        "J2.1": "TXD",
        "J2.2": "RXD",
        "J3.1": "UART_TXD",
        "J3.2": "UART_RXD",
        "J4.1": "TX",
        "J4.2": "RX",
        "U1.1": "USART1_TX",
        "U1.2": "USART1_RX",
        "U1.3": "UART2_TXD",
        "U1.4": "UART2_RXD",
        "U1.5": "TX+",
        "U1.6": "RX-",
    }
    nets = {
        "SERIAL_A_TX": ("J1.1", "J2.2"),
        "SERIAL_A_RX": ("J1.2", "J2.1"),
        "SERIAL_B_TX": ("J3.1",),
        "SERIAL_B_RX": ("J3.2",),
        "J4_TX": ("J4.1",),
        "J4_RX": ("J4.2",),
        "UART1_TX": ("U1.1",),
        "UART1_RX": ("U1.2",),
        "UART2_TX": ("U1.3",),
        "UART2_RX": ("U1.4",),
        "DIFF_TX_P": ("U1.5",),
        "DIFF_RX_N": ("U1.6",),
    }
    return NetlistContract(
        components=components,
        nets=nets,
        dnp_components=dnp,
        component_symbols={reference: f"Synthetic:{reference}" for reference in components},
        pin_functions=functions,
        component_pin_numbers={
            reference: tuple(
                pin.rsplit(".", 1)[1] for pin in functions if pin.startswith(f"{reference}.")
            )
            for reference in components
        },
    )


def alternate_function_serial_netlist(*, dnp: tuple[str, ...] = ()) -> NetlistContract:
    """Use explicit UART net labels with MCU package-pin functions and generic connector pins."""
    components = {
        "U1": ComponentContract(value="Synthetic MCU", footprint="Synthetic:MCU"),
        "J5": ComponentContract(value="Synthetic serial header", footprint="Synthetic:Header"),
    }
    return NetlistContract(
        components=components,
        nets={
            "UART_TX": ("J5.1", "U1.1"),
            "UART_RX": ("J5.2", "U1.2"),
            "GND": ("J5.3", "U1.3"),
        },
        dnp_components=dnp,
        component_symbols={"U1": "Synthetic:GPIO_MCU", "J5": "Synthetic:GenericHeader"},
        pin_functions={
            "U1.1": "PA2",
            "U1.2": "PA3",
            "U1.3": "VSS",
            "J5.1": "Pin_1",
            "J5.2": "Pin_2",
            "J5.3": "Pin_3",
        },
        pin_electrical_types={
            "U1.1": "bidirectional",
            "U1.2": "bidirectional",
            "U1.3": "power_in",
            "J5.1": "passive",
            "J5.2": "passive",
            "J5.3": "passive",
        },
        component_pin_numbers={"U1": ("1", "2", "3"), "J5": ("1", "2", "3")},
    )


def endpoint(
    reference: str,
    *,
    tx_pin: str,
    tx_net: str,
    rx_pin: str,
    rx_net: str,
) -> SerialEndpointRequirement:
    return SerialEndpointRequirement(
        id=reference,
        reference=reference,
        symbol=f"Synthetic:{reference}",
        footprint="Synthetic:Header",
        logic_domain="3V3",
        tx=SerialPinNetRequirement(pin=tx_pin, net=tx_net),
        rx=SerialPinNetRequirement(pin=rx_pin, net=rx_net),
    )


def serial_peers() -> SerialPeerAnalysis:
    left = endpoint("J1", tx_pin="J1.1", tx_net="SERIAL_A_TX", rx_pin="J1.2", rx_net="SERIAL_A_RX")
    right = endpoint("J2", tx_pin="J2.1", tx_net="SERIAL_A_RX", rx_pin="J2.2", rx_net="SERIAL_A_TX")
    return SerialPeerAnalysis(
        basis="Synthetic reviewed logic-level UART peer map",
        links=(
            SerialPeerLinkRequirement(
                id="main-console",
                basis="Synthetic paired connector endpoints",
                endpoint=left,
                peer=SerialDirectPeerRequirement(mode="direct", endpoint=right),
                reference_policy="not_applicable",
            ),
        ),
    )


def alternate_function_serial_peer_analysis() -> SerialPeerAnalysis:
    """Return the exact synthetic MCU-to-header UART map for label discovery tests."""
    mapped_endpoint = SerialEndpointRequirement(
        id="U1",
        reference="U1",
        symbol="Synthetic:GPIO_MCU",
        footprint="Synthetic:MCU",
        logic_domain="3V3",
        tx=SerialPinNetRequirement(pin="U1.1", net="UART_TX"),
        rx=SerialPinNetRequirement(pin="U1.2", net="UART_RX"),
    )
    mapped_connector = SerialEndpointRequirement(
        id="J5",
        reference="J5",
        symbol="Synthetic:GenericHeader",
        footprint="Synthetic:Header",
        logic_domain="3V3",
        tx=SerialPinNetRequirement(pin="J5.2", net="UART_RX"),
        rx=SerialPinNetRequirement(pin="J5.1", net="UART_TX"),
    )
    return SerialPeerAnalysis(
        basis="Synthetic project-authored net-label endpoint map",
        links=(
            SerialPeerLinkRequirement(
                id="mcu-header",
                basis="Synthetic exact endpoint map",
                endpoint=mapped_endpoint,
                peer=SerialDirectPeerRequirement(mode="direct", endpoint=mapped_connector),
                reference_policy="not_applicable",
            ),
        ),
    )


def coach(observed: NetlistContract, netlist_sha256: str = _NETLIST_SHA256) -> ContractCoachReport:
    return ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-serial-roster",
        observed=observed,
        netlist_sha256=netlist_sha256,
    )
