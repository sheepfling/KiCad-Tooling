"""Discover direct serial peers and their explicit reference domains."""

from __future__ import annotations

import re

from .models import NetlistContract
from .return_nets import is_return_like_net_name
from .serial_participants import serial_function_role_and_channel
from .serial_peer_reference_types import (
    SerialLabelPeerLink,
    SerialReferenceDomain,
    SerialReferencePinAssignment,
)

_IC_REFERENCE = re.compile(r"^(?:U|IC)[0-9]+$", re.IGNORECASE)


_RETURN_FUNCTION_SUFFIX = re.compile(r"\d+$")


_NON_SIGNAL_REFERENCE_MARKER = re.compile(
    r"(?:^|[^A-Z0-9])(?:CHASSIS|SHIELD|FRAME|PE)(?:$|[^A-Z0-9])",
    re.IGNORECASE,
)


_RETURN_PIN_TYPES = frozenset({"passive", "power_in"})


_SERIAL_CHANNEL_LABEL = re.compile(r"^(uart|usart)[_. ]*([0-9]+)[_. ]*(txd?|rxd?)$", re.IGNORECASE)


def _serial_channel_label_role_and_channel(value: str) -> tuple[str, str] | None:
    """Recognize numbered UART/USART label leaves, including dotted channel forms."""
    label = value.rsplit("/", 1)[-1].strip()
    match = _SERIAL_CHANNEL_LABEL.fullmatch(label)
    if match is None:
        return None
    prefix, number, role = match.groups()
    return ("tx" if role.casefold().startswith("tx") else "rx", f"{prefix.casefold()}{number}")


def _is_explicit_signal_reference_function(function: str) -> bool:
    normalized = _RETURN_FUNCTION_SUFFIX.sub("", function.strip())
    return not _NON_SIGNAL_REFERENCE_MARKER.search(normalized) and is_return_like_net_name(
        normalized
    )


def pin_index(
    observed: NetlistContract,
) -> tuple[
    dict[str, set[str]],
    dict[str, str],
    dict[str, str],
    dict[str, str],
    dict[str, tuple[str, ...]],
    set[str],
]:
    pin_nets: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin.casefold(), set()).add(net)
    references = {reference.casefold(): reference for reference in observed.components}
    symbols = {
        reference.casefold(): symbol for reference, symbol in observed.component_symbols.items()
    }
    footprints = {
        reference.casefold(): component.footprint
        for reference, component in observed.components.items()
    }
    pin_numbers = {
        reference.casefold(): tuple(numbers)
        for reference, numbers in observed.component_pin_numbers.items()
    }
    dnp = {reference.casefold() for reference in observed.dnp_components}
    return (
        pin_nets,
        references,
        symbols,
        footprints,
        pin_numbers,
        dnp,
    )


def reference_domain(
    reference: str,
    observed: NetlistContract,
    pin_nets: dict[str, set[str]],
    pin_numbers: dict[str, tuple[str, ...]],
    dnp: set[str],
    connector_references: set[str],
) -> SerialReferenceDomain | None:
    reference_key = reference.casefold()
    if reference_key in dnp or not (
        _IC_REFERENCE.fullmatch(reference) or reference_key in connector_references
    ):
        return None
    numbers = pin_numbers.get(reference_key, ())
    if not numbers:
        return None

    functions = {pin.casefold(): value for pin, value in observed.pin_functions.items()}
    electrical_types = {
        pin.casefold(): value.casefold() for pin, value in observed.pin_electrical_types.items()
    }
    assignments: list[SerialReferencePinAssignment] = []
    for number in numbers:
        pin = f"{reference}.{number}"
        pin_key = pin.casefold()
        function = functions.get(pin_key)
        electrical_type = electrical_types.get(pin_key)
        if function is None or electrical_type is None:
            return None
        if not _is_explicit_signal_reference_function(function):
            continue
        if electrical_type not in _RETURN_PIN_TYPES:
            return None
        nets = pin_nets.get(pin_key, set())
        if len(nets) != 1:
            return None
        assignments.append(
            SerialReferencePinAssignment(
                pin=pin,
                function=function,
                electrical_type=electrical_type,
                net=next(iter(nets)),
            )
        )

    if not assignments:
        return None
    nets = {item.net for item in assignments}
    if len(nets) != 1:
        return None
    return SerialReferenceDomain(
        net=next(iter(nets)),
        pins=tuple(sorted(assignments, key=lambda item: item.pin.casefold())),
    )


def labelled_direct_peer_links(observed: NetlistContract) -> tuple[SerialLabelPeerLink, ...]:
    """Find exact UART/USART label pairs directly connecting the same two ICs.

    Labels are only a discovery clue. Each TX and RX net must contain exactly
    one pin on each of the same two fitted U/IC components. No connector or
    multi-hop path is inferred here.
    """
    pin_nets: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin.casefold(), set()).add(net)
    references = {reference.casefold(): reference for reference in observed.components}
    dnp = {reference.casefold() for reference in observed.dnp_components}
    functions = {pin.casefold(): value for pin, value in observed.pin_functions.items()}
    electrical_types = {
        pin.casefold(): value.casefold() for pin, value in observed.pin_electrical_types.items()
    }
    by_channel_and_pair: dict[
        tuple[str, tuple[str, str]], dict[str, list[tuple[str, dict[str, str]]]]
    ] = {}

    for net, pins in sorted(observed.nets.items(), key=lambda item: item[0].casefold()):
        signal_name = net.rsplit("/", 1)[-1].strip()
        role_channel = _serial_channel_label_role_and_channel(signal_name)
        if role_channel is None:
            continue
        role, channel = role_channel
        if len(pins) != 2:
            continue
        pin_by_reference: dict[str, str] = {}
        valid = True
        for pin in pins:
            reference, separator, number = pin.rpartition(".")
            reference_key = reference.casefold()
            canonical_reference = references.get(reference_key)
            pin_key = pin.casefold()
            function = functions.get(pin_key)
            if (
                not separator
                or not number
                or canonical_reference is None
                or not _IC_REFERENCE.fullmatch(canonical_reference)
                or reference_key in dnp
                or pin_nets.get(pin_key, set()) != {net}
                or function is None
                or pin_key not in electrical_types
                or serial_function_role_and_channel(function) is not None
                or reference_key in pin_by_reference
            ):
                valid = False
                break
            pin_numbers = {
                item.casefold()
                for item in observed.component_pin_numbers.get(canonical_reference, ())
            }
            if number.casefold() not in pin_numbers:
                valid = False
                break
            pin_by_reference[reference_key] = pin
        if not valid or len(pin_by_reference) != 2:
            continue
        first_reference_key, second_reference_key = sorted(pin_by_reference)
        pair = (first_reference_key, second_reference_key)
        by_channel_and_pair.setdefault((channel, pair), {}).setdefault(role, []).append(
            (net, pin_by_reference)
        )

    links: list[SerialLabelPeerLink] = []
    for (channel, pair), roles in sorted(by_channel_and_pair.items()):
        tx_rows = roles.get("tx", [])
        rx_rows = roles.get("rx", [])
        if len(tx_rows) != 1 or len(rx_rows) != 1:
            continue
        tx_net, tx_pins = tx_rows[0]
        rx_net, rx_pins = rx_rows[0]
        if tx_net == rx_net or set(tx_pins) != set(pair) or set(rx_pins) != set(pair):
            continue
        if any(
            tx_pins[reference].casefold() == rx_pins[reference].casefold() for reference in pair
        ):
            continue
        first_key, second_key = pair
        links.append(
            SerialLabelPeerLink(
                channel=channel,
                tx_net=tx_net,
                rx_net=rx_net,
                first_reference=references[first_key],
                second_reference=references[second_key],
                first_tx_pin=tx_pins[first_key],
                second_tx_pin=tx_pins[second_key],
                first_rx_pin=rx_pins[first_key],
                second_rx_pin=rx_pins[second_key],
            )
        )
    return tuple(links)
