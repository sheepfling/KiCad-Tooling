"""Electrical requirements, negative engineering cases and runner evidence boundaries."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Literal
from unittest.mock import patch

from kicad_tooling.hwrepo.bus_heuristics import (
    can_termination_checks,
)
from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.electrical import (
    bound_inputs,
    load_analysis,
    policy_issues,
    power_budget_checks,
    selected_config,
)
from kicad_tooling.hwrepo.electrical_runner import analyze
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.generation import expected_outputs
from kicad_tooling.hwrepo.models import (
    AnalysisNotApplicable,
    CanTerminationAnalysis,
    CanTerminationBusRequirement,
    CanTerminationEndpointRequirement,
    CanTerminationMidpointCapacitorRequirement,
    CanTerminationResistorRequirement,
    CommandEvidence,
    ComponentContract,
    ElectricalAnalysisContract,
    FrequencyAnalysis,
    GroundDomain,
    GroundingAnalysis,
    HighFrequencyAnalysis,
    NetlistContract,
    PowerAnalysis,
    PowerConnectivityAnalysis,
    PowerConnectivityRailRequirement,
    PowerLoad,
    PowerLoadConnectivityRequirement,
    PowerPinEndpointRequirement,
    PowerRail,
    PowerSourceGroupRequirement,
    Rs485Analysis,
    Rs485BiasResistorRequirement,
    Rs485BusRequirement,
    Rs485DnpResistorRequirement,
    Rs485EndpointPinRequirement,
    Rs485EndpointRequirement,
    Rs485InternalFailSafeRequirement,
    Rs485LocalBiasRequirement,
    Rs485NoBiasRequirement,
    Rs485RemoteBiasRequirement,
    Rs485SignalPairRequirement,
    Rs485TerminationEndpointRequirement,
    Rs485TerminationResistorRequirement,
    SimulationMeasure,
    TransientAnalysis,
)
from kicad_tooling.hwrepo.power_connectivity import power_connectivity_checks
from kicad_tooling.hwrepo.rs485_heuristics import rs485_checks
from kicad_tooling.hwrepo.spice import (
    expanded_deck,
    measured_checks,
    run_case,
    simulation_deck,
    simulator_version,
    waveform_checks,
)
from kicad_tooling.validate import hashes

PROJECT = "controller"
ISLAND = "examples/projects/controller"
NA = AnalysisNotApplicable(mode="not_applicable", reason="Synthetic test scope")


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
    paths: dict[str, tuple[str, str, str]] | None = None,
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


def rs485_requirement(
    *,
    topology: Literal["two_wire_half_duplex", "four_wire_full_duplex"] = "two_wire_half_duplex",
    termination_mode: Literal["direct", "split"] = "direct",
    bias_mode: Literal["local", "remote", "internal_failsafe", "not_required"] = "local",
    isolated: bool = False,
    dnp_option: bool = False,
    external_peers: tuple[str, ...] = (),
) -> Rs485Analysis:
    pair_specs = (
        ("shared", "bidirectional", "485_LINE_1", "485_LINE_2", "R20", "R26", "R21", "R22"),
    )
    if topology == "four_wire_full_duplex":
        pair_specs = (
            (
                "board-to-peer",
                "board_to_peer",
                "485_TX_1",
                "485_TX_2",
                "R20",
                "R26",
                "R21",
                "R22",
            ),
            (
                "peer-to-board",
                "peer_to_board",
                "485_RX_1",
                "485_RX_2",
                "R23",
                "R27",
                "R24",
                "R25",
            ),
        )
    pairs: list[Rs485SignalPairRequirement] = []
    transceiver_pins: list[Rs485EndpointPinRequirement] = []
    connector_pins: list[Rs485EndpointPinRequirement] = []
    for index, (
        pair_id,
        purpose,
        line_1,
        line_2,
        term_ref,
        split_term_ref,
        up_ref,
        down_ref,
    ) in enumerate(pair_specs):
        transceiver_line_pins = (f"U20.{1 + index * 2}", f"U20.{2 + index * 2}")
        connector_line_pins = (f"J20.{1 + index * 2}", f"J20.{2 + index * 2}")
        transceiver_pins.extend(
            (
                Rs485EndpointPinRequirement(
                    role="bus_line_1",
                    pair_id=pair_id,
                    pin=transceiver_line_pins[0],
                    net=line_1,
                ),
                Rs485EndpointPinRequirement(
                    role="bus_line_2",
                    pair_id=pair_id,
                    pin=transceiver_line_pins[1],
                    net=line_2,
                ),
            )
        )
        connector_pins.extend(
            (
                Rs485EndpointPinRequirement(
                    role="bus_line_1", pair_id=pair_id, pin=connector_line_pins[0], net=line_1
                ),
                Rs485EndpointPinRequirement(
                    role="bus_line_2", pair_id=pair_id, pin=connector_line_pins[1], net=line_2
                ),
            )
        )
        if bias_mode == "local":
            bias: (
                Rs485LocalBiasRequirement
                | Rs485RemoteBiasRequirement
                | Rs485InternalFailSafeRequirement
                | Rs485NoBiasRequirement
            ) = Rs485LocalBiasRequirement(
                mode="local",
                basis="Synthetic two-resistor idle-bus bias values authored for this fixture",
                pull_up=Rs485BiasResistorRequirement(
                    reference=up_ref,
                    symbol="Device:R",
                    footprint="Resistor_SMD:R_0603_1608Metric",
                    bus_net=line_1,
                    rail_net="+5V_BIAS",
                    minimum_ohms=600,
                    maximum_ohms=750,
                ),
                pull_down=Rs485BiasResistorRequirement(
                    reference=down_ref,
                    symbol="Device:R",
                    footprint="Resistor_SMD:R_0603_1608Metric",
                    bus_net=line_2,
                    rail_net="GND_BUS",
                    minimum_ohms=600,
                    maximum_ohms=750,
                ),
            )
        elif bias_mode == "remote":
            bias = Rs485RemoteBiasRequirement(
                mode="remote",
                basis="Synthetic remote node provides bus-idle bias",
                reason="Bias resistors are fitted in the remote master assembly.",
            )
        elif bias_mode == "internal_failsafe":
            bias = Rs485InternalFailSafeRequirement(
                mode="internal_failsafe",
                basis="Synthetic reviewed transceiver specification states receiver failsafe",
                transceiver_references=("U20",),
            )
        else:
            bias = Rs485NoBiasRequirement(
                mode="not_required",
                basis="Synthetic board has no local bus-idle bias requirement",
                reason="The deployed system contract covers idle-bus handling externally.",
            )
        if termination_mode == "split":
            midpoint = f"TERM_{pair_id.upper().replace('-', '_')}"
            termination = Rs485TerminationEndpointRequirement(
                id="local-end",
                basis="Two authored resistor legs form the local split termination",
                topology="split",
                midpoint_net=midpoint,
                resistors=(
                    Rs485TerminationResistorRequirement(
                        reference=term_ref,
                        symbol="Device:R",
                        footprint="Resistor_SMD:R_0603_1608Metric",
                        first_net=line_1,
                        second_net=midpoint,
                        minimum_ohms=57,
                        maximum_ohms=63,
                    ),
                    Rs485TerminationResistorRequirement(
                        reference=split_term_ref,
                        symbol="Device:R",
                        footprint="Resistor_SMD:R_0603_1608Metric",
                        first_net=line_2,
                        second_net=midpoint,
                        minimum_ohms=57,
                        maximum_ohms=63,
                    ),
                ),
            )
        else:
            termination = Rs485TerminationEndpointRequirement(
                id="local-end",
                basis="Fitted local endpoint termination",
                topology="direct",
                resistors=(
                    Rs485TerminationResistorRequirement(
                        reference=term_ref,
                        symbol="Device:R",
                        footprint="Resistor_SMD:R_0603_1608Metric",
                        first_net=line_1,
                        second_net=line_2,
                        minimum_ohms=117,
                        maximum_ohms=123,
                    ),
                ),
            )
        remote_termination = Rs485TerminationEndpointRequirement(
            id="remote-end",
            basis="Remote cable endpoint termination is owned by the remote assembly",
            topology="external",
        )
        if dnp_option:
            termination_data = remote_termination.model_dump(mode="python")
            termination_data["expected_dnp_resistors"] = (
                Rs485DnpResistorRequirement(
                    reference="R28",
                    symbol="Device:R",
                    footprint="Resistor_SMD:R_0603_1608Metric",
                    first_net=line_1,
                    second_net=line_2,
                ).model_dump(mode="python"),
            )
            remote_termination = Rs485TerminationEndpointRequirement.model_validate(
                termination_data
            )
        pairs.append(
            Rs485SignalPairRequirement(
                id=pair_id,
                basis="Synthetic project-declared pair mapping",
                purpose=purpose,
                line_1_net=line_1,
                line_2_net=line_2,
                terminations=(termination, remote_termination),
                bias=bias,
            )
        )
    transceiver_pins.extend(
        (
            Rs485EndpointPinRequirement(role="driver_input", pin="U20.5", net="UART_TX"),
            Rs485EndpointPinRequirement(role="receiver_output", pin="U20.6", net="UART_RX"),
            Rs485EndpointPinRequirement(role="driver_enable", pin="U20.7", net="BUS_DIR"),
            Rs485EndpointPinRequirement(role="receiver_enable", pin="U20.8", net="BUS_DIR"),
            Rs485EndpointPinRequirement(
                role="reference", pin="U20.9", net="GND_LOGIC" if isolated else "GND_BUS"
            ),
        )
    )
    if isolated:
        transceiver_pins.append(
            Rs485EndpointPinRequirement(role="reference", pin="U20.10", net="GND_BUS")
        )
    connector_pins.append(Rs485EndpointPinRequirement(role="reference", pin="J20.9", net="GND_BUS"))
    return Rs485Analysis(
        basis="Synthetic authored RS-485 topology, transceiver map, and termination/bias intent",
        buses=(
            Rs485BusRequirement(
                id="fieldbus",
                basis="Synthetic RS-485 bus topology and local endpoint",
                topology=topology,
                pairs=tuple(pairs),
                endpoints=(
                    Rs485EndpointRequirement(
                        id="controller",
                        kind="transceiver",
                        reference="U20",
                        symbol="Synthetic:Rs485Transceiver",
                        footprint="Package_SO:SOIC-16",
                        pins=tuple(transceiver_pins),
                    ),
                    Rs485EndpointRequirement(
                        id="bus-connector",
                        kind="connector",
                        reference="J20",
                        symbol="Synthetic:Rs485Connector",
                        footprint="Connector_Generic:Conn_01x09",
                        pins=tuple(connector_pins),
                    ),
                ),
                external_peers=external_peers,
            ),
        ),
    )


def rs485_netlist(
    spec: Rs485Analysis,
    *,
    fault: Literal[
        "endpoint-line-wrong-net",
        "endpoint-reference-wrong-net",
        "termination-dnp",
        "termination-wrong-net",
        "bias-dnp",
        "bias-wrong-net",
        "dnp-option-fitted",
        "identity-wrong",
    ]
    | None = None,
) -> NetlistContract:
    assignments: dict[str, str] = {}
    components: dict[str, ComponentContract] = {}
    symbols: dict[str, str] = {}
    pin_numbers: dict[str, set[str]] = {}
    pin_functions: dict[str, str] = {}
    dnp: set[str] = set()

    def add_pin(pin: str, net: str, role: str) -> None:
        reference, number = pin.rsplit(".", 1)
        pin_numbers.setdefault(reference, set()).add(number)
        pin_functions[pin] = role
        assignments[pin] = net

    resistor_values: dict[str, tuple[str, str, str, str]] = {}
    for bus in spec.buses:
        for endpoint in bus.endpoints:
            components[endpoint.reference] = ComponentContract(
                value=f"Synthetic {endpoint.kind}", footprint=endpoint.footprint
            )
            symbols[endpoint.reference] = endpoint.symbol
            for pin in endpoint.pins:
                add_pin(pin.pin, pin.net, pin.role)
        for pair in bus.pairs:
            for endpoint in pair.terminations:
                for resistor in endpoint.resistors:
                    resistor_values[resistor.reference] = (
                        f"{(resistor.minimum_ohms + resistor.maximum_ohms) / 2:g}R",
                        resistor.first_net,
                        resistor.second_net,
                        resistor.footprint,
                    )
                    symbols[resistor.reference] = resistor.symbol
                for resistor in endpoint.expected_dnp_resistors:
                    resistor_values[resistor.reference] = (
                        "120R",
                        resistor.first_net,
                        resistor.second_net,
                        resistor.footprint,
                    )
                    symbols[resistor.reference] = resistor.symbol
                    dnp.add(resistor.reference)
            if isinstance(pair.bias, Rs485LocalBiasRequirement):
                for resistor in (pair.bias.pull_up, pair.bias.pull_down):
                    resistor_values[resistor.reference] = (
                        "680R",
                        resistor.bus_net,
                        resistor.rail_net,
                        resistor.footprint,
                    )
                    symbols[resistor.reference] = resistor.symbol
    for reference, (value, first_net, second_net, footprint) in resistor_values.items():
        components[reference] = ComponentContract(value=value, footprint=footprint)
        pin_numbers[reference] = {"1", "2"}
        pin_functions[f"{reference}.1"] = "1"
        pin_functions[f"{reference}.2"] = "2"
        assignments[f"{reference}.1"] = first_net
        assignments[f"{reference}.2"] = second_net

    if fault == "endpoint-line-wrong-net":
        assignments["U20.1"] = "WRONG_PAIR"
    elif fault == "endpoint-reference-wrong-net":
        assignments["J20.9"] = "GND_OTHER"
    elif fault == "termination-dnp":
        dnp.add("R20")
    elif fault == "termination-wrong-net":
        assignments["R20.2"] = "WRONG_PAIR"
    elif fault == "bias-dnp":
        dnp.add("R21")
    elif fault == "bias-wrong-net":
        assignments["R22.2"] = "WRONG_REFERENCE"
    elif fault == "identity-wrong":
        symbols["U20"] = "Synthetic:DifferentTransceiver"
    elif fault == "dnp-option-fitted":
        dnp.discard("R28")

    nets: dict[str, list[str]] = {}
    for pin, net in assignments.items():
        nets.setdefault(net, []).append(pin)
    return NetlistContract(
        components=components,
        nets={net: tuple(sorted(pins)) for net, pins in nets.items()},
        dnp_components=tuple(sorted(dnp)),
        component_symbols=symbols,
        pin_functions=pin_functions,
        component_pin_numbers={
            reference: tuple(sorted(numbers)) for reference, numbers in pin_numbers.items()
        },
    )


def power_connectivity_requirement(
    *, source_selection: Literal["all", "any"] = "all"
) -> PowerConnectivityAnalysis:
    source_endpoints = (
        PowerPinEndpointRequirement(
            id="barrel-input",
            reference="J40",
            symbol="Synthetic:PowerInput",
            footprint="Connector_BarrelJack:BarrelJack_Horizontal",
            pins=("J40.1",),
        ),
        PowerPinEndpointRequirement(
            id="terminal-input",
            reference="J41",
            symbol="Synthetic:PowerInput",
            footprint="Connector_Generic:Conn_01x02",
            pins=("J41.1",),
        ),
    )
    return PowerConnectivityAnalysis(
        basis="Synthetic reviewed source and load pin map",
        rails=(
            PowerConnectivityRailRequirement(
                id="supply",
                basis="Reviewed unregulated input rail",
                net="VIN_IN",
                source_groups=(
                    PowerSourceGroupRequirement(
                        id="approved-inputs",
                        basis="At least one approved input connector is populated",
                        selection=source_selection,
                        endpoints=source_endpoints,
                    ),
                ),
                loads=(
                    PowerLoadConnectivityRequirement(
                        id="load",
                        basis="Budgeted input load includes regulator and monitor pins",
                        endpoints=(
                            PowerPinEndpointRequirement(
                                id="regulator",
                                reference="U40",
                                symbol="Synthetic:PowerRegulator",
                                footprint="Package_SO:SOIC-8",
                                pins=("U40.1",),
                            ),
                            PowerPinEndpointRequirement(
                                id="monitor",
                                reference="U41",
                                symbol="Synthetic:VoltageMonitor",
                                footprint="Package_SOT:SOT-23-5",
                                pins=("U41.1",),
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )


def power_connectivity_netlist(
    *,
    fault: Literal[
        "source-wrong-net",
        "load-wrong-net",
        "source-dnp",
        "all-sources-dnp",
        "source-identity-wrong",
    ]
    | None = None,
) -> NetlistContract:
    components = {
        "J40": ComponentContract(
            value="Synthetic barrel input", footprint="Connector_BarrelJack:BarrelJack_Horizontal"
        ),
        "J41": ComponentContract(
            value="Synthetic terminal input", footprint="Connector_Generic:Conn_01x02"
        ),
        "U40": ComponentContract(value="Synthetic regulator", footprint="Package_SO:SOIC-8"),
        "U41": ComponentContract(value="Synthetic monitor", footprint="Package_SOT:SOT-23-5"),
    }
    symbols = {
        "J40": "Synthetic:PowerInput",
        "J41": "Synthetic:PowerInput",
        "U40": "Synthetic:PowerRegulator",
        "U41": "Synthetic:VoltageMonitor",
    }
    assignments = {
        "J40.1": "VIN_IN",
        "J41.1": "VIN_IN",
        "U40.1": "VIN_IN",
        "U41.1": "VIN_IN",
    }
    dnp: set[str] = set()
    if fault == "source-wrong-net":
        assignments["J40.1"] = "WRONG_INPUT"
    elif fault == "load-wrong-net":
        assignments["U40.1"] = "WRONG_INPUT"
    elif fault == "source-dnp":
        dnp.add("J40")
    elif fault == "all-sources-dnp":
        dnp.update(("J40", "J41"))
    elif fault == "source-identity-wrong":
        symbols["J40"] = "Synthetic:DifferentConnector"
    nets: dict[str, list[str]] = {}
    for pin, net in assignments.items():
        nets.setdefault(net, []).append(pin)
    return NetlistContract(
        components=components,
        nets={net: tuple(sorted(pins)) for net, pins in nets.items()},
        dnp_components=tuple(sorted(dnp)),
        component_symbols=symbols,
        pin_functions={pin: pin.rsplit(".", 1)[1] for pin in assignments},
        component_pin_numbers={reference: ("1",) for reference in components},
    )


def install_fixture(root: Path, version: str = "47") -> ElectricalAnalysisContract:
    """Author synthetic requirements only in a disposable copy of the training island."""
    from tests.support import template_root

    template = template_root()
    directory = root / ISLAND / "tests/electrical"
    directory.mkdir(parents=True)
    for name in ("startup.cir", "signal.cir"):
        shutil.copy2(template / "templates/electrical" / name, directory / name)
    config = selected_config(root, PROJECT)
    source = hashes(root, config.source_roots)

    def model(name: str) -> dict[str, str]:
        path = directory / name
        return {path.relative_to(root).as_posix(): digest(path)}

    startup_model = model("startup.cir")
    signal_model = model("signal.cir")
    startup = TransientAnalysis(
        id="startup",
        basis="Synthetic 5 V source ramp into 100 uF through 1 ohm",
        deck=next(iter(startup_model)),
        source_sha256=source,
        model_sha256=startup_model,
        step_s=1e-6,
        stop_s=0.005,
        measures=(
            SimulationMeasure(
                id="peak-current",
                expression="-i(vrail)",
                statistic="max",
                unit="A",
                start=0.0,
                stop=0.001,
                maximum=5.1,
            ),
        ),
    )
    steady = startup.model_copy(
        update={
            "id": "steady-state",
            "measures": (
                SimulationMeasure(
                    id="average-current",
                    expression="-i(vrail)",
                    statistic="avg",
                    unit="A",
                    start=0.004,
                    stop=0.005,
                    minimum=0.049,
                    maximum=0.051,
                ),
                SimulationMeasure(
                    id="average-power",
                    expression="-v(supply)*i(vrail)",
                    statistic="avg",
                    unit="W",
                    start=0.004,
                    stop=0.005,
                    minimum=0.24,
                    maximum=0.26,
                ),
                SimulationMeasure(
                    id="rail-minimum",
                    expression="v(out)",
                    statistic="min",
                    unit="V",
                    start=0.004,
                    stop=0.005,
                    minimum=4.9,
                ),
            ),
        }
    )
    sweep = FrequencyAnalysis(
        id="passband",
        basis="Synthetic 50 ohm/10 pF first-order low-pass",
        deck=next(iter(signal_model)),
        source_sha256=source,
        model_sha256=signal_model,
        start_hz=1000.0,
        stop_hz=1e9,
        measures=(
            SimulationMeasure(
                id="gain",
                expression="db(v(out)/v(in))",
                statistic="min",
                unit="dB",
                start=1000.0,
                stop=1e6,
                minimum=-0.1,
                maximum=0.0,
            ),
        ),
    )
    waveform = TransientAnalysis(
        id="edges",
        basis="Synthetic 1 MHz source with 1 ns rise and fall times",
        deck=sweep.deck,
        source_sha256=source,
        model_sha256=signal_model,
        step_s=1e-10,
        stop_s=3e-6,
        measures=(
            SimulationMeasure(
                id="overshoot",
                expression="v(out)",
                statistic="max",
                unit="V",
                start=0.0,
                stop=3e-6,
                minimum=0.99,
                maximum=1.01,
            ),
        ),
    )
    contract = ElectricalAnalysisContract(
        project_id=PROJECT,
        ngspice_version=version,
        grounding=GroundingAnalysis(
            basis="Synthetic reference net, not protective earth",
            domains=(GroundDomain(net="PILOT_B", pins=("R1.2", "R2.2")),),
        ),
        pcb_return_paths=NA,
        power=PowerAnalysis(
            rails=(
                PowerRail(
                    id="supply",
                    basis="Synthetic derated supply and path limits",
                    voltage_v=5.0,
                    continuous_limit_a=0.1,
                    peak_limit_a=6.0,
                    peak_duration_limit_s=0.002,
                    loads=(
                        PowerLoad(
                            id="load",
                            basis="Synthetic worst case",
                            steady_a=0.05,
                            startup_a=5.0,
                            startup_s=0.001,
                        ),
                    ),
                ),
            ),
            startup=(startup,),
            steady_state=(steady,),
        ),
        high_frequency=HighFrequencyAnalysis(
            basis="Synthetic model only",
            frequency_hz=1e6,
            rise_time_s=1e-9,
            sweeps=(sweep,),
            waveforms=(waveform,),
        ),
        test_access=NA,
    )
    path = root / ISLAND / "tests/electrical.json"
    write_model(path, contract)
    test_path = root / ISLAND / "tests/contract.json"
    raw = json.loads(test_path.read_text())
    raw["electrical"] = "tests/electrical.json"
    test_path.write_text(json.dumps(raw))
    return contract


class ElectricalTests(unittest.TestCase):
    def stage(self) -> Path:
        from tests.support import reference_root

        temporary = tempfile.TemporaryDirectory(prefix="electrical-test-")
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name) / "repository"
        shutil.copytree(reference_root(), root)
        return root

    def test_rs485_contract_checks_authored_pair_termination_bias_and_faults(self) -> None:
        spec = rs485_requirement()
        checks = {item.id: item for item in rs485_checks(spec, rs485_netlist(spec))}
        self.assertTrue(all(item.status in {"PASS", "NOT_APPLICABLE"} for item in checks.values()))
        self.assertEqual(checks["rs485/fieldbus/endpoint/controller/identity"].status, "PASS")
        self.assertEqual(checks["rs485/fieldbus/endpoint/bus-connector/pins"].status, "PASS")
        self.assertEqual(checks["rs485/fieldbus/pair/shared/membership"].status, "PASS")
        self.assertEqual(checks["rs485/fieldbus/pair/shared/termination/local-end"].observed, 120)
        self.assertEqual(checks["rs485/fieldbus/pair/shared/bias"].status, "PASS")

        fault_expectations = {
            "endpoint-line-wrong-net": (
                "rs485/fieldbus/endpoint/controller/pins",
                "FAIL",
            ),
            "endpoint-reference-wrong-net": (
                "rs485/fieldbus/endpoint/bus-connector/pins",
                "FAIL",
            ),
            "termination-dnp": (
                "rs485/fieldbus/pair/shared/termination/local-end",
                "FAIL",
            ),
            "termination-wrong-net": (
                "rs485/fieldbus/pair/shared/termination/local-end",
                "FAIL",
            ),
            "bias-dnp": ("rs485/fieldbus/pair/shared/bias", "FAIL"),
            "bias-wrong-net": ("rs485/fieldbus/pair/shared/bias", "FAIL"),
            "identity-wrong": ("rs485/fieldbus/endpoint/controller/identity", "FAIL"),
        }
        for fault, (check_id, status) in fault_expectations.items():
            with self.subTest(fault=fault):
                rows = {
                    item.id: item for item in rs485_checks(spec, rs485_netlist(spec, fault=fault))
                }
                self.assertEqual(rows[check_id].status, status)

        split = rs485_requirement(termination_mode="split")
        split_checks = {item.id: item for item in rs485_checks(split, rs485_netlist(split))}
        self.assertEqual(
            split_checks["rs485/fieldbus/pair/shared/termination/local-end"].status, "PASS"
        )
        self.assertEqual(
            split_checks["rs485/fieldbus/pair/shared/termination/local-end"].observed, 120
        )

        optional = rs485_requirement(dnp_option=True)
        optional_checks = {
            item.id: item for item in rs485_checks(optional, rs485_netlist(optional))
        }
        self.assertEqual(
            optional_checks["rs485/fieldbus/pair/shared/termination/remote-end/dnp-options"].status,
            "PASS",
        )
        fitted_option = {
            item.id: item
            for item in rs485_checks(optional, rs485_netlist(optional, fault="dnp-option-fitted"))
        }
        self.assertEqual(
            fitted_option["rs485/fieldbus/pair/shared/termination/remote-end/dnp-options"].status,
            "FAIL",
        )

    def test_rs485_contract_records_duplex_isolation_and_bias_applicability(self) -> None:
        full_duplex = rs485_requirement(
            topology="four_wire_full_duplex",
            termination_mode="split",
            bias_mode="internal_failsafe",
            isolated=True,
            external_peers=("Remote controller pin map not supplied",),
        )
        checks = {item.id: item for item in rs485_checks(full_duplex, rs485_netlist(full_duplex))}
        self.assertTrue(all(item.status in {"PASS", "NOT_APPLICABLE"} for item in checks.values()))
        for pair_id in ("board-to-peer", "peer-to-board"):
            self.assertEqual(checks[f"rs485/fieldbus/pair/{pair_id}/membership"].status, "PASS")
            self.assertEqual(
                checks[f"rs485/fieldbus/pair/{pair_id}/termination/local-end"].status,
                "PASS",
            )
            internal = checks[f"rs485/fieldbus/pair/{pair_id}/bias"]
            self.assertEqual(internal.status, "NOT_APPLICABLE")
            self.assertIn("not verified from the netlist", internal.detail)
        self.assertEqual(checks["rs485/fieldbus/endpoint/controller/pins"].status, "PASS")
        self.assertTrue(
            any(
                item.status == "NOT_APPLICABLE"
                and "remote controller pin map not supplied" in item.detail.casefold()
                for item in checks.values()
            )
        )

        for bias_mode in ("remote", "not_required"):
            with self.subTest(bias_mode=bias_mode):
                declared = rs485_requirement(bias_mode=bias_mode)
                rows = {item.id: item for item in rs485_checks(declared, rs485_netlist(declared))}
                self.assertEqual(rows["rs485/fieldbus/pair/shared/bias"].status, "NOT_APPLICABLE")

        bus = rs485_requirement().buses[0]
        with self.assertRaisesRegex(ValueError, "Four-wire RS-485 needs"):
            Rs485BusRequirement(
                id=bus.id,
                basis=bus.basis,
                topology="four_wire_full_duplex",
                pairs=bus.pairs,
                endpoints=bus.endpoints,
            )

    def test_power_connectivity_checks_authored_sources_loads_and_alternatives(self) -> None:
        spec = power_connectivity_requirement()
        checks = {
            item.id: item for item in power_connectivity_checks(spec, power_connectivity_netlist())
        }
        self.assertTrue(all(item.status == "PASS" for item in checks.values()))
        self.assertEqual(
            checks["power-connectivity/supply/source/approved-inputs"].status,
            "PASS",
        )
        self.assertEqual(
            checks["power-connectivity/supply/load/load"].status,
            "PASS",
        )
        fault_expectations = {
            "source-wrong-net": "power-connectivity/supply/source/approved-inputs",
            "load-wrong-net": "power-connectivity/supply/load/load",
            "source-dnp": "power-connectivity/supply/source/approved-inputs",
            "source-identity-wrong": "power-connectivity/supply/source/approved-inputs",
        }
        for fault, check_id in fault_expectations.items():
            with self.subTest(fault=fault):
                rows = {
                    item.id: item
                    for item in power_connectivity_checks(
                        spec, power_connectivity_netlist(fault=fault)
                    )
                }
                self.assertEqual(rows[check_id].status, "FAIL")

        alternatives = power_connectivity_requirement(source_selection="any")
        one_available = {
            item.id: item
            for item in power_connectivity_checks(
                alternatives, power_connectivity_netlist(fault="source-dnp")
            )
        }
        self.assertEqual(
            one_available["power-connectivity/supply/source/approved-inputs"].status,
            "PASS",
        )
        none_available = {
            item.id: item
            for item in power_connectivity_checks(
                alternatives, power_connectivity_netlist(fault="all-sources-dnp")
            )
        }
        self.assertEqual(
            none_available["power-connectivity/supply/source/approved-inputs"].status,
            "FAIL",
        )

    def test_power_connectivity_map_covers_power_budget_rail_and_load_ids(self) -> None:
        root = self.stage()
        contract = install_fixture(root)
        source_rail = power_connectivity_requirement().rails[0]
        mapped = PowerConnectivityAnalysis(
            basis="Synthetic connectivity map matched to its budget",
            rails=(
                PowerConnectivityRailRequirement(
                    id="supply",
                    basis="Existing budget rail with exact schematic membership",
                    net="VIN_IN",
                    source_groups=source_rail.source_groups,
                    loads=(
                        PowerLoadConnectivityRequirement(
                            id="load",
                            basis="Existing budget load covers both selected components",
                            endpoints=tuple(
                                endpoint
                                for load in source_rail.loads
                                for endpoint in load.endpoints
                            ),
                        ),
                    ),
                ),
            ),
        )
        raw = json.loads(contract.model_dump_json())
        raw["power_connectivity"] = json.loads(mapped.model_dump_json())
        validated = ElectricalAnalysisContract.model_validate_json(json.dumps(raw))
        self.assertIsNotNone(validated.power_connectivity)

        raw["power_connectivity"]["rails"][0]["loads"][0]["id"] = "unbudgeted-load"
        with self.assertRaisesRegex(ValueError, "load IDs must match"):
            ElectricalAnalysisContract.model_validate_json(json.dumps(raw))

    def test_can_contract_checks_both_declared_direct_endpoints_and_detects_extra_parts(
        self,
    ) -> None:
        checks = {
            item.id: item
            for item in can_termination_checks(
                can_termination_requirement(), can_termination_netlist()
            )
        }
        self.assertEqual(checks["can-termination/fieldbus/local-a"].status, "PASS")
        self.assertEqual(checks["can-termination/fieldbus/local-b"].status, "PASS")
        self.assertEqual(checks["can-termination/fieldbus/unlisted-direct"].status, "PASS")
        self.assertEqual(checks["can-termination/fieldbus/signal-pins"].status, "PASS")

        misassigned_pins = can_termination_netlist().model_copy(
            update={
                "nets": {
                    "CAN_H": ("R1.1", "R2.1"),
                    "CAN_L": ("U1.2", "R1.2", "R2.2"),
                    "OTHER": ("U1.1",),
                }
            }
        )
        pin_check = {
            item.id: item
            for item in can_termination_checks(can_termination_requirement(), misassigned_pins)
        }["can-termination/fieldbus/signal-pins"]
        self.assertEqual(pin_check.status, "FAIL")
        self.assertIn("U1.1 is assigned to OTHER", pin_check.detail)

        stale_pin_check = {
            item.id: item
            for item in can_termination_checks(
                can_termination_requirement(high_pin="U9.7"), can_termination_netlist()
            )
        }["can-termination/fieldbus/signal-pins"]
        self.assertEqual(stale_pin_check.status, "FAIL")
        self.assertIn("U9.7 is absent", stale_pin_check.detail)

        boundary = can_termination_netlist(
            {"R1": ("108R", "CAN_H", "CAN_L"), "R2": ("132R", "CAN_H", "CAN_L")}
        )
        boundary_checks = {
            item.id: item
            for item in can_termination_checks(can_termination_requirement(), boundary)
        }
        self.assertEqual(boundary_checks["can-termination/fieldbus/local-a"].status, "PASS")
        self.assertEqual(boundary_checks["can-termination/fieldbus/local-b"].status, "PASS")

        no_termination = can_termination_netlist(paths={})
        no_termination_checks = {
            item.id
            for item in can_termination_checks(can_termination_requirement(), no_termination)
            if item.status == "FAIL"
        }
        self.assertIn("can-termination/fieldbus/local-a", no_termination_checks)
        self.assertIn("can-termination/fieldbus/local-b", no_termination_checks)

        missing = can_termination_netlist(paths={"R1": ("120R", "CAN_H", "CAN_L")})
        missing_checks = {
            item.id: item for item in can_termination_checks(can_termination_requirement(), missing)
        }
        self.assertEqual(missing_checks["can-termination/fieldbus/local-b"].status, "FAIL")
        self.assertIn("R2 is absent", missing_checks["can-termination/fieldbus/local-b"].detail)

        dnp = can_termination_netlist(dnp=("R1",))
        dnp_checks = {
            item.id: item for item in can_termination_checks(can_termination_requirement(), dnp)
        }
        self.assertEqual(dnp_checks["can-termination/fieldbus/local-a"].status, "FAIL")
        self.assertIn("R1 is DNP", dnp_checks["can-termination/fieldbus/local-a"].detail)

        low_value = can_termination_netlist(
            {"R1": ("100R", "CAN_H", "CAN_L"), "R2": ("120R", "CAN_H", "CAN_L")}
        )
        value_checks = {
            item.id
            for item in can_termination_checks(can_termination_requirement(), low_value)
            if item.status == "FAIL"
        }
        self.assertIn("can-termination/fieldbus/local-a", value_checks)

        extra = can_termination_netlist(
            {
                "R1": ("120R", "CAN_H", "CAN_L"),
                "R2": ("120R", "CAN_H", "CAN_L"),
                "R3": ("60R", "CAN_H", "CAN_L"),
            }
        )
        extra_checks = {
            item.id: item for item in can_termination_checks(can_termination_requirement(), extra)
        }
        self.assertEqual(extra_checks["can-termination/fieldbus/unlisted-direct"].status, "FAIL")
        self.assertIn("R3=60Ω", extra_checks["can-termination/fieldbus/unlisted-direct"].detail)

    def test_can_contract_checks_split_network_and_external_dnp_option(self) -> None:
        split = CanTerminationAnalysis(
            basis="Synthetic split termination requirement",
            buses=(
                CanTerminationBusRequirement(
                    id="fieldbus",
                    basis="Synthetic test bus",
                    high_net="CAN_H",
                    low_net="CAN_L",
                    high_pins=("U1.1",),
                    low_pins=("U1.2",),
                    endpoints=(
                        CanTerminationEndpointRequirement(
                            id="local",
                            basis="Two equal legs meet at the declared midpoint",
                            topology="split",
                            midpoint_net="CAN_TERM_MID",
                            resistors=(
                                CanTerminationResistorRequirement(
                                    reference="R4",
                                    first_net="CAN_H",
                                    second_net="CAN_TERM_MID",
                                    minimum_ohms=54,
                                    maximum_ohms=66,
                                ),
                                CanTerminationResistorRequirement(
                                    reference="R5",
                                    first_net="CAN_L",
                                    second_net="CAN_TERM_MID",
                                    minimum_ohms=54,
                                    maximum_ohms=66,
                                ),
                            ),
                        ),
                    ),
                ),
            ),
        )
        split_paths = {
            "R4": ("60R", "CAN_H", "CAN_TERM_MID"),
            "R5": ("60R", "CAN_L", "CAN_TERM_MID"),
        }
        checks = {
            item.id: item
            for item in can_termination_checks(split, can_termination_netlist(split_paths))
        }
        self.assertEqual(checks["can-termination/fieldbus/local"].status, "PASS")
        self.assertEqual(checks["can-termination/fieldbus/local"].observed, 120)
        self.assertNotIn("can-termination/fieldbus/local/midpoint-capacitor", checks)

        midpoint_capacitor = CanTerminationMidpointCapacitorRequirement(
            reference="C1",
            expected_symbol="Device:C",
            expected_footprint="Synthetic:CAP",
            midpoint_pin="C1.1",
            reference_pin="C1.2",
            reference_net="GND",
            minimum_nominal_capacitance_pf=90,
            maximum_nominal_capacitance_pf=110,
        )
        split_with_cap_data = split.model_dump()
        split_with_cap_data["buses"][0]["endpoints"][0]["midpoint_capacitor"] = (
            midpoint_capacitor.model_dump()
        )
        split_with_capacitor = CanTerminationAnalysis.model_validate(split_with_cap_data)
        self.assertEqual(
            CanTerminationAnalysis.model_validate_json(split_with_capacitor.model_dump_json()),
            split_with_capacitor,
        )
        cap_paths = can_termination_netlist(
            split_paths, midpoint_capacitor=("C1", "100pF", "CAN_TERM_MID", "GND")
        )
        cap_checks = {
            item.id: item for item in can_termination_checks(split_with_capacitor, cap_paths)
        }
        cap_check_id = "can-termination/fieldbus/local/midpoint-capacitor"
        self.assertEqual(cap_checks[cap_check_id].status, "PASS")
        self.assertEqual(cap_checks[cap_check_id].observed, 100)

        for value in ("90pF", "110pF"):
            boundary_cap = can_termination_netlist(
                split_paths, midpoint_capacitor=("C1", value, "CAN_TERM_MID", "GND")
            )
            self.assertEqual(
                {
                    item.id: item
                    for item in can_termination_checks(split_with_capacitor, boundary_cap)
                }[cap_check_id].status,
                "PASS",
            )

        missing_cap_checks = {
            item.id: item
            for item in can_termination_checks(
                split_with_capacitor, can_termination_netlist(split_paths)
            )
        }
        self.assertEqual(missing_cap_checks[cap_check_id].status, "FAIL")
        self.assertIn("C1 is absent", missing_cap_checks[cap_check_id].detail)

        wrong_value = can_termination_netlist(
            split_paths, midpoint_capacitor=("C1", "120pF", "CAN_TERM_MID", "GND")
        )
        wrong_value_check = {
            item.id: item for item in can_termination_checks(split_with_capacitor, wrong_value)
        }[cap_check_id]
        self.assertEqual(wrong_value_check.status, "FAIL")
        self.assertIn("outside 90–110pF", wrong_value_check.detail)

        dnp_cap = can_termination_netlist(
            split_paths,
            dnp=("C1",),
            midpoint_capacitor=("C1", "100pF", "CAN_TERM_MID", "GND"),
        )
        self.assertIn(
            "C1 is DNP",
            {item.id: item for item in can_termination_checks(split_with_capacitor, dnp_cap)}[
                cap_check_id
            ].detail,
        )

        wrong_cap_identity = cap_paths.model_copy(
            update={
                "component_symbols": {**cap_paths.component_symbols, "C1": "Device:R"},
                "components": {
                    **cap_paths.components,
                    "C1": ComponentContract(value="100pF", footprint="Synthetic:WRONG"),
                },
            }
        )
        identity_check = {
            item.id: item
            for item in can_termination_checks(split_with_capacitor, wrong_cap_identity)
        }[cap_check_id]
        self.assertEqual(identity_check.status, "FAIL")
        self.assertIn("symbol is Device:R", identity_check.detail)
        self.assertIn("expected Synthetic:CAP", identity_check.detail)

        wrong_cap_net = cap_paths.model_copy(
            update={
                "nets": {
                    **cap_paths.nets,
                    "GND": (),
                    "OTHER": ("C1.2",),
                }
            }
        )
        net_check = {
            item.id: item for item in can_termination_checks(split_with_capacitor, wrong_cap_net)
        }[cap_check_id]
        self.assertEqual(net_check.status, "FAIL")
        self.assertIn("C1.2 is assigned to OTHER", net_check.detail)

        missing_cap_inventory = cap_paths.model_copy(
            update={
                "component_pin_numbers": {
                    reference: numbers
                    for reference, numbers in cap_paths.component_pin_numbers.items()
                    if reference != "C1"
                }
            }
        )
        self.assertIn(
            "C1 native pin inventory is missing",
            {
                item.id: item
                for item in can_termination_checks(split_with_capacitor, missing_cap_inventory)
            }[cap_check_id].detail,
        )

        wrong_topology = can_termination_netlist(
            {
                "R4": ("60R", "CAN_H", "CAN_TERM_MID"),
                "R5": ("60R", "CAN_L", "CAN_H"),
            }
        )
        wrong_checks = {item.id: item for item in can_termination_checks(split, wrong_topology)}
        self.assertEqual(wrong_checks["can-termination/fieldbus/local"].status, "FAIL")

        external = CanTerminationAnalysis(
            basis="Synthetic bus is externally terminated in this assembly",
            buses=(
                CanTerminationBusRequirement(
                    id="fieldbus",
                    basis="Synthetic external termination declaration",
                    high_net="CAN_H",
                    low_net="CAN_L",
                    high_pins=("U1.1",),
                    low_pins=("U1.2",),
                    endpoints=(
                        CanTerminationEndpointRequirement(
                            id="remote",
                            basis="Remote equipment owns this bus-end terminator",
                            topology="external",
                            expected_dnp_resistors=("R9",),
                        ),
                    ),
                ),
            ),
        )
        external_netlist = can_termination_netlist({"R9": ("120R", "CAN_H", "CAN_L")}, dnp=("R9",))
        external_checks = {
            item.id: item for item in can_termination_checks(external, external_netlist)
        }
        self.assertEqual(
            external_checks["can-termination/fieldbus/remote/external-evidence"].status,
            "NOT_APPLICABLE",
        )
        self.assertEqual(
            external_checks["can-termination/fieldbus/remote/dnp-options"].status, "PASS"
        )

        misassigned_dnp = external_netlist.model_copy(
            update={
                "nets": {
                    "CAN_H": ("U1.1", "R9.1"),
                    "CAN_L": ("U1.2",),
                    "OTHER": ("R9.2",),
                }
            }
        )
        misassigned_dnp_checks = {
            item.id: item for item in can_termination_checks(external, misassigned_dnp)
        }
        self.assertEqual(
            misassigned_dnp_checks["can-termination/fieldbus/remote/dnp-options"].status,
            "FAIL",
        )

        external_bus_pin_missing = external_netlist.model_copy(
            update={
                "nets": {
                    "CAN_H": ("R9.1",),
                    "CAN_L": ("U1.2", "R9.2"),
                    "OTHER": ("U1.1",),
                }
            }
        )
        external_pin_checks = {
            item.id: item for item in can_termination_checks(external, external_bus_pin_missing)
        }
        self.assertEqual(external_pin_checks["can-termination/fieldbus/signal-pins"].status, "FAIL")
        self.assertEqual(
            external_pin_checks["can-termination/fieldbus/remote/external-evidence"].status,
            "NOT_APPLICABLE",
        )

        fitted_option = can_termination_netlist({"R9": ("120R", "CAN_H", "CAN_L")})
        fitted_checks = {item.id: item for item in can_termination_checks(external, fitted_option)}
        self.assertEqual(
            fitted_checks["can-termination/fieldbus/remote/dnp-options"].status, "FAIL"
        )
        self.assertEqual(fitted_checks["can-termination/fieldbus/unlisted-direct"].status, "FAIL")

    def test_can_termination_contract_rejects_incomplete_and_crossed_topologies(self) -> None:
        with self.assertRaisesRegex(ValueError, "Direct CAN termination needs one resistor"):
            CanTerminationEndpointRequirement(
                id="missing-part",
                basis="Invalid synthetic direct requirement",
                topology="direct",
            )
        with self.assertRaisesRegex(ValueError, "Only split CAN termination"):
            CanTerminationEndpointRequirement(
                id="direct-with-cap",
                basis="Invalid synthetic direct requirement",
                topology="direct",
                resistors=(
                    CanTerminationResistorRequirement(
                        reference="R1",
                        first_net="CAN_H",
                        second_net="CAN_L",
                        minimum_ohms=108,
                        maximum_ohms=132,
                    ),
                ),
                midpoint_capacitor=CanTerminationMidpointCapacitorRequirement(
                    reference="C1",
                    expected_symbol="Device:C",
                    expected_footprint="Synthetic:CAP",
                    midpoint_pin="C1.1",
                    reference_pin="C1.2",
                    reference_net="GND",
                    minimum_nominal_capacitance_pf=90,
                    maximum_nominal_capacitance_pf=110,
                ),
            )
        with self.assertRaisesRegex(ValueError, "each bus net to one midpoint"):
            CanTerminationBusRequirement(
                id="fieldbus",
                basis="Invalid synthetic split requirement",
                high_net="CAN_H",
                low_net="CAN_L",
                high_pins=("U1.1",),
                low_pins=("U1.2",),
                endpoints=(
                    CanTerminationEndpointRequirement(
                        id="local",
                        basis="Two legs are required",
                        topology="split",
                        midpoint_net="CAN_TERM_MID",
                        resistors=(
                            CanTerminationResistorRequirement(
                                reference="R4",
                                first_net="CAN_H",
                                second_net="CAN_TERM_MID",
                                minimum_ohms=54,
                                maximum_ohms=66,
                            ),
                            CanTerminationResistorRequirement(
                                reference="R5",
                                first_net="CAN_L",
                                second_net="CAN_H",
                                minimum_ohms=54,
                                maximum_ohms=66,
                            ),
                        ),
                    ),
                ),
            )

    def test_strict_contract_round_trip_and_schema(self) -> None:
        root = self.stage()
        contract = install_fixture(root)
        path = root / ISLAND / "tests/electrical.json"
        self.assertEqual(read_model(path, ElectricalAnalysisContract), contract)
        schema = json.loads(expected_outputs(root)["schemas/electrical-analysis-v1.schema.json"])
        self.assertEqual(schema, ElectricalAnalysisContract.model_json_schema())
        for key, value in (("schema_version", "2"), ("unknown", True), ("ngspice_version", 47)):
            raw = json.loads(contract.model_dump_json())
            raw[key] = value
            path.write_text(json.dumps(raw))
            with self.assertRaises(ValueError):
                read_model(path, ElectricalAnalysisContract)

    def test_invalid_ground_duplicates_windows_limits_and_model_bindings(self) -> None:
        root = self.stage()
        contract = install_fixture(root)
        mutations = (
            lambda d: d["grounding"]["domains"][0]["pins"].append("R1.2"),
            lambda d: d["power"]["startup"][0]["measures"][0].update(minimum=6.0),
            lambda d: d["power"]["startup"][0].update(step_s=1.0),
            lambda d: d["power"]["startup"][0].update(source_sha256={}),
            lambda d: d["high_frequency"]["waveforms"][0].update(step_s=1e-7),
            lambda d: d["high_frequency"]["sweeps"][0].update(stop_hz=1.0),
            lambda d: d["power"]["startup"][0]["measures"][0].update(expression="v(out)\nquit"),
            lambda d: d["power"]["steady_state"][0].update(id="startup"),
            lambda d: d["power"]["steady_state"][0]["measures"][1].update(unit="A"),
        )
        for mutation in mutations:
            raw = json.loads(contract.model_dump_json())
            mutation(raw)
            with self.assertRaises(ValueError):
                ElectricalAnalysisContract.model_validate_json(json.dumps(raw))

    def test_budgets_reject_steady_peak_and_excess_peak_duration(self) -> None:
        root = self.stage()
        spec = install_fixture(root).power
        assert isinstance(spec, PowerAnalysis)
        self.assertTrue(all(c.status == "PASS" for c in power_budget_checks(spec)))
        for field, value, expected in (
            ("continuous_limit_a", 0.01, "steady-current"),
            ("peak_limit_a", 1.0, "startup-current"),
            ("peak_duration_limit_s", 1e-5, "startup-duration"),
        ):
            changed = spec.model_copy(
                update={"rails": (spec.rails[0].model_copy(update={field: value}),)}
            )
            failures = [c.id for c in power_budget_checks(changed) if c.status == "FAIL"]
            self.assertIn(f"power/supply/{expected}", failures)

    def test_zero_startup_current_cannot_hide_steady_load(self) -> None:
        root = self.stage()
        spec = install_fixture(root).power
        assert isinstance(spec, PowerAnalysis)
        load = spec.rails[0].loads[0].model_copy(update={"startup_a": 0.0})
        changed = spec.model_copy(
            update={"rails": (spec.rails[0].model_copy(update={"loads": (load,)}),)}
        )
        check = next(c for c in power_budget_checks(changed) if c.id.endswith("startup-current"))
        self.assertEqual(check.observed, 0.05)

    def test_binding_rejects_changed_source_model_wrong_project_and_escaping_contract(self) -> None:
        for kind in ("source", "model", "identity", "path"):
            with self.subTest(kind=kind):
                root = self.stage()
                contract = install_fixture(root)
                config = selected_config(root, PROJECT)
                self.assertEqual(policy_issues(root, config), ())
                if kind == "source":
                    target = root / config.required_inputs[0]
                    target.write_bytes(target.read_bytes() + b"\n")
                elif kind == "model":
                    target = root / ISLAND / "tests/electrical/startup.cir"
                    target.write_text(target.read_text().replace("100u", "200u"))
                elif kind == "identity":
                    write_model(
                        root / config.electrical,
                        contract.model_copy(update={"project_id": "wrong"}),
                    )
                else:
                    config = config.model_copy(update={"electrical": "../elsewhere.json"})
                self.assertTrue(policy_issues(root, config))

    def test_undeclared_includes_control_code_and_unused_models_rejected(self) -> None:
        root = self.stage()
        contract = install_fixture(root)
        assert isinstance(contract.power, PowerAnalysis)
        case = contract.power.startup[0]
        target = root / case.deck
        for text in (
            'title\n.include "hidden.lib"\n.end\n',
            "title\n.control\nquit\n.endc\n.end\n",
            'title\n.lib "hidden.lib" section\n.end\n',
            "title\n.end\nR1 a 0 1k\n",
        ):
            target.write_text(text)
            changed = case.model_copy(update={"model_sha256": {case.deck: digest(target)}})
            with self.assertRaises(ValueError):
                expanded_deck(root, changed)

    def test_simulator_failure_missing_duplicate_nonfinite_and_out_of_limit_measurements(
        self,
    ) -> None:
        root = self.stage()
        contract = install_fixture(root)
        assert isinstance(contract.power, PowerAnalysis)
        case = contract.power.startup[0]
        for stdout in (
            "",
            "check0 = nan",
            "check0 = 2\ncheck0 = 3",
            "check0 = 9",
            "check0 = 2\nError: transient failed",
        ):
            command = CommandEvidence(
                argv=("ngspice",), started_utc="fixture", returncode=0, stdout=stdout
            )
            self.assertTrue(any(c.status == "FAIL" for c in measured_checks(case, command)))
        command = CommandEvidence(
            argv=("ngspice",), started_utc="fixture", returncode=0, stdout="check0 = 4.95"
        )
        self.assertEqual(measured_checks(case, command)[0].status, "PASS")
        deck = simulation_deck(root, case)
        self.assertIn("tran 9.999", deck)
        self.assertIn("set measureprec=15", deck)
        self.assertIn("set rawfileprec=17", deck)

    def test_missing_or_wrong_simulator_does_not_pass(self) -> None:
        root = self.stage()
        contract = install_fixture(root)
        write_model(
            root / ISLAND / "tests/electrical.json", contract.model_copy(update={"grounding": NA})
        )
        report = analyze(root, PROJECT, ngspice="missing-electrical-simulator")
        self.assertEqual(report.status, "FAIL")
        self.assertTrue(any(c.status == "NOT_RUN" for c in report.checks))
        self.assertTrue((Path(report.run_directory) / "ngspice-version.command.json").is_file())
        with patch(
            "kicad_tooling.hwrepo.spice.run_command",
            return_value=CommandEvidence(
                argv=("ngspice",), started_utc="fixture", returncode=0, stdout="ngspice-46"
            ),
        ):
            self.assertRaisesRegex(
                ValueError,
                "Exact ngspice",
                simulator_version,
                Path(report.run_directory),
                "ngspice",
                "47",
            )

    def test_unconfigured_cli_is_explicit_nonzero_and_writes_a_receipt(self) -> None:
        root = self.stage()
        command = subprocess.run(
            (
                sys.executable,
                "-I",
                "-B",
                "-m",
                "kicad_tooling.electrical",
                "--root",
                str(root),
                "--project",
                PROJECT,
                "--format",
                "json",
            ),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(command.returncode, 1, command.stderr)
        self.assertEqual(json.loads(command.stdout)["status"], "NOT_CONFIGURED")

    def test_bound_inputs_and_policy_are_rechecked_after_execution(self) -> None:
        root = self.stage()
        contract = install_fixture(root)
        contract = contract.model_copy(update={"power": NA, "high_frequency": NA, "grounding": NA})
        write_model(root / ISLAND / "tests/electrical.json", contract)
        config = selected_config(root, PROJECT)
        self.assertIsNotNone(load_analysis(root, config))
        before = bound_inputs(root, config, contract)
        with patch("kicad_tooling.hwrepo.electrical_runner.bound_inputs", side_effect=[before, {}]):
            report = analyze(root, PROJECT)
        self.assertEqual(report.status, "FAIL")
        self.assertIn("changed during", report.checks[-1].detail)

    def test_timeout_receipt_and_missing_waveforms_fail(self) -> None:
        root = self.stage()
        contract = install_fixture(root)
        assert isinstance(contract.power, PowerAnalysis)
        output = root / "build/spice-test"
        output.mkdir(parents=True)
        with patch(
            "kicad_tooling.hwrepo.spice.run_command",
            return_value=CommandEvidence(
                argv=("ngspice",), started_utc="fixture", returncode=124, error="Timed out"
            ),
        ):
            _, checks = run_case(root, output, "ngspice", contract.power.startup[0])
        self.assertTrue(all(c.status == "FAIL" for c in checks))
        self.assertTrue((output / "startup/ngspice.command.json").is_file())

    def test_waveform_parser_rejects_truncated_nonfinite_and_uncovered_data(self) -> None:
        root = self.stage()
        contract = install_fixture(root)
        assert isinstance(contract.power, PowerAnalysis)
        case = contract.power.startup[0]
        raw = root / "waveform.raw"
        content = "Title: test\nFlags: real\nNo. Variables: 2\nNo. Points: 3\nVariables:\n0 time time\n1 v(out) voltage\nValues:\n0 0\n0\n1 0.001\n4.9\n2 0.005\n5\n"
        raw.write_text(content)
        self.assertTrue(all(c.status == "PASS" for c in waveform_checks(raw, case)))
        for changed in (
            content.replace("2 0.005\n5\n", ""),
            content.replace("4.9", "nan"),
            content.replace("1 0.001", "1 -0.001"),
        ):
            raw.write_text(changed)
            with self.assertRaises(ValueError):
                waveform_checks(raw, case)
        raw.write_text(content.replace("0.001", "0.0001").replace("0.005", "0.0005"))
        self.assertTrue(any(c.status == "FAIL" for c in waveform_checks(raw, case)))

    def test_recursive_escaping_and_unlisted_model_includes_fail(self) -> None:
        root = self.stage()
        contract = install_fixture(root)
        assert isinstance(contract.power, PowerAnalysis)
        case = contract.power.startup[0]
        target = root / case.deck
        for include in ("startup.cir", "../other.cir", "/tmp/other.cir"):
            target.write_text(f'title\n.include "{include}"\n.end\n')
            changed = case.model_copy(update={"model_sha256": {case.deck: digest(target)}})
            with self.assertRaises(ValueError):
                expanded_deck(root, changed)
        included = target.with_name("passive.lib")
        included.write_text("R1 in out 10\n")
        target.write_text('title\n.include "passive.lib"\n.end\n')
        case = case.model_copy(
            update={
                "model_sha256": {
                    case.deck: digest(target),
                    included.relative_to(root).as_posix(): digest(included),
                }
            }
        )
        self.assertIn("R1 in out 10", expanded_deck(root, case))
        target.write_text("title\nR1 in out 1\n.end\n")
        case = case.model_copy(
            update={"model_sha256": {**case.model_sha256, case.deck: digest(target)}}
        )
        with self.assertRaisesRegex(ValueError, "Unused model"):
            expanded_deck(root, case)

    def test_portable_gate_rejects_an_overload_and_cli_cannot_bypass_model_hashes(self) -> None:
        root = self.stage()
        contract = install_fixture(root)
        assert isinstance(contract.power, PowerAnalysis)
        overloaded = contract.power.model_copy(
            update={
                "rails": (
                    contract.power.rails[0].model_copy(update={"continuous_limit_a": 0.001}),
                ),
            }
        )
        write_model(
            root / ISLAND / "tests/electrical.json",
            contract.model_copy(update={"power": overloaded}),
        )
        from kicad_tooling.ci import project_static_pipeline

        result = project_static_pipeline(root, (PROJECT,))
        self.assertEqual(result.status, "FAIL")
        self.assertTrue(any("steady-current" in issue for issue in result.registry.issues))
        write_model(root / ISLAND / "tests/electrical.json", contract)
        model = root / contract.power.startup[0].deck
        model.write_text(model.read_text() + "\n")
        command = subprocess.run(
            (
                sys.executable,
                "-I",
                "-B",
                "-m",
                "kicad_tooling.ci",
                "--root",
                str(root),
                "--electrical",
                "--project",
                PROJECT,
            ),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(command.returncode, 1, command.stderr)
        report = json.loads(command.stdout)
        self.assertEqual(report["status"], "FAIL")
        self.assertIn("stale reviewed model", report["projects"][0]["checks"][-1]["detail"])

    def test_combined_verification_cannot_pass_a_failed_electrical_lane(self) -> None:
        from kicad_tooling.hwrepo.models import ElectricalAnalysisReport, ElectricalCheck
        from kicad_tooling.verify import verify
        from tests.test_verify import VerifyTests, native_summary

        root = self.stage().resolve()
        contract = install_fixture(root).model_copy(update={"power": NA, "high_frequency": NA})
        write_model(root / ISLAND / "tests/electrical.json", contract)
        failed = ElectricalAnalysisReport(
            project_id=PROJECT,
            status="FAIL",
            run_directory=str(root / "build/simulation"),
            checks=(ElectricalCheck(id="grounding", status="FAIL", detail="Missing pin U1.2"),),
        )
        with (
            VerifyTests.runner_environment("10.0.0"),
            patch("kicad_tooling.verify.check_all", return_value=native_summary()),
            patch(
                "kicad_tooling.hwrepo.electrical_runner.analyze", return_value=failed
            ) as simulation,
        ):
            result = verify(
                root, PROJECT, depth="electrical", runner="local", ngspice="approved-ngspice"
            )
        self.assertEqual(result.status, "FAIL")
        self.assertEqual(result.electrical, failed)
        self.assertEqual(simulation.call_args.args[-1], "approved-ngspice")
        self.assertIn("electrical", result.next_actions[0])


if __name__ == "__main__":
    unittest.main()
