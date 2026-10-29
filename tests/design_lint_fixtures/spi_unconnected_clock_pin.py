"""Synthetic SPI clock-open cases."""

from __future__ import annotations

from collections.abc import Mapping

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def spi_unconnected_clock_netlist(
    *,
    open_pins: tuple[str, ...] = (),
    dnp_components: tuple[str, ...] = (),
    functions: Mapping[str, str] | None = None,
) -> NetlistContract:
    pin_functions = functions or {
        "U1.1": "SCK",
        "U1.2": "MOSI",
        "U2.1": "SCK",
        "U2.2": "MISO",
    }
    assignments = {
        "SPI_CLK": ("U1.1", "U2.1"),
        "SPI_MOSI": ("U1.2",),
        "SPI_MISO": ("U2.2",),
    }
    open_keys = {pin.casefold() for pin in open_pins}
    nets = {
        net: tuple(pin for pin in pins if pin.casefold() not in open_keys)
        for net, pins in assignments.items()
    }
    return NetlistContract(
        components={
            "U1": ComponentContract(value="Synthetic SPI controller", footprint="Synthetic:QFN"),
            "U2": ComponentContract(value="Synthetic SPI device", footprint="Synthetic:QFN"),
        },
        nets={net: pins for net, pins in nets.items() if pins},
        unconnected_nets={"unconnected": tuple(sorted(open_pins))},
        dnp_components=dnp_components,
        component_symbols={"U1": "Synthetic:SpiController", "U2": "Synthetic:SpiDevice"},
        pin_functions=pin_functions,
        component_pin_numbers={"U1": ("1", "2"), "U2": ("1", "2")},
    )
