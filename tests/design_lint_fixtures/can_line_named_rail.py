"""Synthetic CAN bus-line assignments for named-rail review tests."""

from __future__ import annotations

from collections.abc import Sequence

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def can_line_named_rail_netlist(
    *,
    high_net: str = "GND",
    low_net: str = "CANL_BUS",
    high_function: str = "CANH",
    low_function: str = "CANL",
    inventory: Sequence[str] = ("1", "2"),
    dnp: bool = False,
) -> NetlistContract:
    """Return a fitted or DNP synthetic device exposing one CANH/CANL pair."""
    nets: dict[str, tuple[str, ...]] = {}
    nets[high_net] = ("U1.1",)
    nets[low_net] = (*nets[low_net], "U1.2") if low_net in nets else ("U1.2",)
    return NetlistContract(
        components={
            "U1": ComponentContract(value="Synthetic CAN transceiver", footprint="Synthetic:QFN")
        },
        nets=nets,
        component_symbols={"U1": "Synthetic:CAN_Transceiver"},
        pin_functions={"U1.1": high_function, "U1.2": low_function},
        component_pin_numbers={"U1": tuple(inventory)},
        dnp_components=("U1",) if dnp else (),
    )
