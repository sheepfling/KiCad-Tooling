"""Synthetic RS-485 electrical contract fixtures."""

from __future__ import annotations

from typing import Literal

from kicad_tooling.hwrepo.models import (
    ComponentContract,
    NetlistContract,
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
