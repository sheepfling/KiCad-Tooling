"""Review crossed USB 2.0 data pairs between connector and PHY endpoints."""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet

from .bus_signal_pairs import usb_data_function_identity
from .connector_identity import connector_candidate_references
from .design_lint_types import Candidate
from .models import NetlistContract
from .usb_data_path_models import UsbDataPathMap
from .usb_peer_endpoint_analysis import (
    IC_REFERENCE,
    casefold_mapping,
    pin_net_index,
    usb_endpoints,
)
from .usb_peer_path_analysis import d_designated_shunt_branches

RULE_ID = "bus.usb_peer_data_pair_crossed"


def _crossed_net_shunts(
    connector_pins: tuple[str, ...],
    phy_pins: tuple[str, ...],
    net: str,
    endpoint_reference_nets: AbstractSet[str],
    net_members: Mapping[str, AbstractSet[str]],
    observed: NetlistContract,
) -> bool:
    endpoint_pins = {pin.casefold() for pin in (*connector_pins, *phy_pins)}
    members = net_members.get(net.casefold(), set())
    if not endpoint_pins <= members:
        return False
    return (
        d_designated_shunt_branches(
            observed,
            net,
            members - endpoint_pins,
            endpoint_reference_nets,
        )
        is not None
    )


def _mapped_pair(
    path_map: UsbDataPathMap | None,
    connector_reference: str,
    phy_reference: str,
    port_group: str | None,
) -> bool:
    if path_map is None:
        return False
    return any(
        item.connector_reference.casefold() == connector_reference.casefold()
        and item.phy_reference.casefold() == phy_reference.casefold()
        and item.data_port_group == port_group
        for item in path_map.interfaces
    )


def usb_peer_data_pair_crossing_candidates(
    observed: NetlistContract,
    path_map: UsbDataPathMap | None = None,
    declared_connector_references: tuple[str, ...] = (),
) -> tuple[Candidate, ...]:
    """Find direct cross-polarity USB 2.0 connector-to-PHY assignments.

    This deliberately requires an exact two-line path, allowing only the
    bounded D-designated protection branches already recognized by the USB
    peer analyzer. Labelled polarity contradictions remain with the dedicated
    USB pin/net-name rule, and authored interface maps remain with their exact
    path-contract check.
    """
    pin_nets, net_members = pin_net_index(observed)
    connector_references = connector_candidate_references(
        observed,
        declared_connector_references,
    )
    connector_keys = {item.casefold() for item in connector_references}
    phy_references = tuple(
        reference
        for reference in sorted(observed.components, key=lambda item: (item.casefold(), item))
        if reference.casefold() not in connector_keys and IC_REFERENCE.fullmatch(reference)
    )
    connectors = usb_endpoints(
        connector_references,
        observed,
        pin_nets,
        connector=True,
    )
    phys = usb_endpoints(
        phy_references,
        observed,
        pin_nets,
        connector=False,
    )
    symbols = casefold_mapping(observed.component_symbols)
    components = casefold_mapping(observed.components)
    findings: list[Candidate] = []

    for connector in connectors:
        for phy in phys:
            if (
                connector.signal_family != "USB 2.0 data"
                or phy.signal_family != "USB 2.0 data"
                or connector.port_group != phy.port_group
                or _mapped_pair(
                    path_map,
                    connector.reference,
                    phy.reference,
                    connector.port_group,
                )
                or connector.positive_net.casefold() != phy.negative_net.casefold()
                or connector.negative_net.casefold() != phy.positive_net.casefold()
            ):
                continue

            # When a net label already states USB D+/D- polarity, the existing
            # label-mismatch lint owns the more direct diagnosis.
            if any(
                usb_data_function_identity(net) is not None
                for net in (connector.positive_net, connector.negative_net)
            ):
                continue

            reference_nets = {
                connector.reference_net.casefold(),
                phy.reference_net.casefold(),
            }
            if not _crossed_net_shunts(
                connector.positive_pins,
                phy.negative_pins,
                connector.positive_net,
                reference_nets,
                net_members,
                observed,
            ) or not _crossed_net_shunts(
                connector.negative_pins,
                phy.positive_pins,
                connector.negative_net,
                reference_nets,
                net_members,
                observed,
            ):
                continue

            connector_component = components.get(connector.reference.casefold())
            phy_component = components.get(phy.reference.casefold())
            connector_identity = (
                f"{connector.reference}: {symbols.get(connector.reference.casefold(), connector.symbol)}; "
                f"{connector_component.footprint if connector_component is not None else connector.footprint}"
            )
            phy_identity = (
                f"{phy.reference}: {symbols.get(phy.reference.casefold(), phy.symbol)}; "
                f"{phy_component.footprint if phy_component is not None else phy.footprint}"
            )
            findings.append(
                Candidate(
                    rule_id=RULE_ID,
                    subject=f"{connector.reference} / {phy.reference}: USB 2.0 data pair is crossed",
                    message=(
                        "The connector D+ pins share a native net with PHY D− pins, and connector "
                        "D− pins share a net with PHY D+ pins. Review the endpoint pin map and "
                        "intended path. Native function names identify a candidate; this check does "
                        "not verify physical routing or device behavior."
                    ),
                    evidence={
                        "connector": (connector_identity,),
                        "phy": (phy_identity,),
                        "connector_positive_pins": connector.positive_pins,
                        "connector_positive_net": (connector.positive_net,),
                        "phy_negative_pins": phy.negative_pins,
                        "connector_negative_pins": connector.negative_pins,
                        "connector_negative_net": (connector.negative_net,),
                        "phy_positive_pins": phy.positive_pins,
                        "connector_reference_net": (connector.reference_net,),
                        "phy_reference_net": (phy.reference_net,),
                        "connector_port_group": (connector.port_group or "unindexed",),
                        "phy_port_group": (phy.port_group or "unindexed",),
                    },
                )
            )

    return tuple(
        sorted(
            findings,
            key=lambda item: (item.subject.casefold(), item.subject),
        )
    )
