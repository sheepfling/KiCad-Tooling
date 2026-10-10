"""Shared recognition and inventory for project control inputs."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .connector_identity import power_function_key
from .models import NetlistContract
from .resistor_paths import direct_resistors
from .return_nets import is_return_like_net_name

OUTPUT_CAPABLE_TYPES = frozenset(
    {
        "output",
        "bidirectional",
        "tri_state",
        "power_out",
        "open_collector",
        "open_emitter",
    }
)

_CONTROL_INPUT_TYPES = frozenset({"input", "input_low"})

_CONTROL_FUNCTION_FAMILIES = {
    "reset": "reset",
    "resetn": "reset",
    "nreset": "reset",
    "nrst": "reset",
    "rst": "reset",
    "rstn": "reset",
    "rstb": "reset",
    "resetb": "reset",
    "hreset": "reset",
    "rsti": "reset",
    "por": "reset",
    "perst": "reset",
    "perst0": "reset",
    "perstn": "reset",
    "en": "enable",
    "ena": "enable",
    "enb": "enable",
    "enn": "enable",
    "nen": "enable",
    "enable": "enable",
    "enablen": "enable",
    "enableb": "enable",
    "shdn": "enable",
    "shutdown": "enable",
    "powerdown": "enable",
    "standby": "enable",
    "boot": "boot/strap",
    "boot0": "boot/strap",
    "boot1": "boot/strap",
    "bootsel": "boot/strap",
    "bootmode": "boot/strap",
    "bootstrap": "boot/strap",
    "nrpiboot": "boot/strap",
    "strap0": "boot/strap",
    "strap1": "boot/strap",
}


@dataclass(frozen=True)
class UnconnectedControlInput:
    pin: str
    function: str
    family: str
    electrical_type: str


@dataclass(frozen=True)
class ConnectedControlInput:
    pin: str
    function: str
    family: str
    electrical_type: str
    net: str


@dataclass(frozen=True)
class ControlInputBiasGap:
    net: str
    controls: tuple[ConnectedControlInput, ...]
    output_capable_peers: tuple[str, ...]


def control_input_family(function: str) -> str | None:
    normalized = re.sub(r"[^a-z0-9]+", "", function.casefold())
    family = _CONTROL_FUNCTION_FAMILIES.get(normalized)
    if family is not None:
        return family
    tokens = re.findall(r"[a-z0-9]+", function.casefold())
    return next(
        (
            _CONTROL_FUNCTION_FAMILIES[token]
            for expected_family in ("reset", "enable", "boot/strap")
            for token in tokens
            if _CONTROL_FUNCTION_FAMILIES.get(token) == expected_family
        ),
        None,
    )


def unconnected_control_inputs(observed: NetlistContract) -> tuple[UnconnectedControlInput, ...]:
    """Find unassigned input pins with a bounded reset, enable, or boot alias."""
    connected_pins = {pin.casefold() for pins in observed.nets.values() for pin in pins}
    dnp_components = {reference.casefold() for reference in observed.dnp_components}
    pin_types = {
        pin.casefold(): value.strip().casefold()
        for pin, value in observed.pin_electrical_types.items()
    }
    candidates: list[UnconnectedControlInput] = []
    for pin, function in observed.pin_functions.items():
        reference = pin.rsplit(".", maxsplit=1)[0].casefold()
        if reference in dnp_components:
            continue
        family = control_input_family(function)
        electrical_type = pin_types.get(pin.casefold(), "")
        if (
            family is not None
            and electrical_type in _CONTROL_INPUT_TYPES
            and pin.casefold() not in connected_pins
        ):
            candidates.append(
                UnconnectedControlInput(
                    pin=pin,
                    function=function,
                    family=family,
                    electrical_type=electrical_type,
                )
            )
    return tuple(sorted(candidates, key=lambda item: (item.pin.casefold(), item.function)))


def connected_control_inputs_without_visible_rail_resistor(
    observed: NetlistContract,
) -> tuple[ControlInputBiasGap, ...]:
    """Find connected reset/enable/boot inputs without a direct fitted resistor to a named rail."""
    pin_nets: dict[str, set[str]] = {}
    pins_by_net: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin.casefold(), set()).add(net)
            pins_by_net.setdefault(net, set()).add(pin)

    dnp_components = {reference.casefold() for reference in observed.dnp_components}
    pin_types = {
        pin.casefold(): value.strip().casefold()
        for pin, value in observed.pin_electrical_types.items()
    }
    controls_by_net: dict[str, list[ConnectedControlInput]] = {}
    for pin, function in observed.pin_functions.items():
        if pin.rsplit(".", maxsplit=1)[0].casefold() in dnp_components:
            continue
        family = control_input_family(function)
        electrical_type = pin_types.get(pin.casefold(), "")
        assigned_nets = pin_nets.get(pin.casefold(), set())
        if family is None or electrical_type not in _CONTROL_INPUT_TYPES or len(assigned_nets) != 1:
            continue
        net = next(iter(assigned_nets))
        controls_by_net.setdefault(net, []).append(
            ConnectedControlInput(
                pin=pin,
                function=function,
                family=family,
                electrical_type=electrical_type,
                net=net,
            )
        )

    positive_rails = {
        net
        for net, pins in observed.nets.items()
        if power_function_key(net) is not None
        or any(power_function_key(observed.pin_functions.get(pin, "")) is not None for pin in pins)
    }
    return_nets = {
        net
        for net, pins in observed.nets.items()
        if is_return_like_net_name(net)
        or any(is_return_like_net_name(observed.pin_functions.get(pin, "")) for pin in pins)
    }
    rail_keys = {net.casefold() for net in positive_rails | return_nets}
    control_net_keys = {net.casefold() for net in controls_by_net}

    biased_signal_keys: set[str] = set()
    for resistor in direct_resistors(observed):
        first_key = resistor.first_net.casefold()
        second_key = resistor.second_net.casefold()
        if first_key in rail_keys and second_key in control_net_keys:
            biased_signal_keys.add(second_key)
        if second_key in rail_keys and first_key in control_net_keys:
            biased_signal_keys.add(first_key)

    gaps: list[ControlInputBiasGap] = []
    for net, controls in controls_by_net.items():
        net_key = net.casefold()
        if net_key in rail_keys or net_key in biased_signal_keys:
            continue
        control_keys = {item.pin.casefold() for item in controls}
        output_capable_peers = tuple(
            sorted(
                (
                    f"{pin}: {observed.pin_functions.get(pin, 'unknown function')} "
                    f"({pin_types.get(pin.casefold(), 'unknown type')})"
                    for pin in pins_by_net.get(net, set())
                    if pin.casefold() not in control_keys
                    and pin_types.get(pin.casefold()) in OUTPUT_CAPABLE_TYPES
                ),
                key=str.casefold,
            )
        )
        gaps.append(
            ControlInputBiasGap(
                net=net,
                controls=tuple(
                    sorted(controls, key=lambda item: (item.pin.casefold(), item.function))
                ),
                output_capable_peers=output_capable_peers,
            )
        )
    return tuple(sorted(gaps, key=lambda item: (item.net.casefold(), item.net)))
