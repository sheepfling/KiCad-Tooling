"""Synthetic RS-485 transceiver pins assigned to named rails."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def rs485_signal_named_rail_netlist(
    *,
    pin: str = "U1.1",
    rail_name: str = "GND",
    function: str = "D",
    identity: str = "RS-485 transceiver",
    symbol: str = "Synthetic:Rs485Transceiver",
    dnp: bool = False,
) -> NetlistContract:
    """Assign one explicit RS-485 D/R role to a rail-like net label."""
    functions = {"U1.1": "D", "U1.2": "R"}
    if pin not in functions:
        raise ValueError(f"Unsupported synthetic RS-485 data pin: {pin}")
    functions[pin] = function
    nets = {"HOST_TX": ("U1.1",), "HOST_RX": ("U1.2",)}
    nets.pop("HOST_TX" if pin == "U1.1" else "HOST_RX")
    nets[rail_name] = (pin,)
    return NetlistContract(
        components={"U1": ComponentContract(value=identity, footprint="Synthetic:IC")},
        nets=nets,
        dnp_components=("U1",) if dnp else (),
        component_symbols={"U1": symbol},
        pin_functions=functions,
        component_pin_numbers={"U1": ("1", "2")},
    )
