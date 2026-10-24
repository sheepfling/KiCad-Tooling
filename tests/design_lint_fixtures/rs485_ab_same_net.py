"""Synthetic RS-485 A/B pin assignments for differential-line regressions."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def rs485_ab_same_net_netlist(
    *,
    shared: bool = True,
    functions: tuple[str, str] = ("A", "B"),
    identity: str = "RS-485 transceiver",
    symbol: str = "Synthetic:Rs485Transceiver",
    dnp: bool = False,
    pin_types: tuple[str, str] = ("passive", "passive"),
) -> NetlistContract:
    """Build a fitted or DNP two-line RS-485 transceiver with full inventory."""
    nets = (
        {"AB_SHARED": ("U1.1", "U1.2")} if shared else {"RS485_A": ("U1.1",), "RS485_B": ("U1.2",)}
    )
    return NetlistContract(
        components={"U1": ComponentContract(value=identity, footprint="Synthetic:IC")},
        nets=nets,
        dnp_components=("U1",) if dnp else (),
        component_symbols={"U1": symbol},
        pin_functions={"U1.1": functions[0], "U1.2": functions[1]},
        component_pin_numbers={"U1": ("1", "2")},
        pin_electrical_types={"U1.1": pin_types[0], "U1.2": pin_types[1]},
    )
