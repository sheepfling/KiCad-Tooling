"""Minimal synthetic native-netlist cases for shared SPI chip selects."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def spi_shared_chip_select_netlist(*, shared: bool = True) -> NetlistContract:
    """Build two fitted SPI select inputs with one driver and selectable topology."""
    nets = (
        {"SPI_CS0": ("U1.1", "U2.1", "U3.1")}
        if shared
        else {
            "SPI_CS0": ("U1.1", "U2.1"),
            "SPI_CS1": ("U1.2", "U3.1"),
        }
    )
    return NetlistContract(
        components={
            reference: ComponentContract(value=f"Synthetic {reference}", footprint="Synthetic:IC")
            for reference in ("U1", "U2", "U3")
        },
        nets=nets,
        dnp_components=(),
        component_symbols={
            "U1": "Synthetic:SPI_Controller",
            "U2": "Synthetic:SPI_Device",
            "U3": "Synthetic:SPI_Device",
        },
        pin_functions={
            "U1.1": "SPI1_NSS",
            "U1.2": "SPI2_NSS",
            "U2.1": "CS_N",
            "U3.1": "NSS",
        },
        pin_electrical_types={
            "U1.1": "output",
            "U1.2": "output",
            "U2.1": "input",
            "U3.1": "input",
        },
        component_pin_numbers={"U1": ("1", "2"), "U2": ("1",), "U3": ("1",)},
    )
