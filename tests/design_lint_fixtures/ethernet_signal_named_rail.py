"""Synthetic Ethernet data-pin assignments for named-rail review."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def ethernet_signal_on_named_rail_netlist(
    *, rail_name: str = "GND", pin: str = "U1.1"
) -> NetlistContract:
    """Assign one exact Ethernet data-pair pin function to a rail-like label."""
    pin_functions = {"U1.1": "TDP", "U1.2": "TDN", "U1.3": "RDP", "U1.4": "RDN"}
    if pin not in pin_functions:
        raise ValueError(f"Unsupported synthetic Ethernet pin: {pin}")
    nets = {
        function: (pin_number,)
        for pin_number, function in pin_functions.items()
        if pin_number != pin
    }
    nets[rail_name] = (pin,)
    return NetlistContract(
        components={
            "U1": ComponentContract(value="Synthetic Ethernet PHY", footprint="Synthetic:QFN")
        },
        nets=nets,
        component_symbols={"U1": "Synthetic:Ethernet_PHY"},
        pin_functions=pin_functions,
        component_pin_numbers={"U1": ("1", "2", "3", "4")},
    )
