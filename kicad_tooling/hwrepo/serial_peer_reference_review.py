"""Review direct UART peers whose explicitly named reference pins use separate nets."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal, Protocol, cast

from .connector_pins import connector_candidate_references
from .models import (
    NetlistContract,
    ReferenceBondRequirement,
    SerialDirectPeerRequirement,
    SerialPeerAnalysis,
)
from .reference_bonds import reference_bond_issues
from .return_nets import is_return_like_net_name
from .serial_participants import (
    SerialNativePeerLink,
    directly_linked_serial_peers,
    serial_function_role_and_channel,
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


class _PinNetView(Protocol):
    pin: str
    net: str


class _SerialEndpointView(Protocol):
    reference: str
    symbol: str
    footprint: str
    tx: _PinNetView
    rx: _PinNetView
    reference_pins: tuple[_PinNetView, ...]


class _DirectPeerView(Protocol):
    endpoint: _SerialEndpointView


class _PeerLinkView(Protocol):
    endpoint: _SerialEndpointView
    peer: object
    reference_policy: str
    reference_bond: ReferenceBondRequirement | None


class _SerialAnalysisView(Protocol):
    links: tuple[_PeerLinkView, ...]


def _reference_policy_matches_native(link: _PeerLinkView, observed: NetlistContract) -> bool:
    if link.reference_policy in {"common_net", "separate_nets"}:
        return True
    if link.reference_policy == "bonded" and link.reference_bond is not None:
        return not reference_bond_issues(observed, link.reference_bond)
    return False


def _is_explicit_signal_reference_function(function: str) -> bool:
    normalized = _RETURN_FUNCTION_SUFFIX.sub("", function.strip())
    return not _NON_SIGNAL_REFERENCE_MARKER.search(normalized) and is_return_like_net_name(
        normalized
    )


@dataclass(frozen=True)
class SerialReferencePinAssignment:
    pin: str
    function: str
    electrical_type: str
    net: str


@dataclass(frozen=True)
class SerialReferenceDomain:
    net: str
    pins: tuple[SerialReferencePinAssignment, ...]


@dataclass(frozen=True)
class SerialPeerReferenceReview:
    first_reference: str
    second_reference: str
    first_reference_domain: SerialReferenceDomain
    second_reference_domain: SerialReferenceDomain
    links: tuple[SerialNativePeerLink, ...]
    label_links: tuple[SerialLabelPeerLink, ...] = ()


@dataclass(frozen=True)
class SerialPeerReferenceScan:
    """Reference-domain candidates with bounded peer and evidence counts."""

    reviews: tuple[SerialPeerReferenceReview, ...]
    link_entries: tuple[SerialPeerReferenceLinkCoverage, ...]
    native_peer_link_count: int
    label_peer_link_count: int
    supported_reference_link_count: int
    incomplete_reference_link_count: int
    common_reference_link_count: int
    separate_reference_link_count: int
    mapped_separate_reference_link_count: int

    @property
    def candidate_group_count(self) -> int:
        return len(self.reviews)


@dataclass(frozen=True)
class SerialPeerReferenceLinkCoverage:
    """Identity, signal evidence, and reference disposition for one discovered link."""

    discovery_basis: Literal["native_function", "channel_label"]
    first_reference: str
    second_reference: str
    signal_group: str
    signal_nets: tuple[str, ...]
    signal_pins: tuple[str, ...]
    disposition: Literal[
        "INCOMPLETE",
        "COMMON_REFERENCE",
        "SEPARATE_REFERENCE_REVIEW",
        "MAP_COVERED_SEPARATE_REFERENCE",
    ]


@dataclass(frozen=True)
class SerialLabelPeerLink:
    """Direct two-IC UART segment identified by an exact TX/RX channel label pair."""

    channel: str
    tx_net: str
    rx_net: str
    first_reference: str
    second_reference: str
    first_tx_pin: str
    second_tx_pin: str
    first_rx_pin: str
    second_rx_pin: str


@dataclass
class _ReviewGroup:
    first_reference: str
    second_reference: str
    first_reference_domain: SerialReferenceDomain
    second_reference_domain: SerialReferenceDomain
    links: set[SerialNativePeerLink] = field(default_factory=set)  # pyright: ignore[reportUnknownVariableType]
    label_links: set[SerialLabelPeerLink] = field(default_factory=set)  # pyright: ignore[reportUnknownVariableType]


def _pin_index(
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


def _reference_domain(
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


def _endpoint_matches_native(
    endpoint: _SerialEndpointView,
    pin_nets: dict[str, set[str]],
    references: dict[str, str],
    symbols: dict[str, str],
    footprints: dict[str, str],
    dnp: set[str],
) -> bool:
    reference = endpoint.reference
    reference_key = reference.casefold()
    if (
        reference_key not in references
        or reference_key in dnp
        or symbols.get(reference_key) != endpoint.symbol
        or footprints.get(reference_key) != endpoint.footprint
    ):
        return False
    assignments = (endpoint.tx, endpoint.rx, *endpoint.reference_pins)
    return all(pin_nets.get(item.pin.casefold(), set()) == {item.net} for item in assignments)


def _fully_mapped_direct_link(
    link: SerialNativePeerLink,
    analysis: SerialPeerAnalysis | None,
    observed: NetlistContract,
    output_domain: SerialReferenceDomain,
    input_domain: SerialReferenceDomain,
    pin_nets: dict[str, set[str]],
    references: dict[str, str],
    symbols: dict[str, str],
    footprints: dict[str, str],
    dnp: set[str],
) -> bool:
    if analysis is None:
        return False
    analysis_view = cast(_SerialAnalysisView, analysis)
    for item in analysis_view.links:
        if not isinstance(item.peer, SerialDirectPeerRequirement) or not (
            _reference_policy_matches_native(item, observed)
        ):
            continue
        peer = cast(_DirectPeerView, item.peer)
        endpoints = (item.endpoint, peer.endpoint)
        for output_endpoint, input_endpoint in (endpoints, endpoints[::-1]):
            if (
                output_endpoint.reference.casefold() != link.output_reference.casefold()
                or output_endpoint.tx.pin.casefold() != link.output_pin.casefold()
                or output_endpoint.tx.net != link.net
                or input_endpoint.reference.casefold() != link.input_reference.casefold()
                or input_endpoint.rx.pin.casefold() != link.input_pin.casefold()
                or input_endpoint.rx.net != link.net
            ):
                continue
            output_reference_pins = {
                (assignment.pin.casefold(), assignment.net)
                for assignment in output_endpoint.reference_pins
            }
            input_reference_pins = {
                (assignment.pin.casefold(), assignment.net)
                for assignment in input_endpoint.reference_pins
            }
            if output_reference_pins != {
                (assignment.pin.casefold(), assignment.net) for assignment in output_domain.pins
            } or input_reference_pins != {
                (assignment.pin.casefold(), assignment.net) for assignment in input_domain.pins
            }:
                continue
            if _endpoint_matches_native(
                output_endpoint, pin_nets, references, symbols, footprints, dnp
            ) and _endpoint_matches_native(
                input_endpoint, pin_nets, references, symbols, footprints, dnp
            ):
                return True
    return False


def _labelled_direct_peer_links(observed: NetlistContract) -> tuple[SerialLabelPeerLink, ...]:
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


def _fully_mapped_label_link(
    link: SerialLabelPeerLink,
    analysis: SerialPeerAnalysis | None,
    observed: NetlistContract,
    first_domain: SerialReferenceDomain,
    second_domain: SerialReferenceDomain,
    pin_nets: dict[str, set[str]],
    references: dict[str, str],
    symbols: dict[str, str],
    footprints: dict[str, str],
    dnp: set[str],
) -> bool:
    """Suppress only when an exact direct map covers the labeled signal pair and returns."""
    if analysis is None:
        return False
    analysis_view = cast(_SerialAnalysisView, analysis)
    observed_signal_assignments = {
        (link.first_tx_pin.casefold(), link.tx_net),
        (link.second_tx_pin.casefold(), link.tx_net),
        (link.first_rx_pin.casefold(), link.rx_net),
        (link.second_rx_pin.casefold(), link.rx_net),
    }
    for item in analysis_view.links:
        if not isinstance(item.peer, SerialDirectPeerRequirement) or not (
            _reference_policy_matches_native(item, observed)
        ):
            continue
        peer = cast(_DirectPeerView, item.peer)
        mapped_signal_assignments = {
            (endpoint.tx.pin.casefold(), endpoint.tx.net)
            for endpoint in (item.endpoint, peer.endpoint)
        } | {
            (endpoint.rx.pin.casefold(), endpoint.rx.net)
            for endpoint in (item.endpoint, peer.endpoint)
        }
        if mapped_signal_assignments != observed_signal_assignments:
            continue
        for first_endpoint, second_endpoint in (
            (item.endpoint, peer.endpoint),
            (peer.endpoint, item.endpoint),
        ):
            if (
                first_endpoint.reference.casefold() != link.first_reference.casefold()
                or second_endpoint.reference.casefold() != link.second_reference.casefold()
            ):
                continue
            first_reference_pins = {
                (assignment.pin.casefold(), assignment.net)
                for assignment in first_endpoint.reference_pins
            }
            second_reference_pins = {
                (assignment.pin.casefold(), assignment.net)
                for assignment in second_endpoint.reference_pins
            }
            if first_reference_pins != {
                (assignment.pin.casefold(), assignment.net) for assignment in first_domain.pins
            } or second_reference_pins != {
                (assignment.pin.casefold(), assignment.net) for assignment in second_domain.pins
            }:
                continue
            if _endpoint_matches_native(
                first_endpoint, pin_nets, references, symbols, footprints, dnp
            ) and _endpoint_matches_native(
                second_endpoint, pin_nets, references, symbols, footprints, dnp
            ):
                return True
    return False


def scan_serial_peer_reference_reviews(
    observed: NetlistContract,
    analysis: SerialPeerAnalysis | None = None,
    declared_connector_references: tuple[str, ...] = (),
) -> SerialPeerReferenceScan:
    """Find serial reference candidates and count supported applicability.

    Only fitted U/IC endpoints and connector candidates with a complete native
    pin/function/type inventory, one unambiguous return net per endpoint, and a
    directionally clear TX-to-RX connection are considered. A bounded label
    path also recognizes TX/RX channel labels that directly join the same two
    fitted ICs when their native pin functions are generic. An exact direct
    serial map with current identity, signal pins, and reference-pin assignments
    records reviewed intent and suppresses the prompt.
    """
    pin_nets, references, symbols, footprints, pin_numbers, dnp = _pin_index(observed)
    connector_references = {
        reference.casefold()
        for reference in connector_candidate_references(observed, declared_connector_references)
    }
    native_links = directly_linked_serial_peers(observed, declared_connector_references)
    label_links = _labelled_direct_peer_links(observed)
    supported_count = 0
    incomplete_count = 0
    common_count = 0
    separate_count = 0
    mapped_separate_count = 0
    link_entries: list[SerialPeerReferenceLinkCoverage] = []

    for link in native_links:
        output_domain = _reference_domain(
            link.output_reference, observed, pin_nets, pin_numbers, dnp, connector_references
        )
        input_domain = _reference_domain(
            link.input_reference, observed, pin_nets, pin_numbers, dnp, connector_references
        )
        if output_domain is None or input_domain is None:
            incomplete_count += 1
            disposition: Literal[
                "INCOMPLETE",
                "COMMON_REFERENCE",
                "SEPARATE_REFERENCE_REVIEW",
                "MAP_COVERED_SEPARATE_REFERENCE",
            ] = "INCOMPLETE"
        else:
            supported_count += 1
            if output_domain.net == input_domain.net:
                common_count += 1
                disposition = "COMMON_REFERENCE"
            else:
                separate_count += 1
                mapped = _fully_mapped_direct_link(
                    link,
                    analysis,
                    observed,
                    output_domain,
                    input_domain,
                    pin_nets,
                    references,
                    symbols,
                    footprints,
                    dnp,
                )
                if mapped:
                    mapped_separate_count += 1
                    disposition = "MAP_COVERED_SEPARATE_REFERENCE"
                else:
                    disposition = "SEPARATE_REFERENCE_REVIEW"
        link_entries.append(
            SerialPeerReferenceLinkCoverage(
                discovery_basis="native_function",
                first_reference=link.output_reference,
                second_reference=link.input_reference,
                signal_group=link.net,
                signal_nets=(link.net,),
                signal_pins=(link.output_pin, link.input_pin),
                disposition=disposition,
            )
        )

    for link in label_links:
        first_domain = _reference_domain(
            link.first_reference, observed, pin_nets, pin_numbers, dnp, connector_references
        )
        second_domain = _reference_domain(
            link.second_reference, observed, pin_nets, pin_numbers, dnp, connector_references
        )
        if first_domain is None or second_domain is None:
            incomplete_count += 1
            disposition = "INCOMPLETE"
        else:
            supported_count += 1
            if first_domain.net == second_domain.net:
                common_count += 1
                disposition = "COMMON_REFERENCE"
            else:
                separate_count += 1
                mapped = _fully_mapped_label_link(
                    link,
                    analysis,
                    observed,
                    first_domain,
                    second_domain,
                    pin_nets,
                    references,
                    symbols,
                    footprints,
                    dnp,
                )
                if mapped:
                    mapped_separate_count += 1
                    disposition = "MAP_COVERED_SEPARATE_REFERENCE"
                else:
                    disposition = "SEPARATE_REFERENCE_REVIEW"
        link_entries.append(
            SerialPeerReferenceLinkCoverage(
                discovery_basis="channel_label",
                first_reference=link.first_reference,
                second_reference=link.second_reference,
                signal_group=link.channel,
                signal_nets=(link.tx_net, link.rx_net),
                signal_pins=(
                    link.first_tx_pin,
                    link.second_tx_pin,
                    link.first_rx_pin,
                    link.second_rx_pin,
                ),
                disposition=disposition,
            )
        )

    groups: dict[tuple[str, str, str, str], _ReviewGroup] = {}
    for link in native_links:
        output_domain = _reference_domain(
            link.output_reference, observed, pin_nets, pin_numbers, dnp, connector_references
        )
        input_domain = _reference_domain(
            link.input_reference, observed, pin_nets, pin_numbers, dnp, connector_references
        )
        if (
            output_domain is None
            or input_domain is None
            or output_domain.net == input_domain.net
            or _fully_mapped_direct_link(
                link,
                analysis,
                observed,
                output_domain,
                input_domain,
                pin_nets,
                references,
                symbols,
                footprints,
                dnp,
            )
        ):
            continue
        domains = {
            link.output_reference.casefold(): output_domain,
            link.input_reference.casefold(): input_domain,
        }
        references_pair = tuple(
            sorted((link.output_reference, link.input_reference), key=str.casefold)
        )
        first_reference, second_reference = references_pair
        first_domain = domains[first_reference.casefold()]
        second_domain = domains[second_reference.casefold()]
        key = (
            first_reference.casefold(),
            second_reference.casefold(),
            first_domain.net,
            second_domain.net,
        )
        group = groups.get(key)
        if group is None:
            group = _ReviewGroup(
                first_reference=first_reference,
                second_reference=second_reference,
                first_reference_domain=first_domain,
                second_reference_domain=second_domain,
            )
            groups[key] = group
        group.links.add(link)

    for link in label_links:
        first_domain = _reference_domain(
            link.first_reference, observed, pin_nets, pin_numbers, dnp, connector_references
        )
        second_domain = _reference_domain(
            link.second_reference, observed, pin_nets, pin_numbers, dnp, connector_references
        )
        if (
            first_domain is None
            or second_domain is None
            or first_domain.net == second_domain.net
            or _fully_mapped_label_link(
                link,
                analysis,
                observed,
                first_domain,
                second_domain,
                pin_nets,
                references,
                symbols,
                footprints,
                dnp,
            )
        ):
            continue
        key = (
            link.first_reference.casefold(),
            link.second_reference.casefold(),
            first_domain.net,
            second_domain.net,
        )
        group = groups.get(key)
        if group is None:
            group = _ReviewGroup(
                first_reference=link.first_reference,
                second_reference=link.second_reference,
                first_reference_domain=first_domain,
                second_reference_domain=second_domain,
            )
            groups[key] = group
        group.label_links.add(link)

    reviews = tuple(
        SerialPeerReferenceReview(
            first_reference=group.first_reference,
            second_reference=group.second_reference,
            first_reference_domain=group.first_reference_domain,
            second_reference_domain=group.second_reference_domain,
            links=tuple(
                sorted(
                    group.links,
                    key=lambda item: (
                        item.net.casefold(),
                        item.output_pin.casefold(),
                        item.input_pin.casefold(),
                    ),
                )
            ),
            label_links=tuple(
                sorted(
                    group.label_links,
                    key=lambda item: (
                        item.channel.casefold(),
                        item.tx_net.casefold(),
                        item.rx_net.casefold(),
                        item.first_tx_pin.casefold(),
                        item.second_tx_pin.casefold(),
                    ),
                )
            ),
        )
        for _, group in sorted(groups.items())
    )
    return SerialPeerReferenceScan(
        reviews=reviews,
        link_entries=tuple(
            sorted(
                link_entries,
                key=lambda item: (
                    0 if item.discovery_basis == "native_function" else 1,
                    item.first_reference.casefold(),
                    item.first_reference,
                    item.second_reference.casefold(),
                    item.second_reference,
                    item.signal_group.casefold(),
                    item.signal_group,
                    tuple(value.casefold() for value in item.signal_nets),
                    item.signal_nets,
                    tuple(value.casefold() for value in item.signal_pins),
                    item.signal_pins,
                ),
            )
        ),
        native_peer_link_count=len(native_links),
        label_peer_link_count=len(label_links),
        supported_reference_link_count=supported_count,
        incomplete_reference_link_count=incomplete_count,
        common_reference_link_count=common_count,
        separate_reference_link_count=separate_count,
        mapped_separate_reference_link_count=mapped_separate_count,
    )


def unmapped_serial_peer_reference_reviews(
    observed: NetlistContract,
    analysis: SerialPeerAnalysis | None = None,
    declared_connector_references: tuple[str, ...] = (),
) -> tuple[SerialPeerReferenceReview, ...]:
    """Compatibility helper returning only the review candidates."""
    return scan_serial_peer_reference_reviews(
        observed,
        analysis,
        declared_connector_references,
    ).reviews
