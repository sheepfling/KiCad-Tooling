"""Synthetic SPI pin-assignment cases for open data-pin review coverage."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def spi_unconnected_data_netlist(
    *,
    open_pins: tuple[str, ...] = ("U1.1",),
    dnp_components: tuple[str, ...] = (),
    functions: dict[str, str] | None = None,
) -> NetlistContract:
    """Build a synthetic two-endpoint SPI data channel with configurable opens."""
    pin_functions = functions or {
        "U1.1": "MOSI",
        "U1.2": "MISO",
        "U2.1": "COPI",
        "U2.2": "CIPO",
    }
    assignments = {
        "SPI_MOSI": ("U1.1", "U2.1"),
        "SPI_MISO": ("U1.2", "U2.2"),
    }
    open_keys = {pin.casefold() for pin in open_pins}
    nets = {
        net: tuple(pin for pin in pins if pin.casefold() not in open_keys)
        for net, pins in assignments.items()
    }
    nets = {net: pins for net, pins in nets.items() if pins}
    return NetlistContract(
        components={
            "U1": ComponentContract(value="Synthetic SPI controller", footprint="Synthetic:QFN"),
            "U2": ComponentContract(value="Synthetic SPI device", footprint="Synthetic:QFN"),
        },
        nets=nets,
        unconnected_nets={"unconnected": tuple(sorted(open_pins))},
        dnp_components=dnp_components,
        component_symbols={
            "U1": "Synthetic:SpiController",
            "U2": "Synthetic:SpiDevice",
        },
        pin_functions=pin_functions,
        component_pin_numbers={"U1": ("1", "2"), "U2": ("1", "2")},
    )
