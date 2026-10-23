"""Minimal synthetic netlists for SPI clock/chip-select label mismatch review."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def spi_clock_select_label_netlist(
    *,
    crossed: bool = True,
    dnp: bool = False,
) -> NetlistContract:
    """Build one fitted SPI IC with clock and select roles on separate nets."""
    nets = (
        {"SPI1_CS": ("U1.1",), "SPI1_SCK": ("U1.2",)}
        if crossed
        else {"SPI1_SCK": ("U1.1",), "SPI1_CS": ("U1.2",)}
    )
    return NetlistContract(
        components={
            "U1": ComponentContract(value="Synthetic SPI device", footprint="Synthetic:IC")
        },
        nets=nets,
        dnp_components=("U1",) if dnp else (),
        component_symbols={"U1": "Synthetic:SpiDevice"},
        pin_functions={"U1.1": "SPI1_SCK", "U1.2": "SPI1_NSS"},
        pin_electrical_types={"U1.1": "input", "U1.2": "input"},
        component_pin_numbers={"U1": ("1", "2")},
    )
