"""Recognize unassigned USB 2.0 D+/D- pins in native netlists."""

from __future__ import annotations

from dataclasses import dataclass

from .bus_signal_pairs import usb_data_function_identity
from .models import NetlistContract


@dataclass(frozen=True)
class UnconnectedUsbDataPin:
    pin: str
    function: str
    port_index: str | None
    side: str
    paired_pin: str
    paired_function: str
    paired_net: str


def unconnected_usb_data_pins(
    observed: NetlistContract,
) -> tuple[UnconnectedUsbDataPin, ...]:
    """Return an open supported USB 2.0 data pin beside its assigned pair.

    Native pin-function aliases identify only a review candidate. An entirely
    open pair is skipped because the result does not infer whether the
    interface is used or which endpoint it serves.
    """
    assignments: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            assignments.setdefault(pin.casefold(), set()).add(net)

    dnp_references = {reference.casefold() for reference in observed.dnp_components}
    component_references = {reference.casefold() for reference in observed.components}
    component_pin_numbers = {
        reference.casefold(): {number.casefold() for number in pin_numbers}
        for reference, pin_numbers in observed.component_pin_numbers.items()
    }
    groups: dict[tuple[str, str | None], dict[str, list[tuple[str, str]]]] = {}
    for pin, function in observed.pin_functions.items():
        reference, separator, number = pin.rpartition(".")
        reference_key = reference.casefold()
        if (
            not separator
            or reference_key not in component_references
            or reference_key in dnp_references
            or number.casefold() not in component_pin_numbers.get(reference_key, set())
        ):
            continue
        identity = usb_data_function_identity(function)
        if identity is None:
            continue
        port_index, side = identity
        groups.setdefault((reference_key, port_index), {}).setdefault(side, []).append(
            (pin, function)
        )

    found: list[UnconnectedUsbDataPin] = []
    for (_reference, port_index), roles in groups.items():
        positive = roles.get("positive", [])
        negative = roles.get("negative", [])
        if len(positive) != 1 or len(negative) != 1:
            continue
        (positive_pin, positive_function), (negative_pin, negative_function) = (
            positive[0],
            negative[0],
        )
        positive_nets = assignments.get(positive_pin.casefold(), set())
        negative_nets = assignments.get(negative_pin.casefold(), set())
        if not positive_nets and len(negative_nets) == 1:
            found.append(
                UnconnectedUsbDataPin(
                    pin=positive_pin,
                    function=positive_function,
                    port_index=port_index,
                    side="positive",
                    paired_pin=negative_pin,
                    paired_function=negative_function,
                    paired_net=next(iter(negative_nets)),
                )
            )
        elif not negative_nets and len(positive_nets) == 1:
            found.append(
                UnconnectedUsbDataPin(
                    pin=negative_pin,
                    function=negative_function,
                    port_index=port_index,
                    side="negative",
                    paired_pin=positive_pin,
                    paired_function=positive_function,
                    paired_net=next(iter(positive_nets)),
                )
            )
    return tuple(sorted(found, key=lambda item: (item.pin.casefold(), item.function.casefold())))
