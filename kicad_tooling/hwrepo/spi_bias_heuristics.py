"""Spi bias heuristics for deterministic KiCad bus analysis."""

from __future__ import annotations

from dataclasses import dataclass

from .bus_signal_roles import is_active_low_chip_select_function
from .models import NetlistContract
from .resistor_paths import (
    VISIBLE_PULLUP_MAX_OHMS,
    VISIBLE_PULLUP_MIN_OHMS,
    positive_power_nets,
    visible_resistor_pullups,
)
from .return_nets import is_return_like_net_name
from .spi_bias_array_paths import spi_bias_array_channel_evidence
from .spi_models import SpiAnalysis


@dataclass(frozen=True, slots=True)
class SpiChipSelectBiasGap:
    net: str
    pins: tuple[str, ...]
    positive_rails: tuple[str, ...]


def spi_active_low_chip_selects_without_pullups(
    observed: NetlistContract,
    analysis: SpiAnalysis | None = None,
) -> tuple[SpiChipSelectBiasGap, ...]:
    """Find assigned active-low SPI input pins without a visible local pull-up path."""
    positive_rails = positive_power_nets(observed)
    if not positive_rails:
        return ()

    pin_nets: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin, set()).add(net)

    dnp = {reference.casefold() for reference in observed.dnp_components}
    chip_selects_by_net: dict[str, set[str]] = {}
    for pin, function in observed.pin_functions.items():
        reference = pin.rsplit(".", 1)[0]
        if reference.casefold() in dnp or not is_active_low_chip_select_function(function):
            continue
        if observed.pin_electrical_types.get(pin, "").casefold() not in {"input", "input_low"}:
            continue
        assignments = pin_nets.get(pin, set())
        if len(assignments) != 1:
            continue
        net = next(iter(assignments))
        if net in positive_rails or is_return_like_net_name(net):
            continue
        chip_selects_by_net.setdefault(net, set()).add(pin)

    visible_pullups = {net.casefold() for net in visible_resistor_pullups(observed)}
    if analysis is not None:
        recognized_rails = {net.casefold() for net in positive_rails}
        visible_pullups.update(
            item.signal_net.casefold()
            for item in spi_bias_array_channel_evidence(analysis, observed)
            if item.matches
            and item.rail_net.casefold() in recognized_rails
            and VISIBLE_PULLUP_MIN_OHMS <= item.resistance_ohms <= VISIBLE_PULLUP_MAX_OHMS
        )
    return tuple(
        SpiChipSelectBiasGap(
            net=net,
            pins=tuple(sorted(pins)),
            positive_rails=tuple(sorted(positive_rails)),
        )
        for net, pins in sorted(chip_selects_by_net.items())
        if net.casefold() not in visible_pullups
    )
