"""Minimal synthetic netlists for serial TX/RX label-direction review."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def serial_tx_rx_label_netlist(*, crossed: bool = True, dnp: bool = False) -> NetlistContract:
    """Build one fitted UART IC with TX and RX assigned to separate named nets."""
    nets = (
        {"USART1_RX": ("U1.1",), "USART1_TX": ("U1.2",)}
        if crossed
        else {"USART1_TX": ("U1.1",), "USART1_RX": ("U1.2",)}
    )
    return NetlistContract(
        components={"U1": ComponentContract(value="Synthetic UART", footprint="Synthetic:IC")},
        nets=nets,
        dnp_components=("U1",) if dnp else (),
        component_symbols={"U1": "Synthetic:UartController"},
        pin_functions={"U1.1": "USART1_TX", "U1.2": "USART1_RX"},
        pin_electrical_types={"U1.1": "passive", "U1.2": "passive"},
        component_pin_numbers={"U1": ("1", "2")},
    )
