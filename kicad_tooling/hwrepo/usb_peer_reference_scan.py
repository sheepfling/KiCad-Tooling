"""Coordinate deterministic USB peer-reference review and coverage."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Literal

from .connector_identity import connector_candidate_references
from .models import NetlistContract, UsbDataPathMap
from .usb_peer_endpoint_analysis import (
    IC_REFERENCE,
    pin_net_index,
    recognized_usb_data_groups,
    usb_endpoints,
)
from .usb_peer_path_analysis import usb_data_link
from .usb_peer_reference_contract import usb_reference_map_matches
from .usb_peer_reference_types import (
    UsbPeerEndpointGroupCoverage,
    UsbPeerReferenceCoverage,
    UsbPeerReferencePathCoverage,
    UsbPeerReferenceReview,
    UsbPeerReferenceScan,
)


def scan_usb_peer_reference_reviews(
    observed: NetlistContract,
    path_map: UsbDataPathMap | None = None,
    declared_connector_references: tuple[str, ...] = (),
) -> UsbPeerReferenceScan:
    """Scan supported USB peers and count bounded heuristic applicability.

    Both fitted endpoints need complete native pin inventories and one or more
    same-net positive and negative USB data pins within one port group, plus
    uniquely assigned passive/power_in reference pins on one net. Numbered
    DPn/DMn aliases pair only with the same number; unnumbered D+/D- aliases
    pair with each other or with one numbered endpoint group. Each data line must be direct
    or joined by exactly one fitted two-pin Device:R between endpoint nets.
    Complete two-pin passive diode-designated shunts to either endpoint
    reference may also appear on those nets. Longer series paths, extra data
    peers, DNP parts, multi-pin protection parts, and mixed reference domains
    remain outside this bounded topology check.
    """
    pin_nets, net_members = pin_net_index(observed)
    connector_candidates = connector_candidate_references(observed, declared_connector_references)
    connector_references = {item.casefold() for item in connector_candidates}
    connectors = usb_endpoints(
        connector_candidates,
        observed,
        pin_nets,
        connector=True,
    )
    phy_references = tuple(
        reference
        for reference in sorted(observed.components, key=lambda item: (item.casefold(), item))
        if reference.casefold() not in connector_references
        and IC_REFERENCE.fullmatch(reference) is not None
    )
    phy_endpoints = usb_endpoints(
        phy_references,
        observed,
        pin_nets,
        connector=False,
    )
    dnp = {reference.casefold() for reference in observed.dnp_components}
    supported_connector_groups = {
        (endpoint.reference.casefold(), endpoint.port_group) for endpoint in connectors
    }
    supported_phy_groups = {
        (endpoint.reference.casefold(), endpoint.port_group) for endpoint in phy_endpoints
    }

    def group_coverage(
        references: Iterable[str],
        *,
        endpoint_role: Literal["connector", "phy"],
        supported: set[tuple[str, str | None]],
    ) -> tuple[UsbPeerEndpointGroupCoverage, ...]:
        result: list[UsbPeerEndpointGroupCoverage] = []
        for reference in references:
            reference_key = reference.casefold()
            for port_group, _sides in recognized_usb_data_groups(observed, reference):
                disposition: Literal["SUPPORTED", "INCOMPLETE", "DNP"] = (
                    "DNP"
                    if reference_key in dnp
                    else "SUPPORTED"
                    if (reference_key, port_group) in supported
                    else "INCOMPLETE"
                )
                result.append(
                    UsbPeerEndpointGroupCoverage(
                        endpoint_role=endpoint_role,
                        reference=reference,
                        port_group=port_group,
                        disposition=disposition,
                    )
                )
        return tuple(result)

    endpoint_groups = tuple(
        sorted(
            (
                *group_coverage(
                    connector_candidates,
                    endpoint_role="connector",
                    supported=supported_connector_groups,
                ),
                *group_coverage(
                    phy_references,
                    endpoint_role="phy",
                    supported=supported_phy_groups,
                ),
            ),
            key=lambda item: (
                0 if item.endpoint_role == "connector" else 1,
                item.reference.casefold(),
                item.reference,
                item.port_group is not None,
                int(item.port_group) if item.port_group is not None else -1,
            ),
        )
    )
    recognized_connector_group_count = sum(
        item.endpoint_role == "connector" for item in endpoint_groups
    )
    recognized_phy_group_count = sum(item.endpoint_role == "phy" for item in endpoint_groups)
    dnp_group_count = sum(item.disposition == "DNP" for item in endpoint_groups)
    incomplete_group_count = sum(item.disposition == "INCOMPLETE" for item in endpoint_groups)

    findings: list[UsbPeerReferenceReview] = []
    path_entries: list[UsbPeerReferencePathCoverage] = []
    for connector in connectors:
        for phy in phy_endpoints:
            data_link = usb_data_link(connector, phy, net_members, observed)
            if data_link is None:
                continue
            common_reference = connector.reference_net.casefold() == phy.reference_net.casefold()
            mapped_separate_reference = not common_reference and usb_reference_map_matches(
                connector, phy, data_link, path_map
            )
            reference_disposition: Literal[
                "COMMON_REFERENCE",
                "SEPARATE_REFERENCE_REVIEW",
                "MAP_COVERED_SEPARATE_REFERENCE",
            ] = (
                "COMMON_REFERENCE"
                if common_reference
                else "MAP_COVERED_SEPARATE_REFERENCE"
                if mapped_separate_reference
                else "SEPARATE_REFERENCE_REVIEW"
            )
            path_entries.append(
                UsbPeerReferencePathCoverage(
                    connector_reference=connector.reference,
                    phy_reference=phy.reference,
                    connector_symbol=connector.symbol,
                    phy_symbol=phy.symbol,
                    connector_footprint=connector.footprint,
                    phy_footprint=phy.footprint,
                    connector_reference_net=connector.reference_net,
                    phy_reference_net=phy.reference_net,
                    connector_reference_pins=connector.reference_pins,
                    phy_reference_pins=phy.reference_pins,
                    reference_disposition=reference_disposition,
                    data_link=data_link,
                )
            )
            if common_reference or mapped_separate_reference:
                continue
            findings.append(
                UsbPeerReferenceReview(
                    connector_reference=connector.reference,
                    phy_reference=phy.reference,
                    connector_symbol=connector.symbol,
                    phy_symbol=phy.symbol,
                    connector_footprint=connector.footprint,
                    phy_footprint=phy.footprint,
                    connector_reference_net=connector.reference_net,
                    phy_reference_net=phy.reference_net,
                    connector_reference_pins=connector.reference_pins,
                    phy_reference_pins=phy.reference_pins,
                    data_link=data_link,
                )
            )
    reviews = tuple(
        sorted(
            findings,
            key=lambda item: (
                item.connector_reference.casefold(),
                item.phy_reference.casefold(),
                item.connector_reference_net.casefold(),
                item.phy_reference_net.casefold(),
                item.data_link.port_group is not None,
                (int(item.data_link.port_group) if item.data_link.port_group is not None else -1),
            ),
        )
    )
    ordered_path_entries = tuple(
        sorted(
            path_entries,
            key=lambda item: (
                item.connector_reference.casefold(),
                item.connector_reference,
                item.phy_reference.casefold(),
                item.phy_reference,
                item.data_link.port_group is not None,
                item.data_link.port_group or "",
            ),
        )
    )
    common_reference_path_count = sum(
        item.reference_disposition == "COMMON_REFERENCE" for item in ordered_path_entries
    )
    separate_reference_path_count = sum(
        item.reference_disposition != "COMMON_REFERENCE" for item in ordered_path_entries
    )
    mapped_separate_reference_path_count = sum(
        item.reference_disposition == "MAP_COVERED_SEPARATE_REFERENCE"
        for item in ordered_path_entries
    )
    return UsbPeerReferenceScan(
        reviews=reviews,
        coverage=UsbPeerReferenceCoverage(
            endpoint_groups=endpoint_groups,
            path_entries=ordered_path_entries,
            recognized_connector_group_count=recognized_connector_group_count,
            supported_connector_group_count=sum(
                item.endpoint_role == "connector" and item.disposition == "SUPPORTED"
                for item in endpoint_groups
            ),
            recognized_phy_group_count=recognized_phy_group_count,
            supported_phy_group_count=sum(
                item.endpoint_role == "phy" and item.disposition == "SUPPORTED"
                for item in endpoint_groups
            ),
            dnp_group_count=dnp_group_count,
            incomplete_group_count=incomplete_group_count,
            supported_data_path_count=len(ordered_path_entries),
            common_reference_path_count=common_reference_path_count,
            separate_reference_path_count=separate_reference_path_count,
            mapped_separate_reference_path_count=mapped_separate_reference_path_count,
            review_candidate_group_count=len(reviews),
        ),
    )


def usb_peer_reference_reviews(
    observed: NetlistContract,
    path_map: UsbDataPathMap | None = None,
    declared_connector_references: tuple[str, ...] = (),
) -> tuple[UsbPeerReferenceReview, ...]:
    """Prompt on supported USB 2.0 peers with different explicit references."""
    return scan_usb_peer_reference_reviews(
        observed, path_map, declared_connector_references
    ).reviews
