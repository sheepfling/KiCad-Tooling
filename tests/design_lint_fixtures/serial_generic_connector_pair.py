"""Synthetic generic connector contacts on an exact native UART TX/RX pair."""

from __future__ import annotations

from kicad_tooling.hwrepo.netlist_contract_models import ComponentContract, NetlistContract


def generic_serial_connector_pair_netlist(
    *,
    connector_functions: tuple[str, ...] = ("Pin_1", "Pin_2", "GND", "3V3"),
    include_rx_contact: bool = True,
) -> NetlistContract:
    """Return a completely inventoried connector and fitted UART endpoint."""
    nets = {
        "LINE_A": ("J1.1", "U1.1"),
        "LINE_B": ("U1.2", *(("J1.2",) if include_rx_contact else ())),
        "BOARD_GND": ("J1.3", "U1.3"),
        "+3V3": ("U1.4", "J1.4"),
    }
    return NetlistContract(
        components={
            "J1": ComponentContract(
                value="Synthetic generic serial connector", footprint="Synthetic:Conn_01x04"
            ),
            "U1": ComponentContract(value="Synthetic UART endpoint", footprint="Synthetic:SOIC"),
        },
        nets=nets,
        component_symbols={
            "J1": "Connector_Generic:Conn_01x04",
            "U1": "Synthetic:UartEndpoint",
        },
        pin_functions={
            **{f"J1.{index + 1}": function for index, function in enumerate(connector_functions)},
            "U1.1": "TXD",
            "U1.2": "RXD",
            "U1.3": "VSS",
            "U1.4": "VDD",
        },
        pin_electrical_types={
            **{f"J1.{index + 1}": "passive" for index in range(4)},
            "U1.1": "output",
            "U1.2": "input",
            "U1.3": "power_in",
            "U1.4": "power_in",
        },
        component_pin_numbers={"J1": ("1", "2", "3", "4"), "U1": ("1", "2", "3", "4")},
    )
