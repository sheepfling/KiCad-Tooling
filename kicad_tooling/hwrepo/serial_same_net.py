"""Review fitted serial TX/RX pin pairs that share one schematic net."""

from __future__ import annotations

from .design_lint_types import Candidate
from .models import NetlistContract
from .serial_participants import serial_function_role_and_channel

RULE_ID = "bus.serial_tx_rx_same_net"


def serial_tx_rx_same_net_candidates(observed: NetlistContract) -> tuple[Candidate, ...]:
    """Find one unambiguous same-component TX/RX pair on the same native net."""
    fitted = {reference.casefold(): reference for reference in observed.components}
    dnp = {reference.casefold() for reference in observed.dnp_components}
    nets_by_pin: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            nets_by_pin.setdefault(pin.casefold(), set()).add(net)

    by_endpoint: dict[tuple[str, str], dict[str, list[tuple[str, str]]]] = {}
    for pin, function in observed.pin_functions.items():
        reference, separator, _number = pin.rpartition(".")
        reference_key = reference.casefold()
        if not separator or reference_key not in fitted or reference_key in dnp:
            continue
        assignment = nets_by_pin.get(pin.casefold(), set())
        if len(assignment) != 1:
            continue
        role_channel = serial_function_role_and_channel(function)
        if role_channel is None:
            continue
        role, channel = role_channel
        by_endpoint.setdefault((reference_key, channel), {}).setdefault(role, []).append(
            (pin, next(iter(assignment)))
        )

    findings: list[Candidate] = []
    for (reference_key, channel), roles in sorted(by_endpoint.items()):
        transmitters = sorted(set(roles.get("tx", ())))
        receivers = sorted(set(roles.get("rx", ())))
        if len(transmitters) != 1 or len(receivers) != 1:
            continue
        tx_pin, tx_net = transmitters[0]
        rx_pin, rx_net = receivers[0]
        if tx_net.casefold() != rx_net.casefold():
            continue

        reference = fitted[reference_key]
        channel_label = (
            channel.upper()
            if channel.startswith(("uart", "usart"))
            else "TX/RX"
            if channel == "default"
            else f"serial channel {channel.removeprefix('index')}"
        )
        findings.append(
            Candidate(
                rule_id=RULE_ID,
                subject=f"{reference}: {channel_label} TX/RX share {tx_net}",
                message=(
                    f"The native {channel_label} transmit pin {tx_pin} and receive pin {rx_pin} "
                    f"on {reference} share one schematic net ({tx_net}). Review whether this "
                    "is an intentional single-wire or loopback topology, or a pin-assignment "
                    "mistake. The netlist does not establish which topology was intended."
                ),
                evidence={
                    "component": (reference,),
                    "channel": (channel_label,),
                    "tx_pin": (tx_pin,),
                    "rx_pin": (rx_pin,),
                    "net": (tx_net,),
                },
            )
        )
    return tuple(findings)
