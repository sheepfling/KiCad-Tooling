"""Synthetic serial-peer requirements and netlist fixtures."""

from __future__ import annotations

from typing import Literal

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract
from kicad_tooling.hwrepo.reference_bond_models import ReferenceBondRequirement
from kicad_tooling.hwrepo.serial_logic_models import (
    SerialLogicInputLimits,
    SerialLogicLimits,
    SerialLogicOutputLimits,
    SerialPinNetRequirement,
)
from kicad_tooling.hwrepo.serial_peer_models import (
    SerialBridgePathRequirement,
    SerialBridgeRequirement,
    SerialDirectPeerRequirement,
    SerialEndpointRequirement,
    SerialExternalPeerRequirement,
    SerialPeerAnalysis,
    SerialPeerLinkRequirement,
    SerialShiftedPeerRequirement,
)


def serial_peer_requirement(
    *,
    peer_mode: Literal["direct", "level_shifted", "external"] = "direct",
    reference_policy: Literal[
        "common_net", "bonded", "separate_nets", "external_unverified", "not_applicable"
    ]
    | None = None,
    endpoint_logic_domain: str = "logic-3v3",
    peer_logic_domain: str = "logic-3v3",
    endpoint_reference: str = "U10",
    peer_reference: str = "U11",
    bridge_reference: str = "U9",
    peer_output_high_maximum_v: float = 3.3,
    peer_output_low_maximum_v: float = 0.2,
    include_logic_limits: bool = True,
) -> SerialPeerAnalysis:
    level_shifted = peer_mode == "level_shifted"
    external = peer_mode == "external"
    selected_reference_policy = reference_policy or (
        "external_unverified" if external else "separate_nets" if level_shifted else "common_net"
    )
    reference_bond = (
        ReferenceBondRequirement(
            reference="R3",
            expected_symbol="Device:R",
            expected_footprint="Synthetic:0603",
            expected_value="0R",
            side_a_pin="R3.1",
            side_b_pin="R3.2",
            side_a_net="GND_A",
            side_b_net="GND_B",
        )
        if selected_reference_policy == "bonded"
        else None
    )

    def logic_limits(
        *, output_high_maximum_v: float = 3.3, output_low_maximum_v: float = 0.2
    ) -> SerialLogicLimits:
        output_high_minimum_v = 4.2 if output_high_maximum_v > 3.6 else 3.0
        return SerialLogicLimits(
            output=SerialLogicOutputLimits(
                low_minimum_v=0.0,
                low_maximum_v=output_low_maximum_v,
                high_minimum_v=output_high_minimum_v,
                high_maximum_v=output_high_maximum_v,
                source="Synthetic UART datasheet Rev A, Table 4",
                conditions="VDD=3.3 V, specified output load, full operating range",
            ),
            input=SerialLogicInputLimits(
                absolute_minimum_v=-0.3,
                low_maximum_v=0.8,
                high_minimum_v=2.0,
                absolute_maximum_v=3.6,
                source="Synthetic UART datasheet Rev A, Table 5",
                conditions="Specified input leakage and full operating range",
            ),
        )

    endpoint = SerialEndpointRequirement(
        id="console",
        reference=endpoint_reference,
        symbol="Synthetic:UartEndpoint",
        footprint="Connector_Generic:Conn_01x03",
        logic_domain=endpoint_logic_domain,
        tx=SerialPinNetRequirement(
            pin=f"{endpoint_reference}.1", net="UART_A_TX" if level_shifted else "UART_TX"
        ),
        rx=SerialPinNetRequirement(
            pin=f"{endpoint_reference}.2", net="UART_A_RX" if level_shifted else "UART_RX"
        ),
        reference_pins=(
            (
                SerialPinNetRequirement(
                    pin=f"{endpoint_reference}.3",
                    net=(
                        "GND_A"
                        if selected_reference_policy in {"separate_nets", "bonded"}
                        else "GND"
                    ),
                ),
            )
            if selected_reference_policy != "not_applicable"
            else ()
        ),
        logic_limits=logic_limits() if include_logic_limits else None,
    )
    if external:
        peer: (
            SerialDirectPeerRequirement
            | SerialShiftedPeerRequirement
            | SerialExternalPeerRequirement
        ) = SerialExternalPeerRequirement(
            mode="external", reason="Synthetic remote device pinout has not been supplied."
        )
    else:
        peer_endpoint = SerialEndpointRequirement(
            id="device",
            reference=peer_reference,
            symbol="Synthetic:UartEndpoint",
            footprint="Connector_Generic:Conn_01x03",
            logic_domain=peer_logic_domain,
            tx=SerialPinNetRequirement(
                pin=f"{peer_reference}.1",
                net="UART_B_TX" if level_shifted else "UART_RX",
            ),
            rx=SerialPinNetRequirement(
                pin=f"{peer_reference}.2",
                net="UART_B_RX" if level_shifted else "UART_TX",
            ),
            reference_pins=(
                (
                    SerialPinNetRequirement(
                        pin=f"{peer_reference}.3",
                        net=(
                            "GND_B"
                            if selected_reference_policy in {"separate_nets", "bonded"}
                            else "GND"
                        ),
                    ),
                )
                if selected_reference_policy != "not_applicable"
                else ()
            ),
            logic_limits=(
                logic_limits(
                    output_high_maximum_v=peer_output_high_maximum_v,
                    output_low_maximum_v=peer_output_low_maximum_v,
                )
                if include_logic_limits
                else None
            ),
        )
        if level_shifted:
            bridge = SerialBridgeRequirement(
                reference=bridge_reference,
                symbol="Synthetic:UartLevelShifter",
                footprint="Package_SO:SOIC-8",
                paths=(
                    SerialBridgePathRequirement(
                        direction="a_tx_to_b_rx",
                        from_pin=f"{bridge_reference}.1",
                        from_net="UART_A_TX",
                        to_pin=f"{bridge_reference}.2",
                        to_net="UART_B_RX",
                    ),
                    SerialBridgePathRequirement(
                        direction="b_tx_to_a_rx",
                        from_pin=f"{bridge_reference}.3",
                        from_net="UART_B_TX",
                        to_pin=f"{bridge_reference}.4",
                        to_net="UART_A_RX",
                    ),
                ),
            )
            peer = SerialShiftedPeerRequirement(
                mode="level_shifted", endpoint=peer_endpoint, bridges=(bridge,)
            )
        else:
            peer = SerialDirectPeerRequirement(mode="direct", endpoint=peer_endpoint)
    return SerialPeerAnalysis(
        basis="Synthetic authored UART endpoint roles and peer map",
        links=(
            SerialPeerLinkRequirement(
                id="console-link",
                basis="Synthetic controller UART connected to one local peer",
                endpoint=endpoint,
                peer=peer,
                reference_policy=selected_reference_policy,
                reference_bond=reference_bond,
            ),
        ),
    )


def serial_peer_netlist(spec: SerialPeerAnalysis, *, fault: str | None = None) -> NetlistContract:
    link = spec.links[0]
    assignments: dict[str, str] = {}
    pins: dict[str, set[str]] = {}
    symbols: dict[str, str] = {}
    components: dict[str, ComponentContract] = {}
    dnp_components: set[str] = set()
    pin_electrical_types: dict[str, str] = {}

    def add_endpoint(endpoint: SerialEndpointRequirement) -> None:
        components[endpoint.reference] = ComponentContract(
            value=f"Synthetic {endpoint.id}", footprint=endpoint.footprint
        )
        symbols[endpoint.reference] = endpoint.symbol
        for mapping in (endpoint.tx, endpoint.rx, *endpoint.reference_pins):
            reference, number = mapping.pin.rsplit(".", 1)
            pins.setdefault(reference, set()).add(number)
            assignments[mapping.pin] = mapping.net

    add_endpoint(link.endpoint)
    if isinstance(link.peer, (SerialDirectPeerRequirement, SerialShiftedPeerRequirement)):
        add_endpoint(link.peer.endpoint)
    if isinstance(link.peer, SerialShiftedPeerRequirement):
        for bridge in link.peer.bridges:
            components[bridge.reference] = ComponentContract(
                value="Synthetic UART level shifter", footprint=bridge.footprint
            )
            symbols[bridge.reference] = bridge.symbol
            for path in bridge.paths:
                for pin, net in ((path.from_pin, path.from_net), (path.to_pin, path.to_net)):
                    reference, number = pin.rsplit(".", 1)
                    pins.setdefault(reference, set()).add(number)
                    assignments[pin] = net

    if link.reference_bond is not None and fault != "bond-missing":
        bond = link.reference_bond
        components[bond.reference] = ComponentContract(
            value=bond.expected_value,
            footprint=bond.expected_footprint,
        )
        symbols[bond.reference] = bond.expected_symbol
        pins.setdefault(bond.reference, set()).update(
            (bond.side_a_pin.rsplit(".", 1)[1], bond.side_b_pin.rsplit(".", 1)[1])
        )
        assignments[bond.side_a_pin] = bond.side_a_net
        assignments[bond.side_b_pin] = bond.side_b_net
        pin_electrical_types[bond.side_a_pin] = "passive"
        pin_electrical_types[bond.side_b_pin] = "passive"
        if fault == "bond-wrong-value":
            components[bond.reference] = components[bond.reference].model_copy(
                update={"value": "1R"}
            )
        elif fault == "bond-wrong-footprint":
            components[bond.reference] = components[bond.reference].model_copy(
                update={"footprint": "Synthetic:0402"}
            )
        elif fault == "bond-wrong-symbol":
            symbols[bond.reference] = "Device:C"
        elif fault == "bond-dnp":
            dnp_components.add(bond.reference)
        elif fault == "bond-active-pin":
            pin_electrical_types[bond.side_b_pin] = "input"
        elif fault == "bond-wrong-net":
            assignments[bond.side_b_pin] = "FLOATING_GND"

    if fault == "tx-to-tx" and isinstance(
        link.peer, (SerialDirectPeerRequirement, SerialShiftedPeerRequirement)
    ):
        if isinstance(link.peer, SerialDirectPeerRequirement):
            assignments[link.peer.endpoint.tx.pin] = link.endpoint.tx.net
            assignments[link.peer.endpoint.rx.pin] = link.endpoint.rx.net
        else:
            assignments[link.peer.endpoint.rx.pin] = "WRONG_UART_NET"
    elif fault == "bridge-output-wrong-net" and isinstance(link.peer, SerialShiftedPeerRequirement):
        path = link.peer.bridges[0].paths[0]
        assignments[path.to_pin] = "WRONG_UART_NET"
    elif fault == "local-reference-wrong-net" and link.endpoint.reference_pins:
        assignment = link.endpoint.reference_pins[0]
        assignments[assignment.pin] = "WRONG_REFERENCE"
    elif (
        fault == "remote-reference-unconnected"
        and isinstance(link.peer, (SerialDirectPeerRequirement, SerialShiftedPeerRequirement))
        and link.peer.endpoint.reference_pins
    ):
        assignments.pop(link.peer.endpoint.reference_pins[0].pin, None)

    nets: dict[str, list[str]] = {}
    for pin, net in assignments.items():
        nets.setdefault(net, []).append(pin)
    return NetlistContract(
        components=components,
        nets={net: tuple(sorted(items)) for net, items in nets.items()},
        component_symbols=symbols,
        component_pin_numbers={
            reference: tuple(sorted(numbers)) for reference, numbers in pins.items()
        },
        dnp_components=tuple(sorted(dnp_components)),
        pin_electrical_types=pin_electrical_types,
    )
