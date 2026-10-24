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


def unconnected_usb_data_pins(
    observed: NetlistContract,
) -> tuple[UnconnectedUsbDataPin, ...]:
    """Return supported USB 2.0 data pins with no exported net assignment.

    Native pin-function aliases identify only a review candidate. The result
    does not infer whether the interface is used or which endpoint it serves.
    """
    assigned_pins = {pin.casefold() for pins in observed.nets.values() for pin in pins}
    dnp_references = {reference.casefold() for reference in observed.dnp_components}
    found: list[UnconnectedUsbDataPin] = []
    for pin, function in observed.pin_functions.items():
        reference, separator, _number = pin.rpartition(".")
        if not separator or reference.casefold() in dnp_references:
            continue
        if pin.casefold() in assigned_pins:
            continue
        identity = usb_data_function_identity(function)
        if identity is None:
            continue
        port_index, side = identity
        found.append(
            UnconnectedUsbDataPin(
                pin=pin,
                function=function,
                port_index=port_index,
                side=side,
            )
        )
    return tuple(sorted(found, key=lambda item: (item.pin.casefold(), item.function.casefold())))
