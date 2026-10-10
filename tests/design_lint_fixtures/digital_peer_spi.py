"""Synthetic SPI peer-voltage netlists used by hosted-lane regressions."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def participant_netlist() -> NetlistContract:
    return NetlistContract(
        components={
            "U1": ComponentContract(value="Synthetic SPI node", footprint="Synthetic:QFN"),
            "U2": ComponentContract(value="Synthetic SPI node", footprint="Synthetic:QFN"),
        },
        nets={
            "SPI_SCK": ("U1.1", "U2.1"),
            "SPI_MOSI": ("U1.2", "U2.2"),
            "SPI_MISO": ("U1.3", "U2.3"),
            "SPI_CS": ("U1.4", "U2.4"),
        },
        component_symbols={"U1": "Synthetic:SPI_Node", "U2": "Synthetic:SPI_Node"},
        pin_functions={
            "U1.1": "SPI1_SCLK",
            "U1.2": "SPI1_COPI",
            "U1.3": "SPI1_CIPO",
            "U1.4": "SPI1_NSS",
            "U2.1": "SPI1_SCLK",
            "U2.2": "SPI1_COPI",
            "U2.3": "SPI1_CIPO",
            "U2.4": "SPI1_NSS",
        },
        component_pin_numbers={"U1": ("1", "2", "3", "4"), "U2": ("1", "2", "3", "4")},
    )


def peer_netlist(*, split_supplies: bool) -> NetlistContract:
    nets = {
        "SPI_SCK": ("U1.1", "U2.1"),
        "+3V3": ("U2.2",) if split_supplies else ("U1.2", "U2.2"),
    }
    if split_supplies:
        nets["+5V"] = ("U1.2",)
    return NetlistContract(
        components={
            "U1": ComponentContract(value="Synthetic SPI controller", footprint="Synthetic:QFN-2"),
            "U2": ComponentContract(value="Synthetic SPI peripheral", footprint="Synthetic:QFN-2"),
        },
        nets=nets,
        component_symbols={
            "U1": "Synthetic:SPI_Controller",
            "U2": "Synthetic:SPI_Peripheral",
        },
        pin_functions={
            "U1.1": "SPI1_SCLK",
            "U1.2": "VDD",
            "U2.1": "SPI1_SCLK",
            "U2.2": "VDD",
        },
        pin_electrical_types={
            "U1.1": "output",
            "U1.2": "power_in",
            "U2.1": "input",
            "U2.2": "power_in",
        },
        component_pin_numbers={"U1": ("1", "2"), "U2": ("1", "2")},
    )


def translator_peer_netlist() -> NetlistContract:
    """Mirror the native synthetic control with separate translator-side nets."""
    return NetlistContract(
        components={
            "U1": ComponentContract(value="Synthetic SPI controller", footprint="Synthetic:QFN-3"),
            "U2": ComponentContract(value="Synthetic SPI peripheral", footprint="Synthetic:QFN-3"),
            "U3": ComponentContract(
                value="Synthetic SPI level translator", footprint="Synthetic:Translator-5"
            ),
        },
        nets={
            "+5V": ("U1.2", "U3.3"),
            "+3V3": ("U2.2", "U3.4"),
            "GND": ("U1.3", "U2.3", "U3.5"),
            "SPI_A_SIDE": ("U1.1", "U3.1"),
            "SPI_B_SIDE": ("U2.1", "U3.2"),
        },
        component_symbols={
            "U1": "Synthetic:SPI_Controller",
            "U2": "Synthetic:SPI_Peripheral",
            "U3": "Synthetic:SPI_LevelTranslator",
        },
        pin_functions={
            "U1.1": "SPI1_SCLK",
            "U1.2": "VDD",
            "U1.3": "GND",
            "U2.1": "SPI1_SCLK",
            "U2.2": "VDD",
            "U2.3": "GND",
            "U3.1": "A_SCLK",
            "U3.2": "B_SCLK",
            "U3.3": "VCCA",
            "U3.4": "VCCB",
            "U3.5": "GND",
        },
        pin_electrical_types={
            "U1.1": "output",
            "U1.2": "power_in",
            "U1.3": "power_in",
            "U2.1": "input",
            "U2.2": "power_in",
            "U2.3": "power_in",
            "U3.1": "input",
            "U3.2": "output",
            "U3.3": "power_in",
            "U3.4": "power_in",
            "U3.5": "power_in",
        },
        component_pin_numbers={
            "U1": ("1", "2", "3"),
            "U2": ("1", "2", "3"),
            "U3": ("1", "2", "3", "4", "5"),
        },
    )
