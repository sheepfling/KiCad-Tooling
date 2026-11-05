"""Review explicit CAN-controller transmit and receive pins on one net."""

from __future__ import annotations

from .can_signal_functions import can_channel_label, can_signal_role_and_channel
from .component_references import is_integrated_circuit_reference
from .design_lint_can_tx_rx_candidate_evidence import (
    CanTxRxEndpoint,
    CanTxRxSameNetCandidate,
    CanTxRxSameNetEvidence,
)
from .design_lint_types import Candidate
from .netlist_contract_models import NetlistContract

RULE_ID = "bus.can_tx_rx_same_net"


def can_tx_rx_same_net_candidates(observed: NetlistContract) -> tuple[Candidate, ...]:
    """Find one fitted IC's uniquely assigned CAN TX/RX functions on the same net."""
    fitted = {
        reference.casefold(): reference
        for reference in observed.components
        if is_integrated_circuit_reference(reference)
    }
    dnp = {reference.casefold() for reference in observed.dnp_components}
    inventory = {
        reference.casefold(): {number.casefold() for number in numbers}
        for reference, numbers in observed.component_pin_numbers.items()
    }
    nets_by_pin: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            nets_by_pin.setdefault(pin.casefold(), set()).add(net)
    electrical_types = {
        pin.casefold(): value.strip().casefold()
        for pin, value in observed.pin_electrical_types.items()
    }
    function_counts: dict[str, int] = {}
    for pin in observed.pin_functions:
        function_counts[pin.casefold()] = function_counts.get(pin.casefold(), 0) + 1

    groups: dict[
        tuple[str, str],
        dict[str, list[tuple[str, str, str, str]]],
    ] = {}
    for pin, function in observed.pin_functions.items():
        reference, separator, number = pin.rpartition(".")
        reference_key = reference.casefold()
        if (
            not separator
            or reference_key not in fitted
            or reference_key in dnp
            or number.casefold() not in inventory.get(reference_key, set())
            or function_counts[pin.casefold()] != 1
        ):
            continue
        assignments = nets_by_pin.get(pin.casefold(), set())
        if len(assignments) != 1:
            continue
        role_channel = can_signal_role_and_channel(function)
        if role_channel is None:
            continue
        role, channel = role_channel
        groups.setdefault((reference_key, channel), {}).setdefault(role, []).append(
            (
                pin,
                function,
                next(iter(assignments)),
                electrical_types.get(pin.casefold(), "unknown"),
            )
        )

    findings: list[Candidate] = []
    for (reference_key, channel), roles in sorted(groups.items()):
        transmitters = sorted(set(roles.get("tx", ())))
        receivers = sorted(set(roles.get("rx", ())))
        if len(transmitters) != 1 or len(receivers) != 1:
            continue
        tx_pin, tx_function, tx_net, tx_type = transmitters[0]
        rx_pin, rx_function, rx_net, rx_type = receivers[0]
        if tx_net != rx_net or tx_type == rx_type == "output":
            continue

        channel_label = can_channel_label(channel)
        reference = fitted[reference_key]
        findings.append(
            CanTxRxSameNetCandidate.from_source_evidence(
                CanTxRxSameNetEvidence(
                    observed=observed,
                    reference=reference,
                    channel=channel,
                    tx=CanTxRxEndpoint(
                        pin=tx_pin,
                        function=tx_function,
                        electrical_type=tx_type,
                    ),
                    rx=CanTxRxEndpoint(
                        pin=rx_pin,
                        function=rx_function,
                        electrical_type=rx_type,
                    ),
                    net=tx_net,
                ),
                subject=(
                    f"{reference}: {channel_label} TX {tx_function} and RX {rx_function} "
                    f"share {tx_net}"
                ),
                message=(
                    f"Fitted IC {reference} has native CAN transmit pin {tx_pin} "
                    f"({tx_function}, {tx_type}) and receive pin {rx_pin} "
                    f"({rx_function}, {rx_type}) on one schematic net ({tx_net}). "
                    "Review whether this is an intentional loopback or a pin-assignment mistake; "
                    "function names alone do not establish the required topology."
                ),
            )
        )
    return tuple(findings)
