"""Synthetic generic connector assignments on native JTAG endpoint nets."""

from __future__ import annotations

from collections.abc import Mapping

from kicad_tooling.hwrepo.netlist_contract_models import ComponentContract, NetlistContract


def generic_jtag_connector_netlist(
    *,
    connector_functions: tuple[str, ...] = ("Pin_1", "Pin_2", "Pin_3", "Pin_4", "GND"),
    endpoint_functions: tuple[str, ...] = ("GPIO_1", "GPIO_2", "GPIO_3", "GPIO_4", "TCK", "TMS"),
    connector_assignments: Mapping[str, str] | None = None,
    endpoint_assignments: Mapping[str, str] | None = None,
    dnp: tuple[str, ...] = (),
) -> NetlistContract:
    """Return complete synthetic connector and fitted-IC pin evidence."""
    connector_nets = connector_assignments or {
        "1": "JTAG_CLOCK",
        "2": "JTAG_MODE",
        "3": "PORT_AUX_3",
        "4": "PORT_AUX_4",
        "5": "BOARD_GND",
    }
    endpoint_nets = endpoint_assignments or {
        "1": "GPIO_1",
        "2": "GPIO_2",
        "3": "GPIO_3",
        "4": "GPIO_4",
        "5": "JTAG_CLOCK",
        "6": "JTAG_MODE",
    }
    nets: dict[str, list[str]] = {}
    for number, net in connector_nets.items():
        nets.setdefault(net, []).append(f"J1.{number}")
    for number, net in endpoint_nets.items():
        nets.setdefault(net, []).append(f"U1.{number}")

    return NetlistContract(
        components={
            "J1": ComponentContract(
                value="Synthetic generic connector", footprint="Synthetic:Conn_01x05"
            ),
            "U1": ComponentContract(value="Synthetic boundary-scan IC", footprint="Synthetic:QFN"),
        },
        nets={net: tuple(pins) for net, pins in nets.items()},
        dnp_components=dnp,
        component_symbols={
            "J1": "Connector_Generic:Conn_01x05",
            "U1": "Synthetic:JtagEndpoint",
        },
        pin_functions={
            **{f"J1.{index + 1}": function for index, function in enumerate(connector_functions)},
            **{f"U1.{index + 1}": function for index, function in enumerate(endpoint_functions)},
        },
        pin_electrical_types={
            **{f"J1.{number}": "passive" for number in range(1, 6)},
            **{f"U1.{number}": "passive" for number in range(1, 7)},
        },
        component_pin_numbers={
            "J1": ("1", "2", "3", "4", "5"),
            "U1": ("1", "2", "3", "4", "5", "6"),
        },
    )
