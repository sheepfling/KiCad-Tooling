"""Review candidates for UART-like endpoints missing from the project peer map."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, Protocol, cast

from .connector_identity import connector_candidate_references
from .models import NetlistContract
from .return_nets import is_return_like_net_name
from .serial_peer_models import (
    SerialDirectPeerRequirement,
    SerialPeerAnalysis,
    SerialShiftedPeerRequirement,
)

SerialPeerRosterState = Literal["not_configured", "pending", "not_applicable", "required"]


class _PinNetView(Protocol):
    pin: str


class _EndpointView(Protocol):
    tx: _PinNetView
    rx: _PinNetView


class _PeerWithEndpointView(Protocol):
    endpoint: _EndpointView


class _PeerLinkView(Protocol):
    endpoint: _EndpointView
    peer: object


class _PeerAnalysisView(Protocol):
    links: tuple[_PeerLinkView, ...]


@dataclass(frozen=True)
class SerialPeerRosterContext:
    """Authored serial-peer coverage state and its source binding for one lint run."""

    state: SerialPeerRosterState
    analysis: SerialPeerAnalysis | None = None
    source_path: str | None = None
    source_sha256: str | None = None


@dataclass(frozen=True)
class UnmappedSerialPeer:
    """Likely UART-like endpoint whose TX/RX pins are absent from the peer map."""

    reference: str
    channel: str
    tx_pins: tuple[str, ...]
    rx_pins: tuple[str, ...]
    signal_assignments: tuple[str, ...]
    discovery_basis: Literal["pin_function", "net_label"]


@dataclass(frozen=True)
class SerialNativePeerLink:
    """One directionally clear, directly shared native UART TX-to-RX net."""

    output_reference: str
    output_pin: str
    output_function: str
    output_type: str
    input_reference: str
    input_pin: str
    input_function: str
    input_type: str
    net: str


_SAFE_FUNCTION = re.compile(r"^[a-zA-Z0-9_ ]+$")
_IC_REFERENCE = re.compile(r"^(?:U|IC)[0-9]+$", re.IGNORECASE)
_PREFIXED_FUNCTION = re.compile(r"^(uart|usart)[_ ]*([0-9]*)[_ ]*(txd?|rxd?)$")
_UNPREFIXED_FUNCTION = re.compile(r"^(txd?|rxd?)[_ ]*([0-9]*)$")
_SERIAL_OUTPUT_TYPES = frozenset({"output", "tri_state", "bidirectional"})
_SERIAL_INPUT_TYPES = frozenset({"input", "bidirectional"})


def serial_function_role_and_channel(value: str) -> tuple[str, str] | None:
    """Recognize a deliberately small set of UART TX/RX pin-function spellings."""
    if not _SAFE_FUNCTION.fullmatch(value):
        return None
    function = value.strip().casefold()
    match = _PREFIXED_FUNCTION.fullmatch(function)
    if match is not None:
        prefix, number, role = match.groups()
        return ("tx" if role.startswith("tx") else "rx", f"{prefix}{number}")
    match = _UNPREFIXED_FUNCTION.fullmatch(function)
    if match is not None:
        role, number = match.groups()
        return ("tx" if role.startswith("tx") else "rx", f"index{number}" if number else "default")
    return None


def directly_linked_serial_peers(
    observed: NetlistContract,
    declared_connector_references: tuple[str, ...] = (),
) -> tuple[SerialNativePeerLink, ...]:
    """Find assigned UART TX-to-RX links between fitted ICs and connector candidates."""
    pin_nets: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin.casefold(), set()).add(net)

    references = {reference.casefold(): reference for reference in observed.components}
    dnp_references = {reference.casefold() for reference in observed.dnp_components}
    connector_references = {
        reference.casefold()
        for reference in connector_candidate_references(observed, declared_connector_references)
    }
    pin_types = {
        pin.casefold(): value.casefold() for pin, value in observed.pin_electrical_types.items()
    }
    by_net: dict[str, list[tuple[str, str, str, str, str]]] = {}
    for pin, function in observed.pin_functions.items():
        reference, separator, _number = pin.rpartition(".")
        reference_key = reference.casefold()
        canonical_reference = references.get(reference_key)
        if (
            not separator
            or canonical_reference is None
            or not (
                _IC_REFERENCE.fullmatch(canonical_reference)
                or reference_key in connector_references
            )
            or reference_key in dnp_references
        ):
            continue
        role_channel = serial_function_role_and_channel(function)
        if role_channel is None:
            continue
        electrical_type = pin_types.get(pin.casefold())
        assignment = pin_nets.get(pin.casefold(), set())
        if electrical_type is None or len(assignment) != 1:
            continue
        role, _channel = role_channel
        net = next(iter(assignment))
        if is_return_like_net_name(net):
            continue
        by_net.setdefault(net, []).append(
            (canonical_reference, pin, function, electrical_type, role)
        )

    links: set[SerialNativePeerLink] = set()
    for net, endpoints in sorted(by_net.items()):
        ordered_endpoints = sorted(endpoints)
        for left_index, left in enumerate(ordered_endpoints):
            for right in ordered_endpoints[left_index + 1 :]:
                left_reference, left_pin, left_function, left_type, left_role = left
                right_reference, right_pin, right_function, right_type, right_role = right
                if left_reference.casefold() == right_reference.casefold():
                    continue
                directions: list[SerialNativePeerLink] = []
                if (
                    left_role == "tx"
                    and left_type in _SERIAL_OUTPUT_TYPES
                    and (right_role == "rx" and right_type in _SERIAL_INPUT_TYPES)
                ):
                    directions.append(
                        SerialNativePeerLink(
                            output_reference=left_reference,
                            output_pin=left_pin,
                            output_function=left_function,
                            output_type=left_type,
                            input_reference=right_reference,
                            input_pin=right_pin,
                            input_function=right_function,
                            input_type=right_type,
                            net=net,
                        )
                    )
                if (
                    right_role == "tx"
                    and right_type in _SERIAL_OUTPUT_TYPES
                    and (left_role == "rx" and left_type in _SERIAL_INPUT_TYPES)
                ):
                    directions.append(
                        SerialNativePeerLink(
                            output_reference=right_reference,
                            output_pin=right_pin,
                            output_function=right_function,
                            output_type=right_type,
                            input_reference=left_reference,
                            input_pin=left_pin,
                            input_function=left_function,
                            input_type=left_type,
                            net=net,
                        )
                    )
                if len(directions) == 1:
                    links.add(directions[0])

    return tuple(
        sorted(
            links,
            key=lambda item: (
                item.output_reference.casefold(),
                item.input_reference.casefold(),
                item.net.casefold(),
                item.output_pin.casefold(),
                item.input_pin.casefold(),
            ),
        )
    )


def _mapped_endpoint_pin_pairs(analysis: SerialPeerAnalysis | None) -> set[tuple[str, str]]:
    if analysis is None:
        return set()
    pairs: set[tuple[str, str]] = set()
    analysis_view = cast(_PeerAnalysisView, analysis)
    for link in analysis_view.links:
        endpoints = [link.endpoint]
        if isinstance(link.peer, (SerialDirectPeerRequirement, SerialShiftedPeerRequirement)):
            peer = cast(_PeerWithEndpointView, link.peer)
            endpoints.append(peer.endpoint)
        pairs.update(
            (endpoint.tx.pin.casefold(), endpoint.rx.pin.casefold()) for endpoint in endpoints
        )
    return pairs


def unmapped_serial_peers(
    observed: NetlistContract,
    roster: SerialPeerRosterContext,
) -> tuple[UnmappedSerialPeer, ...]:
    """Find assigned TX/RX function pairs absent from the reviewed peer map.

    This is a review-only coverage prompt. It uses exported symbol pin functions
    and exact UART/USART net labels on fitted IC-to-connector paths. Explicit
    UART labels can expose alternate-function MCU pins whose native functions
    are named for package pins. It does not infer intent from component values
    or reference prefixes, and it does not declare that an endpoint must be
    connected or needs a peer.
    """
    pin_nets: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin.casefold(), set()).add(net)

    references = {reference.casefold(): reference for reference in observed.components}
    dnp_references = {reference.casefold() for reference in observed.dnp_components}
    analysis = roster.analysis
    mapped_pairs = _mapped_endpoint_pin_pairs(analysis)
    by_endpoint: dict[tuple[str, str], dict[str, list[tuple[str, str]]]] = {}

    for pin, function in observed.pin_functions.items():
        reference, separator, _pin_number = pin.rpartition(".")
        if not separator:
            continue
        canonical_reference = references.get(reference.casefold())
        if canonical_reference is None or canonical_reference.casefold() in dnp_references:
            continue
        assignment = pin_nets.get(pin.casefold(), set())
        if len(assignment) != 1:
            continue
        role_channel = serial_function_role_and_channel(function)
        if role_channel is None:
            continue
        role, channel = role_channel
        endpoint_key = (canonical_reference.casefold(), channel)
        by_endpoint.setdefault(endpoint_key, {}).setdefault(role, []).append(
            (pin, next(iter(assignment)))
        )

    connector_references = {
        reference.casefold(): reference for reference in connector_candidate_references(observed)
    }
    labelled_by_endpoint: dict[tuple[str, str], dict[str, list[tuple[str, str]]]] = {}
    labelled_connector_references: dict[tuple[str, str], dict[str, set[str]]] = {}
    for net, pins in sorted(observed.nets.items(), key=lambda item: item[0].casefold()):
        # Net names are a deliberately narrow discovery signal: bare TX/RX and
        # arbitrary suffix matches are not enough to classify a UART endpoint.
        signal_name = net.rsplit("/", 1)[-1].strip()
        role_channel = serial_function_role_and_channel(signal_name)
        if role_channel is None:
            continue
        role, channel = role_channel
        if not channel.startswith(("uart", "usart")):
            continue
        endpoint_pins: list[tuple[str, str]] = []
        net_connectors: set[str] = set()
        for pin in sorted(pins, key=str.casefold):
            reference, separator, number = pin.rpartition(".")
            reference_key = reference.casefold()
            canonical_reference = references.get(reference_key)
            if not separator or canonical_reference is None or reference_key in dnp_references:
                continue
            if reference_key in connector_references:
                net_connectors.add(reference_key)
                continue
            if not _IC_REFERENCE.fullmatch(canonical_reference):
                continue
            if number not in observed.component_pin_numbers.get(canonical_reference, ()):
                continue
            if pin_nets.get(pin.casefold(), set()) != {net}:
                continue
            # Native serial functions already have their own stricter path.
            # Do not reinterpret a pin whose declared function contradicts or
            # duplicates the role supplied by a net label.
            if serial_function_role_and_channel(observed.pin_functions.get(pin, "")) is not None:
                continue
            endpoint_pins.append((pin, net))
        if len(endpoint_pins) != 1 or not net_connectors:
            continue
        endpoint_key = (endpoint_pins[0][0].rsplit(".", 1)[0].casefold(), channel)
        labelled_by_endpoint.setdefault(endpoint_key, {}).setdefault(role, []).extend(endpoint_pins)
        labelled_connector_references.setdefault(endpoint_key, {}).setdefault(role, set()).update(
            net_connectors
        )

    findings: list[UnmappedSerialPeer] = []
    for (reference_key, channel), role_pins in sorted(by_endpoint.items()):
        tx = tuple(sorted(set(role_pins.get("tx", ()))))
        rx = tuple(sorted(set(role_pins.get("rx", ()))))
        if (
            not tx
            or not rx
            or not any(tx_net != rx_net for _tx_pin, tx_net in tx for _rx_pin, rx_net in rx)
        ):
            continue
        if any(
            (tx_pin.casefold(), rx_pin.casefold()) in mapped_pairs
            for tx_pin, _tx_net in tx
            for rx_pin, _rx_net in rx
        ):
            continue

        reference = references[reference_key]
        channel_label = (
            channel.upper()
            if channel in {"uart", "usart"} or channel.startswith(("uart", "usart"))
            else "TX/RX"
            if channel == "default"
            else f"channel {channel.removeprefix('index')}"
        )
        assignments = tuple(sorted({f"{pin}={net}" for pin, net in (*tx, *rx)}))
        findings.append(
            UnmappedSerialPeer(
                reference=reference,
                channel=channel_label,
                tx_pins=tuple(pin for pin, _net in tx),
                rx_pins=tuple(pin for pin, _net in rx),
                signal_assignments=assignments,
                discovery_basis="pin_function",
            )
        )

    for endpoint_key, role_pins in sorted(labelled_by_endpoint.items()):
        reference_key, channel = endpoint_key
        tx = tuple(sorted(set(role_pins.get("tx", ()))))
        rx = tuple(sorted(set(role_pins.get("rx", ()))))
        connector_roles = labelled_connector_references[endpoint_key]
        if (
            len(tx) != 1
            or len(rx) != 1
            or tx[0][1] == rx[0][1]
            or not (connector_roles.get("tx", set()) & connector_roles.get("rx", set()))
            or (tx[0][0].casefold(), rx[0][0].casefold()) in mapped_pairs
        ):
            continue
        reference = references[reference_key]
        channel_label = channel.upper() if channel.startswith(("uart", "usart")) else channel
        findings.append(
            UnmappedSerialPeer(
                reference=reference,
                channel=channel_label,
                tx_pins=(tx[0][0],),
                rx_pins=(rx[0][0],),
                signal_assignments=tuple(
                    sorted({f"{tx[0][0]}={tx[0][1]}", f"{rx[0][0]}={rx[0][1]}"})
                ),
                discovery_basis="net_label",
            )
        )

    unique = {
        (item.reference.casefold(), item.channel.casefold(), item.tx_pins, item.rx_pins): item
        for item in findings
    }
    return tuple(unique[key] for key in sorted(unique))
