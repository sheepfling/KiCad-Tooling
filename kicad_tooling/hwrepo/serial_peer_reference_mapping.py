"""Validate current project maps for serial peers with split references."""

from __future__ import annotations

from typing import cast

from kicad_tooling.hwrepo.serial_peer_models import (
    SerialDirectPeerRequirement,
    SerialExternalPeerRequirement,
    SerialPeerAnalysis,
    SerialShiftedPeerRequirement,
)

from .netlist_contract_models import NetlistContract
from .reference_bonds import reference_bond_issues
from .serial_participants import SerialNativePeerLink
from .serial_peer_reference_types import (
    DirectPeerView,
    PeerLinkView,
    SerialAnalysisView,
    SerialEndpointView,
    SerialLabelPeerLink,
    SerialPeerPinIndex,
    SerialReferenceDomain,
)


def _reference_policy_matches_native(link: PeerLinkView, observed: NetlistContract) -> bool:
    if link.reference_policy in {"common_net", "separate_nets"}:
        return True
    if link.reference_policy == "bonded" and link.reference_bond is not None:
        return not reference_bond_issues(observed, link.reference_bond)
    return False


def _endpoint_matches_native(
    endpoint: SerialEndpointView,
    index: SerialPeerPinIndex,
) -> bool:
    reference = endpoint.reference
    reference_key = reference.casefold()
    if (
        reference_key not in index.references
        or reference_key in index.dnp_references
        or index.symbols.get(reference_key) != endpoint.symbol
        or index.footprints.get(reference_key) != endpoint.footprint
    ):
        return False
    assignments = (endpoint.tx, endpoint.rx, *endpoint.reference_pins)
    return all(
        index.pin_nets.get(item.pin.casefold(), frozenset()) == frozenset({item.net})
        for item in assignments
    )


def fully_mapped_direct_link(
    link: SerialNativePeerLink,
    analysis: SerialPeerAnalysis | None,
    observed: NetlistContract,
    output_domain: SerialReferenceDomain,
    input_domain: SerialReferenceDomain,
    index: SerialPeerPinIndex,
) -> bool:
    if analysis is None:
        return False
    analysis_view = cast(SerialAnalysisView, analysis)
    for item in analysis_view.links:
        peer: (
            SerialDirectPeerRequirement
            | SerialShiftedPeerRequirement
            | SerialExternalPeerRequirement
        ) = item.peer
        if not isinstance(peer, SerialDirectPeerRequirement) or not (
            _reference_policy_matches_native(item, observed)
        ):
            continue
        direct_peer = cast(DirectPeerView, peer)
        endpoints = (item.endpoint, direct_peer.endpoint)
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
            if _endpoint_matches_native(output_endpoint, index) and _endpoint_matches_native(
                input_endpoint, index
            ):
                return True
    return False


def fully_mapped_label_link(
    link: SerialLabelPeerLink,
    analysis: SerialPeerAnalysis | None,
    observed: NetlistContract,
    first_domain: SerialReferenceDomain,
    second_domain: SerialReferenceDomain,
    index: SerialPeerPinIndex,
) -> bool:
    """Suppress only when an exact direct map covers the labeled signal pair and returns."""
    if analysis is None:
        return False
    analysis_view = cast(SerialAnalysisView, analysis)
    observed_signal_assignments = {
        (link.first_tx_pin.casefold(), link.tx_net),
        (link.second_tx_pin.casefold(), link.tx_net),
        (link.first_rx_pin.casefold(), link.rx_net),
        (link.second_rx_pin.casefold(), link.rx_net),
    }
    for item in analysis_view.links:
        peer: (
            SerialDirectPeerRequirement
            | SerialShiftedPeerRequirement
            | SerialExternalPeerRequirement
        ) = item.peer
        if not isinstance(peer, SerialDirectPeerRequirement) or not (
            _reference_policy_matches_native(item, observed)
        ):
            continue
        direct_peer = cast(DirectPeerView, peer)
        mapped_signal_assignments = {
            (endpoint.tx.pin.casefold(), endpoint.tx.net)
            for endpoint in (item.endpoint, direct_peer.endpoint)
        } | {
            (endpoint.rx.pin.casefold(), endpoint.rx.net)
            for endpoint in (item.endpoint, direct_peer.endpoint)
        }
        if mapped_signal_assignments != observed_signal_assignments:
            continue
        for first_endpoint, second_endpoint in (
            (item.endpoint, direct_peer.endpoint),
            (direct_peer.endpoint, item.endpoint),
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
            if _endpoint_matches_native(first_endpoint, index) and _endpoint_matches_native(
                second_endpoint, index
            ):
                return True
    return False
