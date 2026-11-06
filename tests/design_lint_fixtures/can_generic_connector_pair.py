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
