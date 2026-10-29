"""Recognize open SPI clock pins on otherwise active channels."""

from __future__ import annotations

from dataclasses import dataclass

from .models import NetlistContract
from .spi_participants import is_spi_ic_reference, spi_signal_role_and_channel


@dataclass(frozen=True, slots=True)
class UnconnectedSpiClockPin:
    pin: str
    function: str
    channel: str
    active_peer_pins: tuple[str, ...]


def unconnected_spi_clock_function_pins(
    observed: NetlistContract,
) -> tuple[UnconnectedSpiClockPin, ...]:
    """Return open clocks when another recognized pin on that channel is assigned."""
    assignments: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            assignments.setdefault(pin.casefold(), set()).add(net)

    fitted = {reference.casefold() for reference in observed.components}
    dnp = {reference.casefold() for reference in observed.dnp_components}
    groups: dict[tuple[str, str], list[tuple[str, str, str, str]]] = {}
    for pin, function in observed.pin_functions.items():
        reference, separator, _number = pin.rpartition(".")
        if (
            not separator
            or reference.casefold() not in fitted
            or reference.casefold() in dnp
            or not is_spi_ic_reference(reference)
        ):
            continue
        identity = spi_signal_role_and_channel(function)
        if identity is None:
            continue
        role, channel = identity
        groups.setdefault((reference.casefold(), channel.casefold()), []).append(
            (pin, function, role, channel)
        )

    findings: list[UnconnectedSpiClockPin] = []
    for rows in groups.values():
        active_peers = tuple(
            sorted(
                pin
                for pin, _function, _role, _channel in rows
                if len(assignments.get(pin.casefold(), ())) == 1
            )
        )
        if not active_peers:
            continue
        for pin, function, role, channel in rows:
            if role == "clock" and not assignments.get(pin.casefold()):
                findings.append(
                    UnconnectedSpiClockPin(
                        pin=pin,
                        function=function,
                        channel=channel,
                        active_peer_pins=active_peers,
                    )
                )
    return tuple(sorted(findings, key=lambda item: (item.pin.casefold(), item.channel.casefold())))
