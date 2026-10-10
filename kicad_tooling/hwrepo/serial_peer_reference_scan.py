"""Coordinate serial peer reference checks and coverage results."""

from __future__ import annotations

from typing import Literal

from .connector_identity import connector_candidate_references
from .models import NetlistContract
from .serial_participants import directly_linked_serial_peers
from .serial_peer_models import SerialPeerAnalysis
from .serial_peer_reference_domains import (
    labelled_direct_peer_links,
    pin_index,
    reference_domain,
)
from .serial_peer_reference_mapping import fully_mapped_direct_link, fully_mapped_label_link
from .serial_peer_reference_types import (
    ReviewGroup,
    SerialPeerReferenceLinkCoverage,
    SerialPeerReferenceReview,
    SerialPeerReferenceScan,
)


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
    pin_nets, references, symbols, footprints, pin_numbers, dnp = pin_index(observed)
    connector_references = {
        reference.casefold()
        for reference in connector_candidate_references(observed, declared_connector_references)
    }
    native_links = directly_linked_serial_peers(observed, declared_connector_references)
    label_links = labelled_direct_peer_links(observed)
    supported_count = 0
    incomplete_count = 0
    common_count = 0
    separate_count = 0
    mapped_separate_count = 0
    link_entries: list[SerialPeerReferenceLinkCoverage] = []

    for link in native_links:
        output_domain = reference_domain(
            link.output_reference, observed, pin_nets, pin_numbers, dnp, connector_references
        )
        input_domain = reference_domain(
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
                mapped = fully_mapped_direct_link(
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
        first_domain = reference_domain(
            link.first_reference, observed, pin_nets, pin_numbers, dnp, connector_references
        )
        second_domain = reference_domain(
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
                mapped = fully_mapped_label_link(
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

    groups: dict[tuple[str, str, str, str], ReviewGroup] = {}
    for link in native_links:
        output_domain = reference_domain(
            link.output_reference, observed, pin_nets, pin_numbers, dnp, connector_references
        )
        input_domain = reference_domain(
            link.input_reference, observed, pin_nets, pin_numbers, dnp, connector_references
        )
        if (
            output_domain is None
            or input_domain is None
            or output_domain.net == input_domain.net
            or fully_mapped_direct_link(
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
            group = ReviewGroup(
                first_reference=first_reference,
                second_reference=second_reference,
                first_reference_domain=first_domain,
                second_reference_domain=second_domain,
            )
            groups[key] = group
        group.links.add(link)

    for link in label_links:
        first_domain = reference_domain(
            link.first_reference, observed, pin_nets, pin_numbers, dnp, connector_references
        )
        second_domain = reference_domain(
            link.second_reference, observed, pin_nets, pin_numbers, dnp, connector_references
        )
        if (
            first_domain is None
            or second_domain is None
            or first_domain.net == second_domain.net
            or fully_mapped_label_link(
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
            group = ReviewGroup(
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
