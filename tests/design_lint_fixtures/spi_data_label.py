"""Minimal native-netlist contracts for SPI data-label polarity checks."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def spi_data_label_netlist(*, reversed_labels: bool = False) -> NetlistContract:
    """Create a two-pin MOSI/MISO control or crossed-label fault."""
    mosi_net, miso_net = ("SPI_MISO", "SPI_MOSI") if reversed_labels else ("SPI_MOSI", "SPI_MISO")
    return NetlistContract(
        components={
            "U1": ComponentContract(value="Synthetic SPI controller", footprint="Synthetic:QFN")
        },
        nets={mosi_net: ("U1.1",), miso_net: ("U1.2",)},
        component_symbols={"U1": "Synthetic:SPI_Controller"},
        pin_functions={"U1.1": "MOSI", "U1.2": "MISO"},
        component_pin_numbers={"U1": ("1", "2")},
    )
