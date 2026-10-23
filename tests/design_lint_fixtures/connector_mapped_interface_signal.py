"""Typed inputs for mapped connector-signal lint regressions."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import NetlistContract


def mapped_interface_signal_netlist(
    *,
    target_net: str | None = None,
    target_function: str = "Pin_2",
    target_type: str = "input",
    dnp: tuple[str, ...] = (),
) -> NetlistContract:
    """Build one reviewed UART connector with a controlled signal assignment."""
    nets = {"UART_TX": ("J1.1",), "SIGNAL_RETURN": ("J1.3",)}
    if target_net is not None:
        nets[target_net] = ("J1.2",)
    return NetlistContract(
        components={},
        nets=nets,
        unconnected_nets={} if target_net is not None else {"unconnected": ("J1.2",)},
        dnp_components=dnp,
        component_symbols={"J1": "Synthetic:GenericUartPort"},
        component_pin_numbers={"J1": ("1", "2", "3")},
        pin_functions={"J1.1": "Pin_1", "J1.2": target_function, "J1.3": "Pin_3"},
        pin_electrical_types={"J1.1": "output", "J1.2": target_type, "J1.3": "passive"},
    )
