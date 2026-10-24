"""Synthetic UART/USART signal assignments for named-rail review checks."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import NetlistContract

from .serial_tx_rx_label_mismatch import serial_tx_rx_label_netlist


def serial_signal_on_named_rail_netlist(
    *, rail_name: str = "GND", pin: str = "U1.1"
) -> NetlistContract:
    """Move one explicit serial signal pin from its channel net to a rail label."""
    source = serial_tx_rx_label_netlist(crossed=False)
    remaining_nets = {
        name: tuple(member for member in pins if member.casefold() != pin.casefold())
        for name, pins in source.nets.items()
    }
    nets = {name: pins for name, pins in remaining_nets.items() if pins}
    existing = nets.get(rail_name, ())
    nets[rail_name] = tuple(sorted((*existing, pin), key=lambda item: (item.casefold(), item)))
    return source.model_copy(update={"nets": nets})
