"""Small synthetic netlists and project requirements for single-ended dividers."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract
from kicad_tooling.hwrepo.signal_divider_models import (
    SignalDividerMap,
    SignalDividerRequirement,
    SignalDividerResistorRequirement,
)


def signal_divider_map() -> SignalDividerMap:
    return SignalDividerMap(
        basis="Synthetic ADC absolute-input limits and reviewed sensor source range",
        dividers=(
            SignalDividerRequirement(
                id="battery-monitor",
                receiver_reference="U1",
                expected_receiver_value="SYNTH-ANALOG",
                expected_receiver_symbol="Synthetic:AnalogMonitor",
                expected_receiver_footprint="Synthetic:SOIC-8",
                receiver_pin="U1.2",
                expected_receiver_pin_function="ADC_IN",
                expected_receiver_electrical_type="input",
                source_net="SENSOR_OUT",
                input_net="ADC_IN",
                reference_net="GND",
                upper_resistor=SignalDividerResistorRequirement(
                    reference="R1",
                    expected_symbol="Device:R",
                    expected_footprint="Synthetic:0603",
                    divider_pin="R1.2",
                    outer_pin="R1.1",
                    minimum_nominal_resistance_ohms=210_000.0,
                    maximum_nominal_resistance_ohms=230_000.0,
                ),
                lower_resistor=SignalDividerResistorRequirement(
                    reference="R2",
                    expected_symbol="Device:R",
                    expected_footprint="Synthetic:0603",
                    divider_pin="R2.1",
                    outer_pin="R2.2",
                    minimum_nominal_resistance_ohms=32_000.0,
                    maximum_nominal_resistance_ohms=34_000.0,
                ),
                minimum_source_voltage_v=24.0,
                maximum_source_voltage_v=24.0,
                minimum_input_voltage_v=3.0,
                maximum_input_voltage_v=3.3,
                basis="Synthetic sensor maximum and ADC operating input interval",
            ),
        ),
    )


def signal_divider_netlist(*, fault: str | None = None) -> NetlistContract:
    top_value = "180k" if fault == "top-resistor-value" else "220k"
    components = {
        "U1": ComponentContract(value="SYNTH-ANALOG", footprint="Synthetic:SOIC-8"),
        "R1": ComponentContract(value=top_value, footprint="Synthetic:0603"),
        "R2": ComponentContract(value="33k", footprint="Synthetic:0603"),
    }
    symbols = {"U1": "Synthetic:AnalogMonitor", "R1": "Device:R", "R2": "Device:R"}
    pin_functions = {
        "U1.1": "VREF_OUT",
        "U1.2": "ADC_IN",
        "R1.1": "passive",
        "R1.2": "passive",
        "R2.1": "passive",
        "R2.2": "passive",
    }
    electrical_types = {
        "U1.1": "output",
        "U1.2": "input",
        "R1.1": "passive",
        "R1.2": "passive",
        "R2.1": "passive",
        "R2.2": "passive",
    }
    nets: dict[str, tuple[str, ...]] = {
        "SENSOR_OUT": ("U1.1", "R1.1"),
        "ADC_IN": ("U1.2", "R1.2", "R2.1"),
        "GND": ("R2.2",),
    }
    pin_numbers = {"U1": ("1", "2"), "R1": ("1", "2"), "R2": ("1", "2")}
    dnp: tuple[str, ...] = ()
    if fault == "split-tap":
        nets["ADC_IN"] = ("U1.2", "R1.2")
        nets["ADC_IN_OTHER"] = ("R2.1",)
    elif fault == "dnp-lower-resistor":
        dnp = ("R2",)
    elif fault == "wrong-symbol":
        symbols["R1"] = "Synthetic:Other"
    elif fault == "wrong-function":
        pin_functions["U1.2"] = "GPIO"
    elif fault == "wrong-electrical-type":
        electrical_types["U1.2"] = "bidirectional"
    elif fault == "unmapped-load":
        components["R3"] = ComponentContract(value="100k", footprint="Synthetic:0603")
        symbols["R3"] = "Device:R"
        pin_functions.update({"R3.1": "passive", "R3.2": "passive"})
        electrical_types.update({"R3.1": "passive", "R3.2": "passive"})
        pin_numbers["R3"] = ("1", "2")
        nets["ADC_IN"] = (*nets["ADC_IN"], "R3.1")
        nets["GND"] = (*nets["GND"], "R3.2")
    return NetlistContract(
        components=components,
        nets=nets,
        dnp_components=dnp,
        component_symbols=symbols,
        pin_functions=pin_functions,
        pin_electrical_types=electrical_types,
        component_pin_numbers=pin_numbers,
    )
