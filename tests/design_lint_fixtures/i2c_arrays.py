"""Synthetic resistor-array inputs for I2C pull-up checks."""

from __future__ import annotations

from kicad_tooling.hwrepo.i2c_pullup_models import (
    I2cPullupCapacitanceContributorRequirement,
    I2cPullupCapacitanceScope,
)
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
    part_id: str | None = "SYNTHETIC-ARRAY-47K",
    dnp: tuple[str, ...] = (),
    swapped_sda_channel: bool = False,
    wrong_sda_net: bool = False,
) -> NetlistContract:
    sda_assignments = ("RN1.2", "RN1.1") if swapped_sda_channel else ("RN1.1", "RN1.2")
    return NetlistContract(
        components={
            "RN1": ComponentContract(value="4x4.7k", footprint="Synthetic:RA4", part_id=part_id)
        },
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
                expected_part_id="SYNTHETIC-ARRAY-47K",
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


def array_netlist_with_capacitor(
    *,
    reference: str = "C1",
    value: str = "10p",
    part_id: str | None = "SYNTHETIC-CAP-10P",
    return_net: str = "GND",
    extra_capacitor: bool = False,
) -> NetlistContract:
    """Add one or two fitted local capacitors to the synthetic SDA bus."""
    observed = array_netlist()
    references = (reference, "C2") if extra_capacitor else (reference,)
    components = dict(observed.components)
    symbols = dict(observed.component_symbols)
    pin_functions = dict(observed.pin_functions)
    pin_numbers = dict(observed.component_pin_numbers)
    nets = {net: tuple(pins) for net, pins in observed.nets.items()}
    for index, component_reference in enumerate(references):
        component_value = value if index == 0 else "4p"
        component_part_id = part_id if index == 0 else "SYNTHETIC-CAP-4P"
        components[component_reference] = ComponentContract(
            value=component_value,
            footprint="Synthetic:0603",
            part_id=component_part_id,
        )
        symbols[component_reference] = "Device:C"
        pin_functions[f"{component_reference}.1"] = "1"
        pin_functions[f"{component_reference}.2"] = "2"
        pin_numbers[component_reference] = ("1", "2")
        nets["I2C_SDA"] = (*nets.get("I2C_SDA", ()), f"{component_reference}.1")
        nets[return_net] = (*nets.get(return_net, ()), f"{component_reference}.2")
    return observed.model_copy(
        update={
            "components": components,
            "nets": nets,
            "component_symbols": symbols,
            "pin_functions": pin_functions,
            "component_pin_numbers": pin_numbers,
        }
    )


def array_requirement_with_capacitance_scope(
    *,
    reference: str = "C1",
    maximum_bus_capacitance_pf: float = 50.0,
    maximum_effective_capacitance_pf: float = 12.0,
    maximum_residual_capacitance_pf: float = 25.0,
) -> I2cPullupAnalysis:
    """Map the SDA capacitor and reserve an explicit residual bus-capacitance bound."""
    from tests.electrical_i2c_support import i2c_pullup_window_requirement

    requirement = array_requirement()
    bus = requirement.buses[0]
    window = (
        i2c_pullup_window_requirement(maximum_bus_capacitance_pf=maximum_bus_capacitance_pf)
        .buses[0]
        .sda.electrical_window
    )
    assert window is not None
    contributor = I2cPullupCapacitanceContributorRequirement(
        reference=reference,
        expected_symbol="Device:C",
        expected_footprint="Synthetic:0603",
        expected_part_id="SYNTHETIC-CAP-10P",
        signal_pin=f"{reference}.1",
        return_pin=f"{reference}.2",
        return_net="GND",
        minimum_nominal_capacitance_pf=5.0,
        maximum_nominal_capacitance_pf=15.0,
        nominal_capacitance_basis="Synthetic capacitor nominal-value review",
        maximum_effective_capacitance_pf=maximum_effective_capacitance_pf,
        effective_capacitance_basis="Synthetic DC-bias and tolerance bound",
    )
    scope = I2cPullupCapacitanceScope(
        inventory_basis="Synthetic inventory of fitted capacitors attached to SDA",
        maximum_residual_capacitance_pf=maximum_residual_capacitance_pf,
        residual_capacitance_basis="Synthetic endpoint, route, and pin-load residual",
        contributors=(contributor,),
    )
    sda_window = window.model_copy(update={"capacitance_scope": scope})
    sda = bus.sda.model_copy(
        update={
            "minimum_ohms": 4_000,
            "maximum_ohms": 5_000,
            "electrical_window": sda_window,
        }
    )
    scl = bus.scl.model_copy(update={"minimum_ohms": 4_000, "maximum_ohms": 5_000})
    return requirement.model_copy(
        update={"buses": (bus.model_copy(update={"sda": sda, "scl": scl}),)}
    )
