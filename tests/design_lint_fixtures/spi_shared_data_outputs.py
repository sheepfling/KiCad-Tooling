"""Minimal synthetic netlists for shared SPI data-output review."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def spi_shared_data_output_netlist(*, shared: bool = True) -> NetlistContract:
    """Build an SPI controller and two fitted data-output endpoints."""
    nets = (
        {"SPI_MISO": ("U1.1", "U2.1", "U3.1")}
        if shared
        else {
            "SPI_MISO": ("U1.1", "U2.1"),
            "SPI_MISO_ALT": ("U3.1",),
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
        pin_functions={"U1.1": "MISO", "U2.1": "MISO", "U3.1": "SPI2_SDO"},
        pin_electrical_types={"U1.1": "input", "U2.1": "passive", "U3.1": "tri_state"},
        component_pin_numbers={"U1": ("1",), "U2": ("1",), "U3": ("1",)},
    )
