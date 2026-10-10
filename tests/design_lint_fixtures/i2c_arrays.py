"""Synthetic resistor-array inputs for I2C pull-up checks."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import (
    ComponentContract,
    I2cPullupAnalysis,
    I2cPullupArrayChannelRequirement,
    I2cPullupArrayRequirement,
    I2cPullupBusRequirement,
    I2cPullupLineRequirement,
    NetlistContract,
)


def array_netlist(
    *,
    symbol: str = "Synthetic:ResistorArray",
    dnp: tuple[str, ...] = (),
    swapped_sda_channel: bool = False,
    wrong_sda_net: bool = False,
) -> NetlistContract:
    sda_assignments = ("RN1.2", "RN1.1") if swapped_sda_channel else ("RN1.1", "RN1.2")
    return NetlistContract(
        components={"RN1": ComponentContract(value="4x4.7k", footprint="Synthetic:RA4")},
        nets={
            "I2C_SDA": ("U1.1",) if wrong_sda_net else ("U1.1", sda_assignments[0]),
            "I2C_SCL": ("U1.2", "RN1.3", sda_assignments[0])
            if wrong_sda_net
            else ("U1.2", "RN1.3"),
            "+3V3": (sda_assignments[1], "RN1.4"),
        },
        dnp_components=dnp,
        component_symbols={"U1": "Synthetic:I2cTarget", "RN1": symbol},
        pin_functions={"U1.1": "SDA", "U1.2": "SCL"},
        component_pin_numbers={"U1": ("1", "2"), "RN1": ("1", "2", "3", "4")},
    )


def array_requirement() -> I2cPullupAnalysis:
    return I2cPullupAnalysis(
        basis="Synthetic datasheet pin map and bus resistance requirement",
        buses=(
            I2cPullupBusRequirement(
                id="main",
                basis="Synthetic two-wire interface requirement",
                sda=I2cPullupLineRequirement(
                    net="I2C_SDA", rail="+3V3", minimum_ohms=1_000, maximum_ohms=100_000
                ),
                scl=I2cPullupLineRequirement(
                    net="I2C_SCL", rail="+3V3", minimum_ohms=1_000, maximum_ohms=100_000
                ),
            ),
        ),
        arrays=(
            I2cPullupArrayRequirement(
                reference="RN1",
                expected_symbol="Synthetic:ResistorArray",
                expected_footprint="Synthetic:RA4",
                expected_value="4x4.7k",
                basis="Synthetic array datasheet and pin map",
                channels=(
                    I2cPullupArrayChannelRequirement(
                        id="sda",
                        signal_pin="RN1.1",
                        rail_pin="RN1.2",
                        signal_net="I2C_SDA",
                        rail_net="+3V3",
                        resistance_ohms=4_700,
                        basis="Synthetic array channel 1 map",
                    ),
                    I2cPullupArrayChannelRequirement(
                        id="scl",
                        signal_pin="RN1.3",
                        rail_pin="RN1.4",
                        signal_net="I2C_SCL",
                        rail_net="+3V3",
                        resistance_ohms=4_700,
                        basis="Synthetic array channel 2 map",
                    ),
                ),
            ),
        ),
    )
