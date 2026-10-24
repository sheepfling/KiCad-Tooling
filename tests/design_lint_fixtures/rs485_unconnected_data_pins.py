"""Synthetic RS-485 transceiver netlists for partial data-pin review."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def rs485_unconnected_data_netlist(
    *,
    open_pin: str | None = "U1.2",
    functions: tuple[str, str] = ("D", "R"),
    identity: str = "RS-485 transceiver",
    symbol: str = "Synthetic:Rs485Transceiver",
    dnp: bool = False,
) -> NetlistContract:
    """Build one native-shaped RS-485 IC with connected or partially open data pins."""
    assignments = {"HOST_TX": ("U1.1",), "HOST_RX": ("U1.2",)}
    if open_pin is not None:
        folded_open = open_pin.casefold()
        assignments = {
            net: tuple(pin for pin in pins if pin.casefold() != folded_open)
            for net, pins in assignments.items()
        }
        assignments = {net: pins for net, pins in assignments.items() if pins}
    return NetlistContract(
        components={"U1": ComponentContract(value=identity, footprint="Synthetic:IC")},
        nets=assignments,
        unconnected_nets={"unconnected": (() if open_pin is None else (open_pin,))},
        dnp_components=("U1",) if dnp else (),
        component_symbols={"U1": symbol},
        pin_functions={"U1.1": functions[0], "U1.2": functions[1]},
        component_pin_numbers={"U1": ("1", "2")},
    )
