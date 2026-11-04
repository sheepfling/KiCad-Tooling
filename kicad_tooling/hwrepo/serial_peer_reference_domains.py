"""Discover direct serial peers and their explicit reference domains."""

from __future__ import annotations

import re
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field
from types import MappingProxyType

from .netlist_contract_models import NetlistContract
from .peer_reference_assignments import peer_reference_assignments
from .serial_participants import serial_function_role_and_channel
from .serial_peer_reference_types import (
    SerialLabelPeerLink,
    SerialPeerPinIndex,
    SerialReferenceDomain,
    SerialReferencePinAssignment,
)

_IC_REFERENCE = re.compile(r"^(?:U|IC)[0-9]+$", re.IGNORECASE)

_SERIAL_CHANNEL_LABEL = re.compile(r"^(uart|usart)[_. ]*([0-9]+)[_. ]*(txd?|rxd?)$", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class _SerialLabelSignalAssignment:
    net: str
    first_pin: str
    second_pin: str


@dataclass(slots=True)
class _SerialLabelChannelAssignments:
    tx: list[_SerialLabelSignalAssignment] = field(
        default_factory=lambda: list[_SerialLabelSignalAssignment]()
    )
    rx: list[_SerialLabelSignalAssignment] = field(
        default_factory=lambda: list[_SerialLabelSignalAssignment]()
    )


def _serial_channel_label_role_and_channel(value: str) -> tuple[str, str] | None:
    """Recognize numbered UART/USART label leaves, including dotted channel forms."""
    label = value.rsplit("/", 1)[-1].strip()
    match = _SERIAL_CHANNEL_LABEL.fullmatch(label)
    if match is None:
        return None
    prefix, number, role = match.groups()
    return ("tx" if role.casefold().startswith("tx") else "rx", f"{prefix.casefold()}{number}")


def pin_index(
    observed: NetlistContract,
) -> SerialPeerPinIndex:
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
    functions = {pin.casefold(): value for pin, value in observed.pin_functions.items()}
    electrical_types = {
        pin.casefold(): value.casefold() for pin, value in observed.pin_electrical_types.items()
    }
    return SerialPeerPinIndex(
        pin_nets=MappingProxyType({key: frozenset(nets) for key, nets in pin_nets.items()}),
        references=MappingProxyType(references),
        symbols=MappingProxyType(symbols),
        footprints=MappingProxyType(footprints),
        pin_numbers=MappingProxyType(pin_numbers),
        dnp_references=frozenset(dnp),
        functions_by_pin_key=MappingProxyType(functions),
        electrical_types_by_pin_key=MappingProxyType(electrical_types),
    )


def reference_domain(
    reference: str,
    observed: NetlistContract,
    index: SerialPeerPinIndex,
    connector_references: AbstractSet[str],
) -> SerialReferenceDomain | None:
    reference_key = reference.casefold()
    if reference_key in index.dnp_references or not (
        _IC_REFERENCE.fullmatch(reference) or reference_key in connector_references
    ):
        return None
    numbers = index.pin_numbers.get(reference_key, ())
    if not numbers:
        return None

    evidence = peer_reference_assignments(reference, observed, index.pin_nets, numbers)
    if evidence.net is None:
        return None
    return SerialReferenceDomain(
        net=evidence.net,
        pins=tuple(
            SerialReferencePinAssignment(
                pin=item.pin,
                function=item.function,
                electrical_type=item.electrical_type,
                net=item.net,
            )
            for item in evidence.pins
        ),
    )


def labelled_direct_peer_links(
    observed: NetlistContract, index: SerialPeerPinIndex
) -> tuple[SerialLabelPeerLink, ...]:
    """Find exact UART/USART label pairs directly connecting the same two ICs.

    Labels are only a discovery clue. Each TX and RX net must contain exactly
    one pin on each of the same two fitted U/IC components. No connector or
    multi-hop path is inferred here.
    """
    by_channel_and_pair: dict[tuple[str, tuple[str, str]], _SerialLabelChannelAssignments] = {}

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
            canonical_reference = index.references.get(reference_key)
            pin_key = pin.casefold()
            function = index.functions_by_pin_key.get(pin_key)
            if (
                not separator
                or not number
                or canonical_reference is None
                or not _IC_REFERENCE.fullmatch(canonical_reference)
                or reference_key in index.dnp_references
                or index.pin_nets.get(pin_key, frozenset()) != frozenset({net})
                or function is None
                or pin_key not in index.electrical_types_by_pin_key
                or serial_function_role_and_channel(function) is not None
                or reference_key in pin_by_reference
            ):
                valid = False
                break
            pin_numbers = index.pin_numbers.get(reference_key, ())
            if number.casefold() not in {item.casefold() for item in pin_numbers}:
                valid = False
                break
            pin_by_reference[reference_key] = pin
        if not valid or len(pin_by_reference) != 2:
            continue
        first_reference_key, second_reference_key = sorted(pin_by_reference)
        pair = (first_reference_key, second_reference_key)
        group = by_channel_and_pair.setdefault((channel, pair), _SerialLabelChannelAssignments())
        assignment = _SerialLabelSignalAssignment(
            net=net,
            first_pin=pin_by_reference[first_reference_key],
            second_pin=pin_by_reference[second_reference_key],
        )
        (group.tx if role == "tx" else group.rx).append(assignment)

    links: list[SerialLabelPeerLink] = []
    for (channel, pair), assignments in sorted(by_channel_and_pair.items()):
        if len(assignments.tx) != 1 or len(assignments.rx) != 1:
            continue
        tx = assignments.tx[0]
        rx = assignments.rx[0]
        if (
            tx.net == rx.net
            or tx.first_pin.casefold() == rx.first_pin.casefold()
            or tx.second_pin.casefold() == rx.second_pin.casefold()
        ):
            continue
        first_key, second_key = pair
        links.append(
            SerialLabelPeerLink(
                channel=channel,
                tx_net=tx.net,
                rx_net=rx.net,
                first_reference=index.references[first_key],
                second_reference=index.references[second_key],
                first_tx_pin=tx.first_pin,
                second_tx_pin=tx.second_pin,
                first_rx_pin=rx.first_pin,
                second_rx_pin=rx.second_pin,
            )
        )
    return tuple(links)
