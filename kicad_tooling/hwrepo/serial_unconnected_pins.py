"""Recognize unassigned UART/USART function pins with a connected channel peer."""

from __future__ import annotations

from dataclasses import dataclass

from .models import NetlistContract
from .serial_participants import serial_function_role_and_channel


@dataclass(frozen=True)
class UnconnectedSerialFunctionPin:
    pin: str
    function: str
    role: str
    channel: str


def unconnected_serial_function_pins(
    observed: NetlistContract,
) -> tuple[UnconnectedSerialFunctionPin, ...]:
    """Return open serial pins only when the same component/channel has assigned evidence.

    Native UART/USART function aliases do not establish that a particular
    channel is used. Requiring another uniquely assigned member of the same
    component/channel avoids prompting for channels that are entirely unused.
    """
    assignments: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            assignments.setdefault(pin.casefold(), set()).add(net)

    dnp_references = {reference.casefold() for reference in observed.dnp_components}
    component_references = {reference.casefold() for reference in observed.components}
    groups: dict[tuple[str, str], list[UnconnectedSerialFunctionPin]] = {}
    assigned_groups: set[tuple[str, str]] = set()
    for pin, function in observed.pin_functions.items():
        reference, separator, _number = pin.rpartition(".")
        reference_key = reference.casefold()
        if (
            not separator
            or reference_key not in component_references
            or reference_key in dnp_references
        ):
            continue
        identity = serial_function_role_and_channel(function)
        if identity is None:
            continue
        role, channel = identity
        group = (reference_key, channel.casefold())
        row = UnconnectedSerialFunctionPin(
            pin=pin,
            function=function,
            role=role,
            channel=channel,
        )
        groups.setdefault(group, []).append(row)
        if len(assignments.get(pin.casefold(), ())) == 1:
            assigned_groups.add(group)

    found = (
        row
        for group, rows in groups.items()
        if group in assigned_groups
        for row in rows
        if not assignments.get(row.pin.casefold())
    )
    return tuple(
        sorted(
            found,
            key=lambda item: (item.pin.casefold(), item.role, item.channel.casefold()),
        )
    )
