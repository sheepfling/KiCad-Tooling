"""Synthetic CAN bus-line assignments for named-rail review tests."""

from __future__ import annotations

from collections.abc import Sequence

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def can_line_named_rail_netlist(
    *,
    reference: str = "U1",
    high_net: str = "GND",
    low_net: str = "CANL_BUS",
    high_function: str = "CANH",
    low_function: str = "CANL",
    inventory: Sequence[str] = ("1", "2"),
    dnp: bool = False,
) -> NetlistContract:
    """Return one synthetic IC or connector exposing a CANH/CANL pair."""
    high_pin = f"{reference}.1"
    low_pin = f"{reference}.2"
    nets: dict[str, tuple[str, ...]] = {}
    nets[high_net] = (high_pin,)
    nets[low_net] = (*nets[low_net], low_pin) if low_net in nets else (low_pin,)
    is_connector = reference.upper().startswith(("J", "P", "X", "CN"))
    footprint = "Synthetic:Conn_01x02" if is_connector else "Synthetic:QFN"
    return NetlistContract(
        components={
            reference: ComponentContract(value="Synthetic CAN endpoint", footprint=footprint)
        },
        nets=nets,
        component_symbols={reference: "Synthetic:CAN_Endpoint"},
        pin_functions={high_pin: high_function, low_pin: low_function},
        component_pin_numbers={reference: tuple(inventory)},
        dnp_components=(reference,) if dnp else (),
    )
