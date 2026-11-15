"""Synthetic RS-485 A/B bus-line pins assigned to named rails."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def rs485_line_named_rail_netlist(
    *,
    pin: str | None = None,
    rail_name: str = "GND",
    function: str = "A",
    identity: str | None = None,
    symbol: str | None = None,
    dnp: bool = False,
) -> NetlistContract:
    """Return a synthetic fitted RS-485 IC or explicitly identified connector."""
    selected_pin = "U1.1" if pin is None else pin
    reference, separator, number = selected_pin.rpartition(".")
    if not separator or number not in {"1", "2"}:
        raise ValueError(f"Unsupported synthetic RS-485 bus-line pin: {selected_pin}")
    first_pin = f"{reference}.1"
    second_pin = f"{reference}.2"
    if selected_pin not in {first_pin, second_pin}:
        raise ValueError(f"Unsupported synthetic RS-485 bus-line pin: {selected_pin}")

    is_connector = reference.upper().startswith(("J", "P", "X", "CN"))
    if symbol is None:
        symbol = "Connector:Conn_01x02" if is_connector else "Synthetic:Rs485Transceiver"
    if identity is None:
        identity = "RS-485 connector" if is_connector else "RS-485 transceiver"
    footprint = "Synthetic:Conn_01x02" if is_connector else "Synthetic:IC"

    functions = {first_pin: "A", second_pin: "B"}
    functions[selected_pin] = function
    nets = {"RS485_A": (first_pin,), "RS485_B": (second_pin,)}
    nets.pop("RS485_A" if selected_pin == first_pin else "RS485_B")
    nets[rail_name] = (selected_pin,)
    return NetlistContract(
        components={reference: ComponentContract(value=identity, footprint=footprint)},
        nets=nets,
        dnp_components=(reference,) if dnp else (),
        component_symbols={reference: symbol},
        pin_functions=functions,
        component_pin_numbers={reference: ("1", "2")},
    )
