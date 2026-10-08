"""Reviewable bias hints for open-collector and open-emitter signal nets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .bus_heuristics import (
    DirectResistor,
    direct_resistors,
    i2c_signal_role,
    is_active_low_chip_select_function,
)
from .connector_pins import power_function_key
from .control_inputs import control_input_family
from .models import NetlistContract
from .return_nets import is_return_like_net_name

_OPEN_OUTPUT_TYPES = frozenset({"open_collector", "open_emitter"})
_INPUT_TYPES = frozenset({"input", "input_low"})


@dataclass(frozen=True)
class OpenOutputBiasGap:
    net: str
    bias: Literal["pull_up", "pull_down"]
    output_pins: tuple[str, ...]
    input_pins: tuple[str, ...]
    visible_resistors: tuple[str, ...]


def open_output_bias_gaps(
    observed: NetlistContract,
) -> tuple[OpenOutputBiasGap, ...]:
    """Find non-specialized open-collector signal nets without a visible local bias path.

    Only native ``open_collector``/``open_emitter`` output types and native
    ``input``/``input_low`` peers are considered. I2C, recognized control
    inputs, and active-low SPI chip-select lines are handled by narrower rules.
    """
    pin_functions = {pin.casefold(): function for pin, function in observed.pin_functions.items()}
    pin_types = {
        pin.casefold(): value.strip().casefold()
        for pin, value in observed.pin_electrical_types.items()
    }
    dnp = {reference.casefold() for reference in observed.dnp_components}
    nets_by_pin: dict[str, set[str]] = {}
    pins_by_net: dict[str, set[str]] = {}
    actual_net_names: dict[str, str] = {}
    for net, pins in observed.nets.items():
        net_key = net.casefold()
        actual_net_names[net_key] = net
        for pin in pins:
            pin_key = pin.casefold()
            nets_by_pin.setdefault(pin_key, set()).add(net_key)
            pins_by_net.setdefault(net_key, set()).add(pin)

    positive_rails = {
        net.casefold()
        for net, pins in observed.nets.items()
        if power_function_key(net) is not None
        or any(
            power_function_key(pin_functions.get(pin.casefold(), "")) is not None for pin in pins
        )
    }
    return_rails = {
        net.casefold()
        for net, pins in observed.nets.items()
        if is_return_like_net_name(net)
        or any(is_return_like_net_name(pin_functions.get(pin.casefold(), "")) for pin in pins)
    }
    resistors = direct_resistors(observed)
    gaps: list[OpenOutputBiasGap] = []

    for net_key, assigned_pins in pins_by_net.items():
        net = actual_net_names[net_key]
        if net_key in positive_rails or net_key in return_rails:
            continue
        pins = tuple(
            sorted(
                (
                    pin
                    for pin in assigned_pins
                    if nets_by_pin.get(pin.casefold()) == {net_key}
                    and pin.rsplit(".", 1)[0].casefold() not in dnp
                ),
                key=str.casefold,
            )
        )
        drivers = tuple(pin for pin in pins if pin_types.get(pin.casefold()) in _OPEN_OUTPUT_TYPES)
        driver_types = {pin_types[pin.casefold()] for pin in drivers}
        if len(driver_types) != 1:
            continue
        input_pins = tuple(pin for pin in pins if pin_types.get(pin.casefold()) in _INPUT_TYPES)
        if not drivers or not input_pins:
            continue
        functions = tuple(pin_functions.get(pin.casefold(), "") for pin in (*drivers, *input_pins))
        if any(
            i2c_signal_role(function) is not None
            or control_input_family(function) is not None
            or is_active_low_chip_select_function(function)
            for function in functions
        ):
            continue

        bias: Literal["pull_up", "pull_down"] = (
            "pull_up" if driver_types == {"open_collector"} else "pull_down"
        )
        target_rails = positive_rails if bias == "pull_up" else return_rails
        signal_resistors = tuple(
            item
            for item in resistors
            if net_key in {item.first_net.casefold(), item.second_net.casefold()}
        )
        has_expected_bias = any(
            (item.first_net.casefold() == net_key and item.second_net.casefold() in target_rails)
            or (item.second_net.casefold() == net_key and item.first_net.casefold() in target_rails)
            for item in signal_resistors
        )
        if has_expected_bias:
            continue
        gaps.append(
            OpenOutputBiasGap(
                net=net,
                bias=bias,
                output_pins=drivers,
                input_pins=input_pins,
                visible_resistors=tuple(_format_resistor(item) for item in signal_resistors),
            )
        )
    return tuple(sorted(gaps, key=lambda item: (item.net.casefold(), item.net)))


def _format_resistor(resistor: DirectResistor) -> str:
    return (
        f"{resistor.reference} ({resistor.resistance_ohms:g} Ω): "
        f"{resistor.first_net} ↔ {resistor.second_net}"
    )
