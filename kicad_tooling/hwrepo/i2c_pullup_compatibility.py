"""Legacy I2C pull-up results projected from the typed heuristic service."""

from __future__ import annotations

from dataclasses import dataclass

from .i2c_pullup_contract import i2c_pullup_checks
from .i2c_pullup_heuristics import (
    I2cLowEquivalentResistanceObservation,
    I2cMultiplePullupRailFamilies,
    I2cPullupGap,
    i2c_buses_with_multiple_pullup_rail_families,
    i2c_buses_without_local_pullups,
    i2c_pullup_heuristic_coverage,
)
from .i2c_pullup_heuristics import (
    i2c_buses_with_low_equivalent_pullup_resistance as _scan_low_equivalent_resistance,
)
from .netlist_contract_models import NetlistContract

__all__ = (
    "I2cLowEquivalentResistance",
    "I2cMultiplePullupRailFamilies",
    "I2cPullupGap",
    "i2c_buses_with_low_equivalent_pullup_resistance",
    "i2c_buses_with_multiple_pullup_rail_families",
    "i2c_buses_without_local_pullups",
    "i2c_pullup_checks",
    "i2c_pullup_heuristic_coverage",
)


@dataclass(frozen=True, slots=True)
class I2cLowEquivalentResistance:
    """Map-shaped result retained for callers of the bus-heuristics facade."""

    sda_net: str
    scl_net: str
    lines: tuple[str, ...]
    pins: dict[str, tuple[str, ...]]
    resistors: dict[str, tuple[str, ...]]
    equivalent_ohms: dict[str, str]


def i2c_buses_with_low_equivalent_pullup_resistance(
    observed: NetlistContract,
) -> tuple[I2cLowEquivalentResistance, ...]:
    """Adapt the typed scan to its established map-shaped return record."""
    observations: tuple[I2cLowEquivalentResistanceObservation, ...] = (
        _scan_low_equivalent_resistance(observed)
    )
    return tuple(
        I2cLowEquivalentResistance(
            sda_net=item.sda_net,
            scl_net=item.scl_net,
            lines=tuple(line.line for line in item.lines),
            pins={"SDA": item.sda_pins, "SCL": item.scl_pins},
            resistors={
                line.line: tuple(
                    f"{' + '.join(path.references)}={path.resistance_ohms:.6g}Ω to {path.rail_net}"
                    for path in line.pullup_paths
                )
                for line in item.lines
            },
            equivalent_ohms={
                line.line: f"{line.equivalent_resistance_ohms:.6g}" for line in item.lines
            },
        )
        for item in observations
    )
