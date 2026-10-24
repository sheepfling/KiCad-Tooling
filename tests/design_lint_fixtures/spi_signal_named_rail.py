"""Synthetic SPI signal assignments for named-rail review checks."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def spi_signal_on_named_rail_netlist(
    *, rail_name: str = "GND", pin: str = "U1.1"
) -> NetlistContract:
    """Assign one exact SPI pin function to a named-rail label."""
    components = {"U1": ComponentContract(value="Synthetic SPI device", footprint="Synthetic:QFN")}
    pin_functions = {
        "U1.1": "SPI1_SCK",
        "U1.2": "SPI1_MOSI",
        "U1.3": "SPI1_MISO",
        "U1.4": "SPI1_NSS",
    }
    nets: dict[str, tuple[str, ...]] = {
        "SPI1_SCK": ("U1.1",),
        "SPI1_MOSI": ("U1.2",),
        "SPI1_MISO": ("U1.3",),
        "SPI1_CS": ("U1.4",),
    }
    if pin not in pin_functions:
        raise ValueError(f"Unsupported synthetic SPI pin: {pin}")
    nets = {
        net: members
        for net, members in (
            (net, tuple(member for member in members if member != pin))
            for net, members in nets.items()
        )
        if members
    }
    nets[rail_name] = tuple(sorted((*nets.get(rail_name, ()), pin)))
    return NetlistContract(
        components=components,
        nets=nets,
        component_symbols={"U1": "Synthetic:SPI_Device"},
        pin_functions=pin_functions,
        component_pin_numbers={"U1": tuple(pin.rsplit(".", 1)[-1] for pin in pin_functions)},
    )
