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


def can_connector_signal_on_named_rail_netlist(
    *, rail_name: str = "GND", pin: str = "J1.1"
) -> NetlistContract:
    """Assign one exact CAN/FDCAN connector function to a named rail."""
    pin_functions = {"J1.1": "CAN2_TX", "J1.2": "CAN2_RX"}
    if pin not in pin_functions:
        raise ValueError(f"Unsupported synthetic CAN connector pin: {pin}")
    signal_net = pin_functions[pin]
    nets = {name: (other_pin,) for other_pin, name in pin_functions.items() if name != signal_net}
    nets[rail_name] = (pin,)
    return NetlistContract(
        components={
            "J1": ComponentContract(
                value="Synthetic CAN connector", footprint="Synthetic:Conn_01x02"
            )
        },
        nets=nets,
        component_symbols={"J1": "Connector_Generic:Conn_01x02"},
        pin_functions=pin_functions,
        component_pin_numbers={"J1": ("1", "2")},
    )


def can_module_connector_named_rail_netlist(
    *,
    value: str = "CAN transceiver module",
    functions: tuple[str, str] = ("TXD", "RXD"),
    rails: tuple[str, str] = ("GND", "+3V3"),
    dnp: bool = False,
    inventory: tuple[str, ...] = ("1", "2"),
) -> NetlistContract:
    """Assign generic module TXD/RXD functions to independently named rails."""
    return NetlistContract(
        components={"J1": ComponentContract(value=value, footprint="Synthetic:Conn_01x02")},
        nets={rails[0]: ("J1.1",), rails[1]: ("J1.2",)},
        component_symbols={"J1": "Connector_Generic:Conn_01x02"},
        pin_functions={"J1.1": functions[0], "J1.2": functions[1]},
        component_pin_numbers={"J1": inventory},
        dnp_components=("J1",) if dnp else (),
    )
