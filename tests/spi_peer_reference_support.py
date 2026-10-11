"""Synthetic native-netlist builder for SPI shared-clock reference tests."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def spi_peer_netlist(
    *,
    reference_nets: dict[str, str] | None = None,
    supply_nets: dict[str, str] | None = None,
    clock_nets: dict[str, str] | None = None,
    clock_types: dict[str, str] | None = None,
    symbols: dict[str, str] | None = None,
    dnp: tuple[str, ...] = (),
    incomplete_reference_types: tuple[str, ...] = (),
    reference_functions: dict[str, str] | None = None,
) -> NetlistContract:
    """Build direct SCK peers with explicit reference-pin inventories."""
    reference_nets = reference_nets or {"U1": "GND_A", "U2": "GND_B"}
    references = tuple(sorted(reference_nets))
    supply_nets = supply_nets or {reference: "+3V3" for reference in references}
    clock_nets = clock_nets or {reference: "SPI_SCK" for reference in references}
    clock_types = clock_types or {
        reference: "output" if index == 0 else "input" for index, reference in enumerate(references)
    }
    symbols = symbols or {
        reference: f"Synthetic:SPIEndpoint{index}"
        for index, reference in enumerate(references, start=1)
    }
    reference_functions = reference_functions or {}

    components = {
        reference: ComponentContract(value="Synthetic SPI endpoint", footprint="Synthetic:SOIC")
        for reference in references
    }
    nets: dict[str, list[str]] = {}
    pin_functions: dict[str, str] = {}
    pin_electrical_types: dict[str, str] = {}
    for reference in references:
        clock_pin = f"{reference}.1"
        data_pin = f"{reference}.2"
        reference_pin = f"{reference}.3"
        supply_pin = f"{reference}.4"
        pin_functions[clock_pin] = "SPI1_SCK"
        pin_functions[data_pin] = "MOSI"
        pin_functions[reference_pin] = reference_functions.get(reference, "GND")
        pin_functions[supply_pin] = "VDD"
        pin_electrical_types[clock_pin] = clock_types[reference]
        pin_electrical_types[data_pin] = "output" if clock_types[reference] == "output" else "input"
        pin_electrical_types[reference_pin] = "power_in"
        pin_electrical_types[supply_pin] = "power_in"
        nets.setdefault(clock_nets[reference], []).append(clock_pin)
        nets.setdefault("SPI_MOSI", []).append(data_pin)
        nets.setdefault(reference_nets[reference], []).append(reference_pin)
        nets.setdefault(supply_nets[reference], []).append(supply_pin)
    for reference in incomplete_reference_types:
        pin_electrical_types.pop(f"{reference}.3", None)

    return NetlistContract(
        components=components,
        component_symbols=symbols,
        component_pin_numbers={reference: ("1", "2", "3", "4") for reference in references},
        pin_functions=pin_functions,
        pin_electrical_types=pin_electrical_types,
        nets={net: tuple(pins) for net, pins in nets.items()},
        dnp_components=dnp,
    )
