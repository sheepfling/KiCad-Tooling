"""Minimal synthetic LED and series-resistor netlists for current-window lint."""

from __future__ import annotations

from kicad_tooling.hwrepo.led_current_models import (
    LedCurrentMap,
    LedCurrentRequirement,
    LedCurrentResistorRequirement,
)
from kicad_tooling.hwrepo.netlist_contract_models import ComponentContract, NetlistContract


def led_current_map(
    *,
    resistor_leg: str = "anode",
    resistor_outer_pin: str = "R1.1",
    resistor_led_side_pin: str = "R1.2",
    minimum_current_ma: float = 2.2,
    maximum_current_ma: float = 3.4,
) -> LedCurrentMap:
    """Return an authored current window for one synthetic indicator path."""
    led_side_net = "LED_A" if resistor_leg == "anode" else "LED_K"
    return LedCurrentMap(
        basis="Synthetic reviewed indicator-LED DC operating requirement",
        leds=(
            LedCurrentRequirement(
                id="status-indicator",
                led_reference="D1",
                expected_led_value="Synthetic green LED",
                expected_led_symbol="Device:LED",
                expected_led_footprint="Synthetic:LED_0603",
                anode_pin="D1.1",
                cathode_pin="D1.2",
                source_net="+3V3",
                return_net="GND",
                led_side_net=led_side_net,
                resistor_leg=resistor_leg,
                resistor=LedCurrentResistorRequirement(
                    reference="R1",
                    expected_symbol="Device:R",
                    expected_footprint="Synthetic:R_0603",
                    outer_pin=resistor_outer_pin,
                    led_side_pin=resistor_led_side_pin,
                    minimum_nominal_resistance_ohms=450,
                    maximum_nominal_resistance_ohms=500,
                    maximum_tolerance_percent=5,
                    tolerance_basis="Synthetic reviewed resistor tolerance",
                ),
                minimum_source_voltage_v=3.3,
                maximum_source_voltage_v=3.3,
                minimum_forward_voltage_v=1.8,
                maximum_forward_voltage_v=2.2,
                minimum_target_current_ma=minimum_current_ma,
                maximum_target_current_ma=maximum_current_ma,
                source_voltage_basis="Synthetic reviewed rail range",
                forward_voltage_basis="Synthetic sourced LED forward-voltage range",
                target_current_basis="Synthetic project-selected indicator-current range",
            ),
        ),
    )


def led_current_netlist(
    *,
    resistor_value: str = "470R",
    resistor_leg: str = "anode",
    dnp: tuple[str, ...] = (),
    extra_resistor: bool = False,
    led_value: str = "Synthetic green LED",
) -> NetlistContract:
    """Return an exact two-terminal LED path with configurable resistor evidence."""
    if resistor_leg == "anode":
        nets = {
            "+3V3": ("R1.1",),
            "LED_A": ("R1.2", "D1.1"),
            "GND": ("D1.2",),
        }
    elif resistor_leg == "cathode":
        nets = {
            "+3V3": ("D1.1",),
            "LED_K": ("D1.2", "R1.2"),
            "GND": ("R1.1",),
        }
    else:
        raise ValueError(f"Unsupported synthetic resistor leg: {resistor_leg}")

    components = {
        "D1": ComponentContract(
            value=led_value,
            footprint="Synthetic:LED_0603",
        ),
        "R1": ComponentContract(
            value=resistor_value,
            footprint="Synthetic:R_0603",
        ),
    }
    component_symbols = {"D1": "Device:LED", "R1": "Device:R"}
    component_pin_numbers = {"D1": ("1", "2"), "R1": ("1", "2")}
    pin_functions = {"D1.1": "A", "D1.2": "K", "R1.1": "~", "R1.2": "~"}
    pin_types = {pin: "passive" for pin in pin_functions}

    if extra_resistor:
        components["R2"] = ComponentContract(
            value="4k7",
            footprint="Synthetic:R_0603",
        )
        component_symbols["R2"] = "Device:R"
        component_pin_numbers["R2"] = ("1", "2")
        pin_functions.update({"R2.1": "~", "R2.2": "~"})
        pin_types.update({"R2.1": "passive", "R2.2": "passive"})
        nets["+3V3"] = (*nets["+3V3"], "R2.1")
        nets["LED_A" if resistor_leg == "anode" else "LED_K"] = (
            *nets["LED_A" if resistor_leg == "anode" else "LED_K"],
            "R2.2",
        )

    return NetlistContract(
        components=components,
        nets=nets,
        dnp_components=dnp,
        component_symbols=component_symbols,
        pin_functions=pin_functions,
        pin_electrical_types=pin_types,
        component_pin_numbers=component_pin_numbers,
    )
