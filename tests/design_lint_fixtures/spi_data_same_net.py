"""Minimal synthetic netlists for SPI data input/output same-net review."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def spi_data_same_net_netlist(
    *,
    shared: bool = True,
    input_function: str = "COPI",
    output_function: str = "CIPO",
) -> NetlistContract:
    """Build one fitted IC with native SPI data-input and data-output pins."""
    nets = (
        {"SPI_DATA": ("U1.1", "U1.2")} if shared else {"SPI_COPI": ("U1.1",), "SPI_CIPO": ("U1.2",)}
    )
    return NetlistContract(
        components={
            "U1": ComponentContract(value="Synthetic SPI device", footprint="Synthetic:IC")
        },
        nets=nets,
        dnp_components=(),
        component_symbols={"U1": "Synthetic:SpiDevice"},
        pin_functions={"U1.1": input_function, "U1.2": output_function},
        pin_electrical_types={"U1.1": "input", "U1.2": "tri_state"},
        component_pin_numbers={"U1": ("1", "2")},
    )
