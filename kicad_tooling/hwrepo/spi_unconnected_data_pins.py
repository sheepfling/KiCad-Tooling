"""Recognize open SPI data-function pins on partially connected channels."""

from __future__ import annotations

from dataclasses import dataclass

from .models import NetlistContract
from .spi_participants import is_spi_ic_reference, spi_data_function_role_and_channel


@dataclass(frozen=True, slots=True)
class UnconnectedSpiDataPin:
    pin: str
    function: str
    role: str
    channel: str


def unconnected_spi_data_function_pins(
    observed: NetlistContract,
) -> tuple[UnconnectedSpiDataPin, ...]:
    """Return open SPI data pins only when the same fitted IC/channel has assigned evidence.

    The bounded MOSI/MISO-family function names are review clues. Requiring a
    uniquely assigned data pin on the same component and parsed channel avoids
    prompting for channels that are entirely unused.
    """
    assignments: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            assignments.setdefault(pin.casefold(), set()).add(net)

    fitted_references = {
        reference.casefold(): reference
        for reference in observed.components
        if is_spi_ic_reference(reference)
    }
    dnp_references = {reference.casefold() for reference in observed.dnp_components}
    groups: dict[tuple[str, str], list[UnconnectedSpiDataPin]] = {}
    assigned_groups: set[tuple[str, str]] = set()
    for pin, function in observed.pin_functions.items():
        reference, separator, _number = pin.rpartition(".")
        reference_key = reference.casefold()
        if (
            not separator
            or reference_key not in fitted_references
            or reference_key in dnp_references
        ):
            continue
        identity = spi_data_function_role_and_channel(function)
        if identity is None:
            continue
        role, channel = identity
        group = (reference_key, channel.casefold())
        row = UnconnectedSpiDataPin(pin=pin, function=function, role=role, channel=channel)
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
            key=lambda item: (
                item.pin.casefold(),
                item.role,
                item.channel.casefold(),
            ),
        )
    )
