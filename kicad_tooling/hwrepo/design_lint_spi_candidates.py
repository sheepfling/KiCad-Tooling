"""Translate SPI chip-select bias observations."""

from __future__ import annotations

from .design_lint_types import Candidate
from .models import NetlistContract
from .spi_bias_heuristics import spi_active_low_chip_selects_without_pullups


def spi_bias_candidates(observed: NetlistContract) -> tuple[Candidate, ...]:
    """Build SPI chip-select bias review prompts."""
    found: list[Candidate] = []
    for gap in spi_active_low_chip_selects_without_pullups(observed):
        found.append(
            Candidate(
                rule_id="bus.spi_active_low_chip_select_without_pullup",
                subject=f"{gap.net}: active-low SPI chip-select bias",
                message=(
                    "This assigned active-low chip-select input has no visible 1 kΩ–100 kΩ "
                    "resistor path to a recognized positive rail. Review the device's reset-time "
                    "state and any internal or off-board bias; the pin name alone does not "
                    "establish that an external pull-up is required."
                ),
                evidence={
                    "net": (gap.net,),
                    "active_low_chip_select_pins": gap.pins,
                    "recognized_positive_rails": gap.positive_rails,
                    "visible_pullup_paths": (),
                },
            )
        )
    return tuple(found)
