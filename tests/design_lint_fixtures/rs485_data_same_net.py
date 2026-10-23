"""Synthetic RS-485 transceiver netlists for same-net review checks."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def rs485_data_same_net_netlist(
    *,
    shared: bool = True,
    functions: tuple[str, str] = ("D", "R"),
    identity: str = "RS-485 transceiver",
    symbol: str = "Synthetic:Rs485Transceiver",
    dnp: bool = False,
) -> NetlistContract:
    """Build one fitted RS-485 IC with a complete two-pin native inventory."""
    return NetlistContract(
        components={"U1": ComponentContract(value=identity, footprint="Synthetic:IC")},
        nets=(
            {"DATA_SHARED": ("U1.1", "U1.2")}
            if shared
            else {"HOST_TX": ("U1.1",), "HOST_RX": ("U1.2",)}
        ),
        dnp_components=("U1",) if dnp else (),
        component_symbols={"U1": symbol},
        pin_functions={"U1.1": functions[0], "U1.2": functions[1]},
        pin_electrical_types={"U1.1": "input", "U1.2": "output"},
        component_pin_numbers={"U1": ("1", "2")},
    )
