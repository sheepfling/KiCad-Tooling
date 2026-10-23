"""Shared native SPI role-pin assignments for same-net review rules."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from .models import NetlistContract
from .spi_participants import is_spi_ic_reference, spi_signal_role_and_channel


@dataclass(frozen=True)
class SpiRolePinAssignment:
    """One bounded SPI function pin and its native net/type evidence."""

    pin: str
    function: str
    nets: tuple[str, ...]
    electrical_type: str
    in_component_inventory: bool


@dataclass(frozen=True)
class SpiRoleAssignmentGroup:
    """Recognized SPI pin roles for one fitted IC and one channel."""

    reference: str
    channel: str
    roles: Mapping[str, tuple[SpiRolePinAssignment, ...]]


def spi_role_assignment_groups(observed: NetlistContract) -> tuple[SpiRoleAssignmentGroup, ...]:
    """Collect fitted SPI IC role pins with exact net and inventory evidence."""
    fitted = {
        reference.casefold(): reference
        for reference in observed.components
        if is_spi_ic_reference(reference)
    }
    dnp = {reference.casefold() for reference in observed.dnp_components}
    pin_numbers = {
        reference.casefold(): {number.casefold() for number in numbers}
        for reference, numbers in observed.component_pin_numbers.items()
    }
    nets_by_pin: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            nets_by_pin.setdefault(pin.casefold(), set()).add(net)
    pin_types = {
        pin.casefold(): value.strip().casefold()
        for pin, value in observed.pin_electrical_types.items()
    }

    role_pins: dict[tuple[str, str, str], list[SpiRolePinAssignment]] = {}
    for pin, function in observed.pin_functions.items():
        reference, separator, number = pin.rpartition(".")
        reference_key = reference.casefold()
        if not separator or reference_key not in fitted or reference_key in dnp:
            continue
        role_channel = spi_signal_role_and_channel(function)
        if role_channel is None:
            continue
        role, channel = role_channel
        assignments = tuple(
            sorted(nets_by_pin.get(pin.casefold(), ()), key=lambda item: (item.casefold(), item))
        )
        role_pins.setdefault((reference_key, channel, role), []).append(
            SpiRolePinAssignment(
                pin=pin,
                function=function,
                nets=assignments,
                electrical_type=pin_types.get(pin.casefold(), "unknown"),
                in_component_inventory=number.casefold() in pin_numbers.get(reference_key, set()),
            )
        )

    grouped: dict[tuple[str, str], dict[str, list[SpiRolePinAssignment]]] = {}
    for (reference, channel, role), endpoints in role_pins.items():
        grouped.setdefault((reference, channel), {}).setdefault(role, []).extend(endpoints)

    return tuple(
        SpiRoleAssignmentGroup(
            reference=fitted[reference],
            channel=channel,
            roles={
                role: tuple(sorted(endpoints, key=lambda item: (item.pin.casefold(), item.pin)))
                for role, endpoints in sorted(roles.items())
            },
        )
        for (reference, channel), roles in sorted(grouped.items())
    )


def spi_channel_label(channel: str) -> str:
    """Render the bounded default or indexed SPI channel in a finding."""
    return "SPI" if channel == "default" else f"SPI channel {channel.removeprefix('index')}"
