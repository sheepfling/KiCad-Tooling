"""Synthetic current-sink LED netlists and exact project path maps."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract
from kicad_tooling.hwrepo.power_path_models import (
    PowerPathElementRequirement,
    PowerPathEndpointRequirement,
    PowerPathMap,
    PowerPathRequirement,
)


def current_sink_netlist(
    *, driver_type: str = "output", two_channels: bool = False
) -> NetlistContract:
    components = {
        "U1": ComponentContract(
            value="Synthetic current sink",
            footprint="Synthetic:QFN",
            part_id="synthetic-cc-sink",
        ),
        "D1": ComponentContract(value="Synthetic LED", footprint="Synthetic:LED"),
        "U2": ComponentContract(value="Synthetic rail source", footprint="Synthetic:Source"),
    }
    nets = {"+5V": ("U2.1", "D1.1"), "LED_SINK": ("D1.2", "U1.1")}
    component_symbols = {
        "U1": "Synthetic:CurrentSink",
        "D1": "Device:LED",
        "U2": "Synthetic:RailSource",
    }
    pin_functions = {"U1.1": "OUT0", "D1.1": "A", "D1.2": "K", "U2.1": "VOUT"}
    pin_electrical_types = {
        "U1.1": driver_type,
        "D1.1": "passive",
        "D1.2": "passive",
        "U2.1": "power_out",
    }
    component_pin_numbers = {"U1": ("1",), "D1": ("1", "2"), "U2": ("1",)}
    if two_channels:
        components["D2"] = ComponentContract(value="Synthetic LED", footprint="Synthetic:LED")
        nets["+5V"] = ("U2.1", "D1.1", "D2.1")
        nets["LED_SINK1"] = ("D2.2", "U1.2")
        component_symbols["D2"] = "Device:LED"
        pin_functions.update({"U1.2": "OUT1", "D2.1": "A", "D2.2": "K"})
        pin_electrical_types.update({"U1.2": driver_type, "D2.1": "passive", "D2.2": "passive"})
        component_pin_numbers["U1"] = ("1", "2")
        component_pin_numbers["D2"] = ("1", "2")
    return NetlistContract(
        components=components,
        nets=nets,
        component_symbols=component_symbols,
        pin_functions=pin_functions,
        pin_electrical_types=pin_electrical_types,
        component_pin_numbers=component_pin_numbers,
    )


def current_sink_path_map(
    *,
    part_id: str = "synthetic-cc-sink",
    pin_function: str = "OUT0",
    pin_electrical_type: str = "output",
    led_anode_pin: str = "D1.1",
    led_cathode_pin: str = "D1.2",
    two_channels: bool = False,
) -> PowerPathMap:
    paths = [
        PowerPathRequirement(
            id="led-channel-0",
            basis="Synthetic reviewed source identifies U1.1 as a current sink output",
            start=PowerPathEndpointRequirement(
                reference="U2",
                pin="U2.1",
                symbol="Synthetic:RailSource",
                footprint="Synthetic:Source",
                net="+5V",
            ),
            end=PowerPathEndpointRequirement(
                reference="U1",
                pin="U1.1",
                symbol="Synthetic:CurrentSink",
                footprint="Synthetic:QFN",
                net="LED_SINK",
                role="current_controlled_sink",
                part_id=part_id,
                pin_function=pin_function,
                pin_electrical_type=pin_electrical_type,
            ),
            elements=(
                PowerPathElementRequirement(
                    reference="D1",
                    symbol="Device:LED",
                    footprint="Synthetic:LED",
                    side_a_pin=led_anode_pin,
                    side_b_pin=led_cathode_pin,
                    side_a_net="+5V",
                    side_b_net="LED_SINK",
                ),
            ),
        ),
    ]
    if two_channels:
        paths.append(
            PowerPathRequirement(
                id="led-channel-1",
                basis="Synthetic reviewed source identifies U1.2 as a current sink output",
                start=PowerPathEndpointRequirement(
                    reference="U2",
                    pin="U2.1",
                    symbol="Synthetic:RailSource",
                    footprint="Synthetic:Source",
                    net="+5V",
                ),
                end=PowerPathEndpointRequirement(
                    reference="U1",
                    pin="U1.2",
                    symbol="Synthetic:CurrentSink",
                    footprint="Synthetic:QFN",
                    net="LED_SINK1",
                    role="current_controlled_sink",
                    part_id=part_id,
                    pin_function="OUT1",
                    pin_electrical_type=pin_electrical_type,
                ),
                elements=(
                    PowerPathElementRequirement(
                        reference="D2",
                        symbol="Device:LED",
                        footprint="Synthetic:LED",
                        side_a_pin="D2.1",
                        side_b_pin="D2.2",
                        side_a_net="+5V",
                        side_b_net="LED_SINK1",
                    ),
                ),
            )
        )
    return PowerPathMap(
        basis="Synthetic project-approved current-controlled LED output path",
        paths=tuple(paths),
    )
