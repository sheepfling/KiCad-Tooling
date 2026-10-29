"""Review one-sided open I3C signal pairs on fitted controller ICs."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .bus_signal_roles import i3c_signal_identity
from .models import NetlistContract


@dataclass(frozen=True, slots=True)
class UnconnectedI3cSignalPin:
    pin: str
    function: str
    role: str
    channel: str | None
    paired_pin: str
    paired_function: str
    paired_net: str


_IC_REFERENCE = re.compile(r"^(?:U|IC)[0-9]+$", re.IGNORECASE)


def unconnected_i3c_signal_pins(
    observed: NetlistContract,
) -> tuple[UnconnectedI3cSignalPin, ...]:
    """Find exactly one open SDA/SCL member beside an assigned channel peer.

    Requires explicit I3C role functions on a fitted U/IC reference and a
    complete pin-number inventory. Function text does not establish interface
    use; an entirely open pair is intentionally quiet.
    """
    fitted = {
        reference.casefold(): reference
        for reference in observed.components
        if _IC_REFERENCE.fullmatch(reference)
    }
    dnp = {reference.casefold() for reference in observed.dnp_components}
    inventories = {
        reference.casefold(): {number.casefold() for number in numbers}
        for reference, numbers in observed.component_pin_numbers.items()
    }
    assignments: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            assignments.setdefault(pin.casefold(), set()).add(net)

    roles: dict[str, dict[tuple[str | None, str], list[tuple[str, str]]]] = {}
    invalid_inventory: set[str] = set()
    for pin, function in observed.pin_functions.items():
        reference, separator, number = pin.rpartition(".")
        reference_key = reference.casefold()
        if not separator or reference_key not in fitted:
            continue
        identity = i3c_signal_identity(function)
        if identity is None:
            continue
        inventory = inventories.get(reference_key, set())
        if not inventory or number.casefold() not in inventory:
            invalid_inventory.add(reference_key)
            continue
        roles.setdefault(reference_key, {}).setdefault(
            (identity.channel, identity.role), []
        ).append((f"{fitted[reference_key]}.{number}", function))

    found: list[UnconnectedI3cSignalPin] = []
    for reference_key, channel_roles in roles.items():
        if reference_key in dnp or reference_key in invalid_inventory:
            continue
        channels = {channel for channel, _role in channel_roles}
        for channel in channels:
            sda = channel_roles.get((channel, "SDA"), ())
            scl = channel_roles.get((channel, "SCL"), ())
            if len(sda) != 1 or len(scl) != 1:
                continue
            (sda_pin, sda_function), (scl_pin, scl_function) = sda[0], scl[0]
            sda_nets = assignments.get(sda_pin.casefold(), set())
            scl_nets = assignments.get(scl_pin.casefold(), set())
            if not sda_nets and len(scl_nets) == 1:
                found.append(
                    UnconnectedI3cSignalPin(
                        sda_pin,
                        sda_function,
                        "SDA",
                        channel,
                        scl_pin,
                        scl_function,
                        next(iter(scl_nets)),
                    )
                )
            elif not scl_nets and len(sda_nets) == 1:
                found.append(
                    UnconnectedI3cSignalPin(
                        scl_pin,
                        scl_function,
                        "SCL",
                        channel,
                        sda_pin,
                        sda_function,
                        next(iter(sda_nets)),
                    )
                )
    return tuple(sorted(found, key=lambda item: (item.pin.casefold(), item.role)))
