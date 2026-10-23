"""Synthetic RS-485 transceiver netlists for direction-label review."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def rs485_data_label_netlist(
    *,
    crossed: bool = True,
    functions: tuple[str, str] = ("D", "R"),
    dnp: bool = False,
) -> NetlistContract:
    """Build a two-data-pin transceiver with explicit UART labels."""
    nets = (
        {"UART1_RX": ("U1.1",), "UART1_TX": ("U1.2",)}
        if crossed
        else {"UART1_TX": ("U1.1",), "UART1_RX": ("U1.2",)}
    )
    return NetlistContract(
        components={"U1": ComponentContract(value="Synthetic RS-485", footprint="Synthetic:IC")},
        nets=nets,
        dnp_components=("U1",) if dnp else (),
        component_symbols={"U1": "Synthetic:Rs485Transceiver"},
        pin_functions={"U1.1": functions[0], "U1.2": functions[1]},
        pin_electrical_types={"U1.1": "passive", "U1.2": "passive"},
        component_pin_numbers={"U1": ("1", "2")},
    )
