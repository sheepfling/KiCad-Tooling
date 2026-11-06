"""Synthetic generic connector contacts on a native SPI clock/data triad."""

from __future__ import annotations

from kicad_tooling.hwrepo.netlist_contract_models import ComponentContract, NetlistContract


def generic_spi_connector_triad_netlist(
    *,
    connector_functions: tuple[str, ...] = ("Pin_1", "Pin_2", "Pin_3", "Pin_4"),
    include_data_output_contact: bool = True,
) -> NetlistContract:
    """Return a completely inventoried synthetic connector and SPI endpoint."""
    nets = {
        "SPI_SCK": ("J1.1", "U1.1"),
        "SPI_MOSI": ("J1.2", "U1.2"),
        "SPI_MISO": ("U1.3", *(('J1.3',) if include_data_output_contact else ())),
        "BOARD_GND": ("J1.4", "U1.4"),
        "+3V3": ("U1.5",),
    }
    return NetlistContract(
        components={
            "J1": ComponentContract(
                value="Synthetic generic connector", footprint="Synthetic:Conn_01x04"
            ),
            "U1": ComponentContract(value="Synthetic SPI endpoint", footprint="Synthetic:SOIC"),
        },
        nets=nets,
        component_symbols={
            "J1": "Synthetic:GenericConnector",
            "U1": "Synthetic:SpiEndpoint",
        },
        pin_functions={
            **{f"J1.{index + 1}": function for index, function in enumerate(connector_functions)},
            "U1.1": "SCK",
            "U1.2": "MOSI",
            "U1.3": "MISO",
            "U1.4": "VSS",
            "U1.5": "VDD",
        },
        pin_electrical_types={
            **{f"J1.{index + 1}": "passive" for index in range(4)},
            "U1.1": "input",
            "U1.2": "output",
            "U1.3": "input",
            "U1.4": "power_in",
            "U1.5": "power_in",
        },
        component_pin_numbers={"J1": ("1", "2", "3", "4"), "U1": ("1", "2", "3", "4", "5")},
    )
