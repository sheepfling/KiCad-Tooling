"""Synthetic CAN controller signal assignments for named-rail review."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def can_signal_on_named_rail_netlist(
    *, rail_name: str = "GND", pin: str = "U1.1"
) -> NetlistContract:
    """Assign one exact CAN/FDCAN controller function to a rail-like label."""
    pin_functions = {"U1.1": "CAN1_TX", "U1.2": "CAN1_RX"}
    if pin not in pin_functions:
        raise ValueError(f"Unsupported synthetic CAN pin: {pin}")
    signal_net = pin_functions[pin]
    nets = {
        name: members
        for name, members in {"CAN1_TX": ("U1.1",), "CAN1_RX": ("U1.2",)}.items()
        if name != signal_net
    }
    nets[rail_name] = (pin,)
    return NetlistContract(
        components={
            "U1": ComponentContract(value="Synthetic CAN controller", footprint="Synthetic:QFN")
        },
        nets=nets,
        component_symbols={"U1": "Synthetic:CAN_Controller"},
        pin_functions=pin_functions,
        component_pin_numbers={"U1": ("1", "2")},
    )
