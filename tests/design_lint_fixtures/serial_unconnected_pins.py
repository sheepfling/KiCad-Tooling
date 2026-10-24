"""Synthetic UART function netlists for unassigned-pin review coverage."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def serial_unconnected_netlist(
    *,
    open_pins: tuple[str, ...] = ("J1.1",),
    dnp_components: tuple[str, ...] = (),
    functions: dict[str, str] | None = None,
) -> NetlistContract:
    """Build a two-direction UART endpoint with configurable open contacts."""
    pin_functions = functions or {
        "J1.1": "TX",
        "J1.2": "RX",
        "U1.1": "UART0_RX",
        "U1.2": "UART0_TX",
    }
    assignments = {
        "UART_TX": ("J1.1", "U1.1"),
        "UART_RX": ("J1.2", "U1.2"),
    }
    open_keys = {pin.casefold() for pin in open_pins}
    nets = {
        net: tuple(pin for pin in pins if pin.casefold() not in open_keys)
        for net, pins in assignments.items()
    }
    nets = {net: pins for net, pins in nets.items() if pins}
    return NetlistContract(
        components={
            "J1": ComponentContract(value="Synthetic UART endpoint", footprint="Synthetic:Header"),
            "U1": ComponentContract(value="Synthetic UART peer", footprint="Synthetic:Module"),
        },
        nets=nets,
        unconnected_nets={"unconnected": tuple(sorted(open_pins))},
        dnp_components=dnp_components,
        component_symbols={"J1": "Synthetic:UART_Endpoint", "U1": "Synthetic:UART_Peer"},
        pin_functions=pin_functions,
        component_pin_numbers={"J1": ("1", "2"), "U1": ("1", "2")},
    )
