"""Synthetic CAN termination contract fixtures."""

from __future__ import annotations

from collections.abc import Mapping

from kicad_tooling.hwrepo.models import (
    CanTerminationAnalysis,
    CanTerminationBusRequirement,
    CanTerminationEndpointRequirement,
    CanTerminationMidpointCapacitorRequirement,
    CanTerminationResistorRequirement,
    ComponentContract,
    NetlistContract,
)


def can_termination_requirement(
    first_reference: str = "R1",
    second_reference: str = "R2",
    high_pin: str = "U1.1",
    low_pin: str = "U1.2",
) -> CanTerminationAnalysis:
    return CanTerminationAnalysis(
        basis="Synthetic reviewed two-end bus topology",
        buses=(
            CanTerminationBusRequirement(
                id="fieldbus",
                basis="Synthetic controller CAN interface",
                high_net="CAN_H",
                low_net="CAN_L",
                high_pins=(high_pin,),
                low_pins=(low_pin,),
                endpoints=(
                    CanTerminationEndpointRequirement(
                        id="local-a",
                        basis="Local terminator at declared bus endpoint A",
                        topology="direct",
                        resistors=(
                            CanTerminationResistorRequirement(
                                reference=first_reference,
                                first_net="CAN_H",
                                second_net="CAN_L",
                                minimum_ohms=108,
                                maximum_ohms=132,
                            ),
                        ),
                    ),
                    CanTerminationEndpointRequirement(
                        id="local-b",
                        basis="Local terminator at declared bus endpoint B",
                        topology="direct",
                        resistors=(
                            CanTerminationResistorRequirement(
                                reference=second_reference,
                                first_net="CAN_H",
                                second_net="CAN_L",
                                minimum_ohms=108,
                                maximum_ohms=132,
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )


def can_split_termination_requirement(
    first_reference: str = "R4", second_reference: str = "R5"
) -> CanTerminationAnalysis:
    """Synthetic CAN split network with an explicitly required midpoint capacitor."""
    return CanTerminationAnalysis(
        basis="Synthetic reviewed split CAN topology",
        buses=(
            CanTerminationBusRequirement(
                id="fieldbus",
                basis="Synthetic controller CAN interface",
                high_net="CAN_H",
                low_net="CAN_L",
                high_pins=("U2.1",),
                low_pins=("U2.2",),
                endpoints=(
                    CanTerminationEndpointRequirement(
                        id="local",
                        basis="Synthetic split termination at the local endpoint",
                        topology="split",
                        midpoint_net="CAN_TERM_MID",
                        resistors=(
                            CanTerminationResistorRequirement(
                                reference=first_reference,
                                first_net="CAN_H",
                                second_net="CAN_TERM_MID",
                                minimum_ohms=54,
                                maximum_ohms=66,
                            ),
                            CanTerminationResistorRequirement(
                                reference=second_reference,
                                first_net="CAN_L",
                                second_net="CAN_TERM_MID",
                                minimum_ohms=54,
                                maximum_ohms=66,
                            ),
                        ),
                        midpoint_capacitor=CanTerminationMidpointCapacitorRequirement(
                            reference="C1",
                            expected_symbol="Synthetic:CanMidpointCapacitor",
                            expected_footprint="Synthetic:CAP",
                            midpoint_pin="C1.1",
                            reference_pin="C1.2",
                            reference_net="GND",
                            minimum_nominal_capacitance_pf=90,
                            maximum_nominal_capacitance_pf=110,
                        ),
                    ),
                ),
            ),
        ),
    )


def can_termination_netlist(
    paths: Mapping[str, tuple[str, str, str]] | None = None,
    *,
    dnp: tuple[str, ...] = (),
    midpoint_capacitor: tuple[str, str, str, str] | None = None,
) -> NetlistContract:
    resistor_paths = (
        {
            "R1": ("120R", "CAN_H", "CAN_L"),
            "R2": ("120R", "CAN_H", "CAN_L"),
        }
        if paths is None
        else paths
    )
    capacitor_components = (
        {}
        if midpoint_capacitor is None
        else {
            midpoint_capacitor[0]: ComponentContract(
                value=midpoint_capacitor[1], footprint="Synthetic:CAP"
            )
        }
    )
    components = {
        "U1": ComponentContract(value="Synthetic CAN transceiver", footprint=""),
        **capacitor_components,
        **{
            reference: ComponentContract(value=value, footprint="")
            for reference, (value, _, _) in resistor_paths.items()
        },
    }
    nets: dict[str, tuple[str, ...]] = {"CAN_H": ("U1.1",), "CAN_L": ("U1.2",)}
    pin_functions = {"U1.1": "CANH", "U1.2": "CANL"}
    for reference, (_, first_net, second_net) in resistor_paths.items():
        nets[first_net] = (*nets.get(first_net, ()), f"{reference}.1")
        nets[second_net] = (*nets.get(second_net, ()), f"{reference}.2")
        pin_functions.update({f"{reference}.1": "1", f"{reference}.2": "2"})
    if midpoint_capacitor is not None:
        reference, _, midpoint_net, reference_net = midpoint_capacitor
        nets[midpoint_net] = (*nets.get(midpoint_net, ()), f"{reference}.1")
        nets[reference_net] = (*nets.get(reference_net, ()), f"{reference}.2")
        pin_functions.update({f"{reference}.1": "1", f"{reference}.2": "2"})
    return NetlistContract(
        components=components,
        nets=nets,
        dnp_components=dnp,
        component_symbols={
            "U1": "Synthetic:CanTransceiver",
            **({midpoint_capacitor[0]: "Device:C"} if midpoint_capacitor else {}),
            **{reference: "Device:R" for reference in resistor_paths},
        },
        pin_functions=pin_functions,
        component_pin_numbers={
            **{reference: ("1", "2") for reference in resistor_paths},
            **({midpoint_capacitor[0]: ("1", "2")} if midpoint_capacitor else {}),
        },
    )
