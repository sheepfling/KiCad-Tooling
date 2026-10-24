"""Synthetic RS-485 A/B bus-line pins assigned to named rails."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def rs485_line_named_rail_netlist(
    *,
    pin: str = "U1.1",
    rail_name: str = "GND",
    function: str = "A",
    identity: str = "RS-485 transceiver",
    symbol: str = "Synthetic:Rs485Transceiver",
    dnp: bool = False,
) -> NetlistContract:
    """Assign one explicit A/B line function to a rail-like net label."""
    functions = {"U1.1": "A", "U1.2": "B"}
    if pin not in functions:
        raise ValueError(f"Unsupported synthetic RS-485 bus-line pin: {pin}")
    functions[pin] = function
    nets = {"RS485_A": ("U1.1",), "RS485_B": ("U1.2",)}
    nets.pop("RS485_A" if pin == "U1.1" else "RS485_B")
    nets[rail_name] = (pin,)
    return NetlistContract(
        components={"U1": ComponentContract(value=identity, footprint="Synthetic:IC")},
        nets=nets,
        dnp_components=("U1",) if dnp else (),
        component_symbols={"U1": symbol},
        pin_functions=functions,
        component_pin_numbers={"U1": ("1", "2")},
    )
