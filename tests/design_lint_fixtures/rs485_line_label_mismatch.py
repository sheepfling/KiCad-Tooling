"""Synthetic RS-485 A/B function and net-label assignments."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import NetlistContract

from .rs485_line_named_rail import rs485_line_named_rail_netlist


def rs485_line_label_mismatch_netlist(*, crossed: bool = True) -> NetlistContract:
    """Return a complete explicit RS-485 A/B pair with chosen labels."""
    source = rs485_line_named_rail_netlist(rail_name="RS485_A")
    nets = (
        {"RS485_B": ("U1.1",), "RS485_A": ("U1.2",)}
        if crossed
        else {"RS485_A": ("U1.1",), "RS485_B": ("U1.2",)}
    )
    return source.model_copy(update={"nets": nets})
