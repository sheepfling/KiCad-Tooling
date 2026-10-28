"""Recognize open CAN/FDCAN direction pins on partially connected channels."""

from __future__ import annotations

from dataclasses import dataclass

from .can_signal_functions import can_signal_role_and_channel
from .models import NetlistContract


@dataclass(frozen=True, slots=True)
class UnconnectedCanDirectionPin:
    pin: str
    function: str
    role: str
    channel: str
    paired_pin: str
    paired_net: str


def unconnected_can_direction_pins(
    observed: NetlistContract,
) -> tuple[UnconnectedCanDirectionPin, ...]:
    """Return one open TX/RX function only when its same-channel peer is assigned.

    Native pin-function names do not establish that a CAN channel is used.
    Requiring exactly one recognized TX and RX function, a native pin-number
    inventory, and one uniquely assigned pair member avoids prompting for
    entirely open, ambiguous, or multi-net channels.
    """
    assignments: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            assignments.setdefault(pin.casefold(), set()).add(net)

    component_references = {reference.casefold() for reference in observed.components}
    dnp_references = {reference.casefold() for reference in observed.dnp_components}
    component_pin_numbers = {
        reference.casefold(): {number.casefold() for number in pin_numbers}
        for reference, pin_numbers in observed.component_pin_numbers.items()
    }
    pin_function_numbers: dict[str, set[str]] = {}
    for pin in observed.pin_functions:
        reference, separator, number = pin.rpartition(".")
        if separator:
            pin_function_numbers.setdefault(reference.casefold(), set()).add(number.casefold())
    complete_pin_inventories = {
        reference
        for reference, numbers in component_pin_numbers.items()
        if numbers and numbers == pin_function_numbers.get(reference, set())
    }
    groups: dict[tuple[str, str], dict[str, list[tuple[str, str]]]] = {}
    for pin, function in observed.pin_functions.items():
        reference, separator, number = pin.rpartition(".")
        reference_key = reference.casefold()
        if (
            not separator
            or reference_key not in component_references
            or reference_key in dnp_references
            or reference_key not in complete_pin_inventories
            or number.casefold() not in component_pin_numbers.get(reference_key, set())
        ):
            continue
        identity = can_signal_role_and_channel(function)
        if identity is None:
            continue
        role, channel = identity
        groups.setdefault((reference_key, channel.casefold()), {}).setdefault(role, []).append(
            (pin, function)
        )

    found: list[UnconnectedCanDirectionPin] = []
    for (_reference_key, channel), roles in groups.items():
        tx_pins = roles.get("tx", [])
        rx_pins = roles.get("rx", [])
        if len(tx_pins) != 1 or len(rx_pins) != 1:
            continue
        (tx_pin, tx_function), (rx_pin, rx_function) = tx_pins[0], rx_pins[0]
        tx_nets = assignments.get(tx_pin.casefold(), set())
        rx_nets = assignments.get(rx_pin.casefold(), set())
        if len(tx_nets) == 1 and not rx_nets:
            found.append(
                UnconnectedCanDirectionPin(
                    pin=rx_pin,
                    function=rx_function,
                    role="rx",
                    channel=channel,
                    paired_pin=tx_pin,
                    paired_net=next(iter(tx_nets)),
                )
            )
        elif len(rx_nets) == 1 and not tx_nets:
            found.append(
                UnconnectedCanDirectionPin(
                    pin=tx_pin,
                    function=tx_function,
                    role="tx",
                    channel=channel,
                    paired_pin=rx_pin,
                    paired_net=next(iter(rx_nets)),
                )
            )
    return tuple(
        sorted(
            found,
            key=lambda item: (item.pin.casefold(), item.role, item.channel.casefold()),
        )
    )
