"""Synthetic Ethernet data-pin assignments for named-rail review."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def ethernet_signal_on_named_rail_netlist(
    *, rail_name: str = "GND", pin: str = "U1.1", function: str | None = None
) -> NetlistContract:
    """Assign one IC or connector Ethernet data function to a rail-like label."""
    reference, separator, number = pin.rpartition(".")
    if not separator or number not in {"1", "2", "3", "4"} or reference.upper() not in {"U1", "J1"}:
        raise ValueError(f"Unsupported synthetic Ethernet pin: {pin}")
    functions = ("TDP", "TDN", "RDP", "RDN")
    pin_functions = {f"{reference}.{index}": value for index, value in enumerate(functions, 1)}
    nets = {
        function: (pin_number,)
        for pin_number, function in pin_functions.items()
        if pin_number != pin
    }
    selected_function = pin_functions[pin] if function is None else function
    pin_functions[pin] = selected_function
    nets[rail_name] = (pin,)
    is_connector = reference.upper().startswith("J")
    return NetlistContract(
        components={
            reference: ComponentContract(
                value="Synthetic Ethernet connector" if is_connector else "Synthetic Ethernet PHY",
                footprint="Synthetic:RJ45" if is_connector else "Synthetic:QFN",
            )
        },
        nets=nets,
        component_symbols={
            reference: "Connector:Conn_01x04" if is_connector else "Synthetic:Ethernet_PHY"
        },
        pin_functions=pin_functions,
        component_pin_numbers={reference: ("1", "2", "3", "4")},
    )
