"""Synthetic builders for authored I2C pull-up contract tests."""

from __future__ import annotations

from kicad_tooling.hwrepo.i2c_pullup_models import (
    I2cPullupAnalysis,
    I2cPullupArrayChannelRequirement,
    I2cPullupArrayRequirement,
    I2cPullupBusRequirement,
    I2cPullupElectricalWindow,
    I2cPullupInputVoltageLimit,
    I2cPullupLineRequirement,
    I2cPullupSeriesPathRequirement,
    I2cPullupSeriesResistorRequirement,
    I2cPullupVoltageCompatibilityRequirement,
)
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    NetlistContract,
)


def i2c_pullup_requirement() -> I2cPullupAnalysis:
    return I2cPullupAnalysis(
        basis="Synthetic local direct-resistor requirements",
        buses=(
            I2cPullupBusRequirement(
                id="control",
                basis="Reviewed synthetic controller bus requirement",
                sda=I2cPullupLineRequirement(
                    net="I2C_SDA", rail="+3V3", minimum_ohms=2_300, maximum_ohms=2_500
                ),
                scl=I2cPullupLineRequirement(
                    net="I2C_SCL", rail="+3V3", minimum_ohms=4_000, maximum_ohms=5_000
                ),
            ),
        ),
    )


def i2c_pullup_window_requirement(
    first_reference: str = "R10",
    second_reference: str = "R11",
    *,
    minimum_ohms: float = 4_000,
    maximum_ohms: float = 5_000,
    maximum_pullup_voltage_v: float = 3.3,
    maximum_low_level_voltage_v: float = 0.4,
    minimum_sink_current_ma: float = 3.0,
    maximum_bus_capacitance_pf: float = 50.0,
    maximum_rise_time_ns: float = 300.0,
    maximum_per_resistor_tolerance_percent: float | None = None,
    resistor_tolerance_basis: str | None = None,
) -> I2cPullupAnalysis:
    base = i2c_pullup_voltage_requirement(
        first_reference,
        second_reference,
        maximum_rail_voltage_v=maximum_pullup_voltage_v,
        maximum_input_voltage_v=maximum_pullup_voltage_v,
    )
    window = I2cPullupElectricalWindow(
        maximum_pullup_voltage_v=maximum_pullup_voltage_v,
        pullup_voltage_basis="Synthetic maximum supply tolerance",
        maximum_low_level_voltage_v=maximum_low_level_voltage_v,
        low_level_voltage_basis="Synthetic weakest-device VOL specification",
        minimum_sink_current_ma=minimum_sink_current_ma,
        sink_current_basis="Synthetic weakest-device guaranteed sink current",
        maximum_bus_capacitance_pf=maximum_bus_capacitance_pf,
        bus_capacitance_basis="Synthetic board and endpoint capacitance bound",
        maximum_rise_time_ns=maximum_rise_time_ns,
        rise_time_basis="Synthetic interface timing requirement",
        maximum_per_resistor_tolerance_percent=maximum_per_resistor_tolerance_percent,
        resistor_tolerance_basis=resistor_tolerance_basis,
    )
    bus = base.buses[0]
    sda = bus.sda.model_copy(
        update={
            "minimum_ohms": minimum_ohms,
            "maximum_ohms": maximum_ohms,
            "electrical_window": window,
        }
    )
    scl = bus.scl.model_copy(
        update={
            "minimum_ohms": minimum_ohms,
            "maximum_ohms": maximum_ohms,
            "electrical_window": window,
        }
    )
    return base.model_copy(update={"buses": (bus.model_copy(update={"sda": sda, "scl": scl}),)})


def i2c_series_pullup_requirement(
    first_reference: str = "R10", second_reference: str = "R11"
) -> I2cPullupAnalysis:
    return I2cPullupAnalysis(
        basis="Synthetic explicit series-chain pull-up requirement",
        buses=(
            I2cPullupBusRequirement(
                id="series-bus",
                basis="Synthetic reviewed controller bus requirement",
                sda=I2cPullupLineRequirement(
                    net="I2C_SDA", rail="+3V3", minimum_ohms=4_000, maximum_ohms=5_000
                ),
                scl=I2cPullupLineRequirement(
                    net="I2C_SCL", rail="+3V3", minimum_ohms=4_000, maximum_ohms=5_000
                ),
            ),
        ),
        series_paths=(
            I2cPullupSeriesPathRequirement(
                id="sda-chain",
                basis="Synthetic reviewed discrete resistor chain",
                signal_net="I2C_SDA",
                rail_net="+3V3",
                resistors=(
                    I2cPullupSeriesResistorRequirement(
                        reference=first_reference,
                        expected_symbol="Device:R",
                        expected_footprint="Synthetic:R",
                        from_net="I2C_SDA",
                        to_net="I2C_SDA_CHAIN",
                        minimum_ohms=900,
                        maximum_ohms=1_100,
                    ),
                    I2cPullupSeriesResistorRequirement(
                        reference=second_reference,
                        expected_symbol="Device:R",
                        expected_footprint="Synthetic:R",
                        from_net="I2C_SDA_CHAIN",
                        to_net="+3V3",
                        minimum_ohms=3_500,
                        maximum_ohms=3_900,
                    ),
                ),
            ),
        ),
    )


def i2c_pullup_voltage_requirement(
    first_reference: str = "R10",
    second_reference: str = "R11",
    *,
    maximum_rail_voltage_v: float = 3.3,
    maximum_input_voltage_v: float = 3.3,
) -> I2cPullupAnalysis:
    base = i2c_series_pullup_requirement(first_reference, second_reference)

    def voltage_limit(pin: str) -> I2cPullupVoltageCompatibilityRequirement:
        return I2cPullupVoltageCompatibilityRequirement(
            input_scope_basis="Synthetic reviewed local I2C endpoint inventory",
            maximum_rail_voltage_v=maximum_rail_voltage_v,
            rail_basis="Synthetic supply ceiling including tolerance",
            input_limits=(
                I2cPullupInputVoltageLimit(
                    pin=pin,
                    expected_symbol="Synthetic:I2cTarget",
                    expected_footprint="Synthetic:SOIC8",
                    limit_kind="absolute_maximum",
                    maximum_bus_voltage_v=maximum_input_voltage_v,
                    limit_basis="Synthetic target datasheet maximum input voltage",
                ),
            ),
        )

    data = base.model_dump(mode="python")
    data["buses"][0]["sda"]["voltage_compatibility"] = voltage_limit("U1.1").model_dump()
    data["buses"][0]["scl"]["voltage_compatibility"] = voltage_limit("U1.2").model_dump()
    return I2cPullupAnalysis.model_validate(data)


def i2c_series_pullup_netlist(
    *,
    first_value: str = "1k",
    second_value: str = "3.7k",
    scl_value: str = "4.7k",
    dnp: tuple[str, ...] = (),
    extra_junction_pin: bool = False,
    first_symbol: str = "Device:R",
    second_footprint: str = "Synthetic:R",
) -> NetlistContract:
    chain_pins = ("R10.2", "R11.1", *(("U9.1",) if extra_junction_pin else ()))
    return NetlistContract(
        components={
            "U1": ComponentContract(value="Synthetic I2C target", footprint="Synthetic:SOIC8"),
            "R10": ComponentContract(value=first_value, footprint="Synthetic:R"),
            "R11": ComponentContract(value=second_value, footprint=second_footprint),
            "R12": ComponentContract(value=scl_value, footprint="Synthetic:R"),
        },
        nets={
            "I2C_SDA": ("U1.1", "R10.1"),
            "I2C_SDA_CHAIN": chain_pins,
            "+3V3": ("R11.2", "R12.2"),
            "I2C_SCL": ("U1.2", "R12.1"),
        },
        dnp_components=dnp,
        component_symbols={
            "U1": "Synthetic:I2cTarget",
            "R10": first_symbol,
            "R11": "Device:R",
            "R12": "Device:R",
        },
        pin_functions={
            "U1.1": "SDA",
            "U1.2": "SCL",
            "R10.1": "1",
            "R10.2": "2",
            "R11.1": "1",
            "R11.2": "2",
            "R12.1": "1",
            "R12.2": "2",
        },
        component_pin_numbers={
            "U1": ("1", "2"),
            "R10": ("1", "2"),
            "R11": ("1", "2"),
            "R12": ("1", "2"),
        },
    )


def i2c_pullup_array_requirement(
    *, unmapped_pin_reasons: dict[str, str] | None = None
) -> I2cPullupAnalysis:
    return I2cPullupAnalysis(
        basis="Synthetic reviewed resistor-array part and bus requirement",
        buses=(
            I2cPullupBusRequirement(
                id="array-bus",
                basis="Synthetic bus topology",
                sda=I2cPullupLineRequirement(
                    net="I2C_SDA", rail="+3V3", minimum_ohms=4_000, maximum_ohms=5_000
                ),
                scl=I2cPullupLineRequirement(
                    net="I2C_SCL", rail="+3V3", minimum_ohms=4_000, maximum_ohms=5_000
                ),
            ),
        ),
        arrays=(
            I2cPullupArrayRequirement(
                reference="RN1",
                expected_symbol="Synthetic:ResistorArray",
                expected_footprint="Synthetic:RA4",
                expected_value="4x4.7k",
                basis="Synthetic reviewed array datasheet and pin-pair map",
                channels=(
                    I2cPullupArrayChannelRequirement(
                        id="sda",
                        signal_pin="RN1.1",
                        rail_pin="RN1.2",
                        signal_net="I2C_SDA",
                        rail_net="+3V3",
                        resistance_ohms=4_700,
                        basis="Synthetic channel one pin pair",
                    ),
                    I2cPullupArrayChannelRequirement(
                        id="scl",
                        signal_pin="RN1.3",
                        rail_pin="RN1.4",
                        signal_net="I2C_SCL",
                        rail_net="+3V3",
                        resistance_ohms=4_700,
                        basis="Synthetic channel two pin pair",
                    ),
                ),
                unmapped_pin_reasons=unmapped_pin_reasons or {},
            ),
        ),
    )


def i2c_pullup_array_netlist(
    *,
    value: str = "4x4.7k",
    symbol: str = "Synthetic:ResistorArray",
    footprint: str = "Synthetic:RA4",
    sda_signal_net: str = "I2C_SDA",
    extra_pin: bool = False,
    dnp: tuple[str, ...] = (),
) -> NetlistContract:
    pins = ("1", "2", "3", "4", *(("5",) if extra_pin else ()))
    nets = {
        "I2C_SDA": ("U1.1", "RN1.1") if sda_signal_net == "I2C_SDA" else ("U1.1",),
        "I2C_SCL": ("U1.2", "RN1.3"),
        "+3V3": ("RN1.2", "RN1.4"),
    }
    if sda_signal_net != "I2C_SDA":
        nets[sda_signal_net] = ("RN1.1",)
    return NetlistContract(
        components={
            "U1": ComponentContract(value="Synthetic I2C target", footprint="Synthetic:SOIC8"),
            "RN1": ComponentContract(value=value, footprint=footprint),
        },
        nets=nets,
        dnp_components=dnp,
        component_symbols={"U1": "Synthetic:I2cTarget", "RN1": symbol},
        pin_functions={
            "U1.1": "SDA",
            "U1.2": "SCL",
            "RN1.1": "A1",
            "RN1.2": "A2",
            "RN1.3": "B1",
            "RN1.4": "B2",
            **({"RN1.5": "NC"} if extra_pin else {}),
        },
        component_pin_numbers={"U1": ("1", "2"), "RN1": pins},
    )


def i2c_pullup_netlist(
    *,
    sda_values: tuple[str, ...] = ("4.7k", "4.7k"),
    scl_values: tuple[str, ...] = ("4.7k",),
    scl_rail: str = "+3V3",
    dnp: tuple[str, ...] = (),
    array_reference: str | None = None,
) -> NetlistContract:
    components = {
        f"R{number}": ComponentContract(value=value, footprint="")
        for number, value in enumerate((*sda_values, *scl_values), start=1)
    }
    nets: dict[str, tuple[str, ...]] = {
        "I2C_SDA": ("U1.1",),
        "I2C_SCL": ("U1.2",),
        "+3V3": (),
    }
    pin_functions = {"U1.1": "SDA", "U1.2": "SCL"}
    for index, reference in enumerate(components):
        bus_net = "I2C_SDA" if index < len(sda_values) else "I2C_SCL"
        rail_net = "+3V3" if bus_net == "I2C_SDA" else scl_rail
        nets[bus_net] = (*nets[bus_net], f"{reference}.1")
        nets[rail_net] = (*nets.get(rail_net, ()), f"{reference}.2")
        pin_functions.update({f"{reference}.1": "1", f"{reference}.2": "2"})
    pin_numbers = {array_reference: ("1", "2", "3", "4")} if array_reference is not None else {}
    return NetlistContract(
        components=components,
        nets=nets,
        dnp_components=dnp,
        component_symbols={
            "U1": "Synthetic:I2cTarget",
            **{reference: "Device:R" for reference in components},
        },
        pin_functions=pin_functions,
        component_pin_numbers=pin_numbers,
    )
