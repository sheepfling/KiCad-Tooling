"""Synthetic generic connector assignments on native Ethernet PHY pairs."""

from __future__ import annotations

from collections.abc import Mapping

from kicad_tooling.hwrepo.netlist_contract_models import ComponentContract, NetlistContract


def generic_ethernet_connector_netlist(
    *,
    connector_functions: tuple[str, ...] = ("Pin_1", "Pin_2", "Pin_3", "Pin_4", "Pin_5"),
    endpoint_functions: tuple[str, ...] = ("TDP", "TDN", "RDP", "RDN"),
    connector_assignments: Mapping[str, str] | None = None,
    endpoint_assignments: Mapping[str, str] | None = None,
    dnp: tuple[str, ...] = (),
) -> NetlistContract:
    """Return complete synthetic connector and Ethernet PHY pin evidence."""
    connector_nets = connector_assignments or {
        "1": "ETH_TX_P",
        "2": "ETH_TX_N",
        "3": "ETH_RX_P",
        "4": "ETH_RX_N",
        "5": "BOARD_GND",
    }
    phy_nets = endpoint_assignments or {
        "1": "ETH_TX_P",
        "2": "ETH_TX_N",
        "3": "ETH_RX_P",
        "4": "ETH_RX_N",
    }
    nets: dict[str, list[str]] = {}
    for number, net in connector_nets.items():
        nets.setdefault(net, []).append(f"J1.{number}")
    for number, net in phy_nets.items():
        nets.setdefault(net, []).append(f"U1.{number}")

    return NetlistContract(
        components={
            "J1": ComponentContract(
                value="Synthetic generic connector", footprint="Synthetic:Conn_01x05"
            ),
            "U1": ComponentContract(value="Synthetic Ethernet PHY", footprint="Synthetic:QFN"),
        },
        nets={net: tuple(pins) for net, pins in nets.items()},
        dnp_components=dnp,
        component_symbols={
            "J1": "Connector_Generic:Conn_01x05",
            "U1": "Synthetic:EthernetPhy",
        },
        pin_functions={
            **{f"J1.{index + 1}": function for index, function in enumerate(connector_functions)},
            **{f"U1.{index + 1}": function for index, function in enumerate(endpoint_functions)},
        },
        pin_electrical_types={
            **{f"J1.{number}": "passive" for number in range(1, 6)},
            **{f"U1.{number}": "passive" for number in range(1, 5)},
        },
        component_pin_numbers={"J1": ("1", "2", "3", "4", "5"), "U1": ("1", "2", "3", "4")},
    )
