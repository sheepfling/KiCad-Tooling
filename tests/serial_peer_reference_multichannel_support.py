"""Synthetic multi-channel UART label fixtures."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract
from tests.serial_peer_reference_support import (
    labelled_serial_reference_netlist,
    multi_uart_connector_reference_netlist,
)


def multi_channel_labelled_serial_reference_netlist(
    *, common_reference: bool = False
) -> NetlistContract:
    """Build three direct UART label channels between generic-function ICs."""
    base = labelled_serial_reference_netlist(
        first_reference_net="GND",
        second_reference_net="GND" if common_reference else "GND_B",
    )
    nets = {name: pins for name, pins in base.nets.items() if name not in {"GND_A", "GND_B", "GND"}}
    if common_reference:
        nets["GND"] = ("U1.9", "U2.9")
    else:
        nets["GND_A"] = ("U1.9",)
        nets["GND_B"] = ("U2.9",)

    pin_functions = dict(base.pin_functions)
    pin_electrical_types = dict(base.pin_electrical_types)
    pin_numbers = dict(base.component_pin_numbers)
    for channel in (1, 2):
        first_pin = channel * 2 + 1
        second_pin = first_pin + 1
        nets[f"Compute module/UART.{channel}.TX"] = (
            f"U1.{first_pin}",
            f"U2.{second_pin}",
        )
        nets[f"Compute module/UART.{channel}.RX"] = (
            f"U1.{second_pin}",
            f"U2.{first_pin}",
        )
        for reference in ("U1", "U2"):
            tx_pin = first_pin if reference == "U1" else second_pin
            rx_pin = second_pin if reference == "U1" else first_pin
            pin_functions[f"{reference}.{tx_pin}"] = f"D{channel}"
            pin_functions[f"{reference}.{rx_pin}"] = f"D{channel + 1}"
            pin_electrical_types[f"{reference}.{tx_pin}"] = "tri_state"
            pin_electrical_types[f"{reference}.{rx_pin}"] = "bidirectional"
            pin_numbers[reference] = (*pin_numbers[reference], str(tx_pin), str(rx_pin))

    return base.model_copy(
        update={
            "nets": nets,
            "pin_functions": pin_functions,
            "pin_electrical_types": pin_electrical_types,
            "component_pin_numbers": pin_numbers,
        }
    )


def three_uart_connector_reference_netlist(*, common_references: bool = False) -> NetlistContract:
    """Add a third direct UART header to the two-header fault/control topology."""
    source = multi_uart_connector_reference_netlist(common_first_return=common_references)
    return source.model_copy(
        update={
            "components": {
                **source.components,
                "J3": ComponentContract(
                    value="Synthetic third UART header", footprint="Package:UART-HEADER"
                ),
            },
            "nets": {
                **source.nets,
                "UART3_TX": ("U1.7", "J3.1"),
                "UART3_RX": ("U1.8", "J3.2"),
                "+3V3": (*source.nets["+3V3"], "J3.3"),
                "GND_A": (*source.nets["GND_A"], "J3.4"),
            },
            "component_symbols": {
                **source.component_symbols,
                "J3": "Synthetic:UartHeader",
            },
            "pin_functions": {
                **source.pin_functions,
                "U1.7": "UART3_TX",
                "U1.8": "UART3_RX",
                "J3.1": "UART3_RX",
                "J3.2": "UART3_TX",
                "J3.3": "VDD",
                "J3.4": "GND",
            },
            "pin_electrical_types": {
                **source.pin_electrical_types,
                "U1.7": "output",
                "U1.8": "input",
                "J3.1": "input",
                "J3.2": "output",
                "J3.3": "passive",
                "J3.4": "passive",
            },
            "component_pin_numbers": {
                **source.component_pin_numbers,
                "U1": (*source.component_pin_numbers["U1"], "7", "8"),
                "J3": ("1", "2", "3", "4"),
            },
        }
    )
