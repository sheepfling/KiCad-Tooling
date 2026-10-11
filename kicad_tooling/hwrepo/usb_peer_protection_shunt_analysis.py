"""Recognize USB paths with exact project-mapped multi-pin protection shunts."""

from __future__ import annotations

from .models import NetlistContract
from .usb_data_path_models import UsbDataInterfaceRequirement, UsbDataPathMap
from .usb_data_paths import usb_data_path_mismatches
from .usb_peer_endpoint_analysis import pin_net_index
from .usb_peer_path_analysis import d_designated_shunt_branches
from .usb_peer_reference_types import (
    UsbEndpoint,
    UsbPeerDataLink,
    UsbPeerDataProtectionShunt,
    UsbPeerDataProtectionShuntPin,
    UsbPeerDataShuntBranch,
)


def _interface_matches(
    interface: UsbDataInterfaceRequirement,
    connector: UsbEndpoint,
    phy: UsbEndpoint,
) -> bool:
    if (
        interface.connector_reference.casefold() != connector.reference.casefold()
        or interface.phy_reference.casefold() != phy.reference.casefold()
        or interface.expected_connector_symbol != connector.symbol
        or interface.expected_phy_symbol != phy.symbol
        or interface.expected_connector_footprint != connector.footprint
        or interface.expected_phy_footprint != phy.footprint
        or interface.data_port_group is not None
        and interface.data_port_group not in {connector.port_group, phy.port_group}
    ):
        return False
    return (
        interface.positive.topology == "direct"
        and interface.positive.connector_net.casefold() == connector.positive_net.casefold()
        and interface.positive.phy_net.casefold() == phy.positive_net.casefold()
        and {pin.casefold() for pin in interface.positive.connector_pins}
        == {pin.casefold() for pin in connector.positive_pins}
        and {pin.casefold() for pin in interface.positive.phy_pins}
        == {pin.casefold() for pin in phy.positive_pins}
        and interface.negative.topology == "direct"
        and interface.negative.connector_net.casefold() == connector.negative_net.casefold()
        and interface.negative.phy_net.casefold() == phy.negative_net.casefold()
        and {pin.casefold() for pin in interface.negative.connector_pins}
        == {pin.casefold() for pin in connector.negative_pins}
        and {pin.casefold() for pin in interface.negative.phy_pins}
        == {pin.casefold() for pin in phy.negative_pins}
    )


def _mapped_data_pins(interface: UsbDataInterfaceRequirement, line: str) -> set[str]:
    return {
        item.pin.casefold()
        for shunt in interface.protection_shunts
        for item in shunt.data_pins
        if item.line == line
    }


def _matched_protection_shunts(
    interface: UsbDataInterfaceRequirement,
) -> tuple[UsbPeerDataProtectionShunt, ...]:
    return tuple(
        sorted(
            (
                UsbPeerDataProtectionShunt(
                    reference=shunt.reference,
                    symbol=shunt.expected_symbol,
                    footprint=shunt.expected_footprint,
                    data_pins=tuple(
                        UsbPeerDataProtectionShuntPin(
                            line=item.line,
                            pin=item.pin,
                            net=item.net,
                        )
                        for item in sorted(
                            shunt.data_pins,
                            key=lambda item: (item.line, item.pin.casefold(), item.pin),
                        )
                    ),
                    pin_assignments=tuple(
                        sorted(
                            (
                                f"{item.pin}={item.net}"
                                if item.disposition == "net"
                                else f"{item.pin}=<unconnected>"
                                for item in shunt.pins
                            ),
                            key=lambda item: (item.casefold(), item),
                        )
                    ),
                )
                for shunt in interface.protection_shunts
            ),
            key=lambda item: (item.reference.casefold(), item.reference),
        )
    )


def _direct_shunt_path(
    connector: UsbEndpoint,
    phy: UsbEndpoint,
    observed: NetlistContract,
    interface: UsbDataInterfaceRequirement,
) -> UsbPeerDataLink | None:
    _pin_nets, net_members = pin_net_index(observed)
    reference_nets = {connector.reference_net.casefold(), phy.reference_net.casefold()}
    branch_groups: list[tuple[UsbPeerDataShuntBranch, ...]] = []
    for line, connector_pins, phy_pins, net in (
        ("D+", connector.positive_pins, phy.positive_pins, connector.positive_net),
        ("D-", connector.negative_pins, phy.negative_pins, connector.negative_net),
    ):
        expected = {
            *(pin.casefold() for pin in connector_pins),
            *(pin.casefold() for pin in phy_pins),
            *_mapped_data_pins(interface, line),
        }
        members = net_members.get(net.casefold(), set())
        if not expected <= members:
            return None
        branches = d_designated_shunt_branches(
            observed,
            net,
            members - expected,
            reference_nets,
        )
        if branches is None:
            return None
        branch_groups.append(branches)
    return UsbPeerDataLink(
        connector_positive_pin=connector.positive_pins[0],
        phy_positive_pin=phy.positive_pins[0],
        connector_positive_net=connector.positive_net,
        phy_positive_net=phy.positive_net,
        connector_negative_pin=connector.negative_pins[0],
        phy_negative_pin=phy.negative_pins[0],
        connector_negative_net=connector.negative_net,
        phy_negative_net=phy.negative_net,
        connector_positive_pins=connector.positive_pins,
        phy_positive_pins=phy.positive_pins,
        connector_negative_pins=connector.negative_pins,
        phy_negative_pins=phy.negative_pins,
        positive_shunt_branches=branch_groups[0],
        negative_shunt_branches=branch_groups[1],
        protection_shunts=_matched_protection_shunts(interface),
        port_group=connector.port_group or phy.port_group or interface.data_port_group,
    )


def mapped_protection_shunt_usb_data_link(
    connector: UsbEndpoint,
    phy: UsbEndpoint,
    observed: NetlistContract,
    path_map: UsbDataPathMap | None,
) -> UsbPeerDataLink | None:
    """Return a path only when the exact mapped shunt contract matches source."""
    if path_map is None:
        return None
    if (
        connector.port_group is not None
        and phy.port_group is not None
        and connector.port_group != phy.port_group
    ):
        return None
    matches = [
        interface
        for interface in path_map.interfaces
        if interface.protection_shunts
        and _interface_matches(interface, connector, phy)
        and not any(
            item.interface_id.casefold() == interface.id.casefold()
            for item in usb_data_path_mismatches(path_map, observed)
        )
    ]
    if len(matches) != 1:
        return None
    return _direct_shunt_path(connector, phy, observed, matches[0])
