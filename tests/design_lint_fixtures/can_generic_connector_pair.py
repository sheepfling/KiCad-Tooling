"""Synthetic generic connector assignments on a native CANH/CANL pair."""

from __future__ import annotations

from kicad_tooling.hwrepo.netlist_contract_models import ComponentContract, NetlistContract


def generic_can_connector_pair_netlist(
    *,
    connector_functions: tuple[str, ...] = ("Pin_1", "Pin_2", "Pin_3", "Pin_4"),
    include_canl_contact: bool = True,
) -> NetlistContract:
    """Return a fully inventoried synthetic connector and CAN endpoint."""
    nets = {
        "CAN_H": ("J1.2", "U1.1"),
        "CAN_L": ("U1.2", *(("J1.3",) if include_canl_contact else ())),
        "BOARD_GND": ("J1.4", "U1.3"),
        "+3V3": ("J1.1", "U1.4"),
    }
    return NetlistContract(
        components={
            "J1": ComponentContract(
                value="Synthetic generic connector", footprint="Synthetic:Conn_01x04"
            ),
            "U1": ComponentContract(value="Synthetic CAN transceiver", footprint="Synthetic:SOIC"),
        },
        nets=nets,
        component_symbols={
            "J1": "Connector_Generic:Conn_01x04",
            "U1": "Synthetic:CanTransceiver",
        },
        pin_functions={
            **{f"J1.{index + 1}": function for index, function in enumerate(connector_functions)},
            "U1.1": "CANH",
            "U1.2": "CANL",
            "U1.3": "VSS",
            "U1.4": "VDD",
        },
        pin_electrical_types={
            "J1.1": "passive",
            "J1.2": "passive",
            "J1.3": "passive",
            "J1.4": "passive",
            "U1.1": "bidirectional",
            "U1.2": "bidirectional",
            "U1.3": "power_in",
            "U1.4": "power_in",
        },
        component_pin_numbers={"J1": ("1", "2", "3", "4"), "U1": ("1", "2", "3", "4")},
    )


def can_connector_return_netlist(
    *,
    with_return_contact: bool = False,
    connector_functions: tuple[str, ...] | None = None,
    include_canl_contact: bool = True,
) -> NetlistContract:
    """Return a synthetic two-line CAN connector, optionally with a return contact."""
    numbers = ("1", "2", "3") if with_return_contact else ("1", "2")
    functions = (
        (("Pin_1", "Pin_2", "GND") if with_return_contact else ("Pin_1", "Pin_2"))
        if connector_functions is None
        else connector_functions
    )
    if len(functions) != len(numbers):
        raise ValueError("CAN connector fixture functions must match the pin inventory")

    connector_l = "J1.2"
    connector_l_net = "CAN_L" if include_canl_contact else "UNRELATED"
    nets = {
        "CAN_H": ("J1.1", "U1.1"),
        "CAN_L": ("U1.2", *((connector_l,) if include_canl_contact else ())),
        "BOARD_GND": (("J1.3",) if with_return_contact else ()) + ("U1.3",),
        "+5V": ("U1.4",),
    }
    if not include_canl_contact:
        nets[connector_l_net] = (connector_l,)

    connector_pin_types = {f"J1.{number}": "passive" for number in numbers}
    return NetlistContract(
        components={
            "J1": ComponentContract(
                value="Synthetic two-line CAN connector",
                footprint="Synthetic:Conn_01x02"
                if not with_return_contact
                else "Synthetic:Conn_01x03",
            ),
            "U1": ComponentContract(value="Synthetic CAN transceiver", footprint="Synthetic:SOIC"),
        },
        nets=nets,
        component_symbols={
            "J1": f"Connector_Generic:Conn_01x{len(numbers):02d}",
            "U1": "Synthetic:CanTransceiver",
        },
        pin_functions={
            **{
                f"J1.{number}": function
                for number, function in zip(numbers, functions, strict=True)
            },
            "U1.1": "CANH",
            "U1.2": "CANL",
            "U1.3": "VSS",
            "U1.4": "VDD",
        },
        pin_electrical_types={
            **connector_pin_types,
            "U1.1": "bidirectional",
            "U1.2": "bidirectional",
            "U1.3": "power_in",
            "U1.4": "power_in",
        },
        component_pin_numbers={"J1": numbers, "U1": ("1", "2", "3", "4")},
    )
