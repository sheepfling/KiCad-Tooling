"""Synthetic serial peer-voltage and labeled-reference netlists."""

from __future__ import annotations

import json
from pathlib import Path
from types import MappingProxyType

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract

SERIAL_LABEL_EXPECTED_NETS = MappingProxyType(
    {
        net: tuple(pins)
        for net, pins in json.loads(
            (
                Path(__file__).resolve().parents[1]
                / "fixtures/design_lint/serial-peer-connector-reference-native/"
                "serial-label-expected-nets.json"
            ).read_text(encoding="utf-8")
        ).items()
    }
)


def serial_peer_netlist(*, split_supplies: bool, split_references: bool = False) -> NetlistContract:
    rails = (
        {"+3V3": ("U1.2", "U2.2")} if not split_supplies else {"+5V": ("U1.2",), "+3V3": ("U2.2",)}
    )
    references = (
        {"GND_A": ("U1.3",), "GND_B": ("U2.3",)} if split_references else {"GND": ("U1.3", "U2.3")}
    )
    return NetlistContract(
        components={
            "U1": ComponentContract(
                value="Synthetic UART transmitter", footprint="Synthetic:QFN-2"
            ),
            "U2": ComponentContract(value="Synthetic UART receiver", footprint="Synthetic:QFN-2"),
        },
        nets={
            "UART_TX": ("U1.1", "U2.1"),
            **rails,
            **references,
        },
        component_symbols={
            "U1": "Synthetic:UartTransmitter",
            "U2": "Synthetic:UartReceiver",
        },
        pin_functions={
            "U1.1": "UART1_TX",
            "U1.2": "VDD",
            "U1.3": "GND",
            "U2.1": "UART1_RX",
            "U2.2": "VDD",
            "U2.3": "GND",
        },
        pin_electrical_types={
            "U1.1": "output",
            "U1.2": "power_in",
            "U1.3": "power_in",
            "U2.1": "input",
            "U2.2": "power_in",
            "U2.3": "power_in",
        },
        component_pin_numbers={"U1": ("1", "2", "3"), "U2": ("1", "2", "3")},
    )


def serial_label_reference_netlist(*, split_references: bool) -> NetlistContract:
    """Mirror the labeled signal assignments in the fixture manifest."""
    references = (
        {"GND_A": ("U1.4", "U2.4")}
        if not split_references
        else {"GND_A": ("U1.4",), "GND_B": ("U2.4",)}
    )
    return NetlistContract(
        components={
            "U1": ComponentContract(
                value="Synthetic UART controller", footprint="Synthetic:UART-CONTROLLER"
            ),
            "U2": ComponentContract(
                value="Synthetic serial bridge", footprint="Synthetic:UART-BRIDGE"
            ),
        },
        nets={
            **SERIAL_LABEL_EXPECTED_NETS,
            "+3V3": ("U1.3", "U2.3"),
            **references,
        },
        component_symbols={"U1": "Synthetic:UartController", "U2": "Synthetic:UartBridge"},
        pin_functions={
            "U1.1": "B2",
            "U1.2": "B1",
            "U1.3": "VDD",
            "U1.4": "GND",
            "U2.1": "ADBUS0",
            "U2.2": "ADBUS1",
            "U2.3": "VDD",
            "U2.4": "GND",
        },
        pin_electrical_types={
            "U1.1": "output",
            "U1.2": "input",
            "U1.3": "power_in",
            "U1.4": "power_in",
            "U2.1": "input",
            "U2.2": "output",
            "U2.3": "passive",
            "U2.4": "passive",
        },
        component_pin_numbers={"U1": ("1", "2", "3", "4"), "U2": ("1", "2", "3", "4")},
    )


def serial_label_connector_reference_netlist(*, split_references: bool) -> NetlistContract:
    """Use generic channel-labeled pins between an IC and a bounded J connector."""
    source = serial_label_reference_netlist(split_references=True)

    def connector_pin(pin: str) -> str:
        return pin.replace("U2.", "J1.", 1)

    nets = {
        net: tuple(sorted(connector_pin(pin) for pin in pins)) for net, pins in source.nets.items()
    }
    if not split_references:
        nets["GND_A"] = tuple(sorted((*nets["GND_A"], *nets.pop("GND_B"))))

    return source.model_copy(
        update={
            "components": {"U1": source.components["U1"], "J1": source.components["U2"]},
            "nets": nets,
            "component_symbols": {
                "U1": source.component_symbols["U1"],
                "J1": source.component_symbols["U2"],
            },
            "pin_functions": {
                pin.replace("U2.", "J1.", 1) if pin.startswith("U2.") else pin: function
                for pin, function in source.pin_functions.items()
            },
            "pin_electrical_types": {
                pin.replace("U2.", "J1.", 1) if pin.startswith("U2.") else pin: kind
                for pin, kind in source.pin_electrical_types.items()
            },
            "component_pin_numbers": {
                "U1": source.component_pin_numbers["U1"],
                "J1": source.component_pin_numbers["U2"],
            },
        }
    )


def serial_optically_isolated_uart_netlist() -> NetlistContract:
    """Model a two-channel optical boundary between independently grounded UARTs."""
    return NetlistContract(
        components={
            "U1": ComponentContract(value="Synthetic host UART", footprint="Synthetic:UART-HOST"),
            "U2": ComponentContract(
                value="Synthetic target UART", footprint="Synthetic:UART-TARGET"
            ),
            "U3": ComponentContract(
                value="Synthetic optical isolator", footprint="Synthetic:SOIC-8"
            ),
        },
        nets={
            "HOST_TO_ISOLATOR_A": ("U1.1", "U3.1"),
            "HOST_FROM_ISOLATOR_B": ("U1.2", "U3.2"),
            "DEVICE_FROM_ISOLATOR_A": ("U2.1", "U3.3"),
            "DEVICE_TO_ISOLATOR_B": ("U2.2", "U3.4"),
            "VDD_HOST": ("U1.3", "U3.5"),
            "GND_HOST": ("U1.4", "U3.6"),
            "VDD_DEVICE": ("U2.3", "U3.7"),
            "GND_DEVICE": ("U2.4", "U3.8"),
        },
        component_symbols={
            "U1": "Synthetic:UartController",
            "U2": "Synthetic:UartTarget",
            "U3": "Synthetic:UartOpticalIsolator",
        },
        pin_functions={
            "U1.1": "UART1_TX",
            "U1.2": "UART1_RX",
            "U1.3": "VDD",
            "U1.4": "GND",
            "U2.1": "UART1_RX",
            "U2.2": "UART1_TX",
            "U2.3": "VDD",
            "U2.4": "GND",
            "U3.1": "CHANNEL_A_INPUT",
            "U3.2": "CHANNEL_A_OUTPUT",
            "U3.3": "CHANNEL_B_OUTPUT",
            "U3.4": "CHANNEL_B_INPUT",
            "U3.5": "VDD_HOST",
            "U3.6": "GND_HOST",
            "U3.7": "VDD_DEVICE",
            "U3.8": "GND_DEVICE",
        },
        pin_electrical_types={
            "U1.1": "output",
            "U1.2": "input",
            "U1.3": "power_in",
            "U1.4": "power_in",
            "U2.1": "input",
            "U2.2": "output",
            "U2.3": "power_in",
            "U2.4": "power_in",
            "U3.1": "input",
            "U3.2": "output",
            "U3.3": "output",
            "U3.4": "input",
            "U3.5": "power_in",
            "U3.6": "power_in",
            "U3.7": "power_in",
            "U3.8": "power_in",
        },
        component_pin_numbers={
            "U1": ("1", "2", "3", "4"),
            "U2": ("1", "2", "3", "4"),
            "U3": ("1", "2", "3", "4", "5", "6", "7", "8"),
        },
    )
