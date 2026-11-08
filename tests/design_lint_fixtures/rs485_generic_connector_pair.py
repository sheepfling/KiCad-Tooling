"""Synthetic generic connector assignments on an identified RS-485 A/B pair."""

from __future__ import annotations

from kicad_tooling.hwrepo.netlist_contract_models import ComponentContract, NetlistContract


def generic_rs485_connector_pair_netlist(
    *,
    connector_functions: tuple[str, ...] = ("Pin_1", "Pin_2", "Pin_3", "Pin_4"),
    line_functions: tuple[str, str] = ("A", "B"),
    identity: str = "SN65HVD485 synthetic transceiver",
    endpoint_symbol: str = "Synthetic:SN65HVD485",
    include_b_contact: bool = True,
    connector_dnp: bool = False,
    endpoint_dnp: bool = False,
    unconnected_connector_pins: tuple[str, ...] = (),
) -> NetlistContract:
    """Return a fully inventoried synthetic connector and RS-485 endpoint."""
    disconnected = {pin.casefold() for pin in unconnected_connector_pins}
    nets = {
        "LINE_A": ("J1.1", "U1.1"),
        "LINE_B": ("U1.2", *(("J1.2",) if include_b_contact else ())),
        "BOARD_GND": ("J1.4", "U1.4"),
        "+3V3": ("J1.3", "U1.3"),
    }
    nets = {
        name: tuple(pin for pin in pins if pin.casefold() not in disconnected)
        for name, pins in nets.items()
    }
    return NetlistContract(
        components={
            "J1": ComponentContract(
                value="Synthetic generic connector", footprint="Synthetic:Conn_01x04"
            ),
            "U1": ComponentContract(value=identity, footprint="Synthetic:SOIC"),
        },
        nets=nets,
        dnp_components=tuple(
            reference
            for reference, selected in (("J1", connector_dnp), ("U1", endpoint_dnp))
            if selected
        ),
        component_symbols={
            "J1": "Connector_Generic:Conn_01x04",
            "U1": endpoint_symbol,
        },
        pin_functions={
            **{f"J1.{index + 1}": function for index, function in enumerate(connector_functions)},
            "U1.1": line_functions[0],
            "U1.2": line_functions[1],
            "U1.3": "VCC",
            "U1.4": "GND",
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
