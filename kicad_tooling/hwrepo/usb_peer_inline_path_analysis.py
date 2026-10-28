"""Recognize USB inline paths only through a current exact project map."""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet

from .models import NetlistContract
from .usb_data_path_models import (
    UsbDataInterfaceRequirement,
    UsbDataPathLineRequirement,
    UsbDataPathMap,
)
from .usb_data_paths import usb_data_path_mismatches
from .usb_peer_path_analysis import d_designated_shunt_branches
from .usb_peer_reference_types import (
    UsbEndpoint,
    UsbPeerDataInlineComponent,
    UsbPeerDataLink,
    UsbPeerDataShuntBranch,
)


def _line_matches_endpoint(
    requirement: UsbDataPathLineRequirement,
    *,
    connector_pins: tuple[str, ...],
    phy_pins: tuple[str, ...],
    connector_net: str,
    phy_net: str,
) -> bool:
    return (
        requirement.topology == "inline_component"
        and {pin.casefold() for pin in requirement.connector_pins}
        == {pin.casefold() for pin in connector_pins}
        and {pin.casefold() for pin in requirement.phy_pins} == {pin.casefold() for pin in phy_pins}
        and requirement.connector_net.casefold() == connector_net.casefold()
        and requirement.phy_net.casefold() == phy_net.casefold()
    )


def _mapped_net_shunts(
    net_members: Mapping[str, AbstractSet[str]],
    net: str,
    endpoint_pins: tuple[str, ...],
    inline_pin: str,
    observed: NetlistContract,
    reference_nets: AbstractSet[str],
) -> tuple[UsbPeerDataShuntBranch, ...] | None:
    expected = {pin.casefold() for pin in (*endpoint_pins, inline_pin)}
    extras = net_members.get(net.casefold(), set()) - expected
    return d_designated_shunt_branches(observed, net, extras, reference_nets)


def _pin_assignments(interface: UsbDataInterfaceRequirement) -> tuple[str, ...]:
    inline = interface.inline_component
    if inline is None:
        return ()
    return tuple(
        sorted(
            (
                f"{item.pin}={item.net}"
                if item.disposition == "net"
                else f"{item.pin}=<unconnected>"
                for item in inline.pins
            ),
            key=lambda item: (item.casefold(), item),
        )
    )


def _mapped_interface_matches(
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
        or (
            interface.data_port_group is not None
            and interface.data_port_group not in {connector.port_group, phy.port_group}
        )
    ):
        return False
    return _line_matches_endpoint(
        interface.positive,
        connector_pins=connector.positive_pins,
        phy_pins=phy.positive_pins,
        connector_net=connector.positive_net,
        phy_net=phy.positive_net,
    ) and _line_matches_endpoint(
        interface.negative,
        connector_pins=connector.negative_pins,
        phy_pins=phy.negative_pins,
        connector_net=connector.negative_net,
        phy_net=phy.negative_net,
    )


def _current_inline_map(
    path_map: UsbDataPathMap,
    interface: UsbDataInterfaceRequirement,
    observed: NetlistContract,
) -> bool:
    if interface.inline_component is None:
        return False
    return not any(
        item.interface_id.casefold() == interface.id.casefold()
        for item in usb_data_path_mismatches(path_map, observed)
    )


def _inline_data_link(
    connector: UsbEndpoint,
    phy: UsbEndpoint,
    net_members: Mapping[str, AbstractSet[str]],
    observed: NetlistContract,
    interface: UsbDataInterfaceRequirement,
) -> UsbPeerDataLink | None:
    inline = interface.inline_component
    if inline is None:
        return None
    assignments = _pin_assignments(interface)
    positive_inline = UsbPeerDataInlineComponent(
        reference=inline.reference,
        symbol=inline.expected_symbol,
        footprint=inline.expected_footprint,
        connector_pin=inline.positive_connector_pin,
        phy_pin=inline.positive_phy_pin,
        connector_net=interface.positive.connector_net,
        phy_net=interface.positive.phy_net,
        pin_assignments=assignments,
    )
    negative_inline = UsbPeerDataInlineComponent(
        reference=inline.reference,
        symbol=inline.expected_symbol,
        footprint=inline.expected_footprint,
        connector_pin=inline.negative_connector_pin,
        phy_pin=inline.negative_phy_pin,
        connector_net=interface.negative.connector_net,
        phy_net=interface.negative.phy_net,
        pin_assignments=assignments,
    )
    reference_nets = {connector.reference_net.casefold(), phy.reference_net.casefold()}
    positive_shunts = (
        _mapped_net_shunts(
            net_members,
            interface.positive.connector_net,
            connector.positive_pins,
            inline.positive_connector_pin,
            observed,
            reference_nets,
        ),
        _mapped_net_shunts(
            net_members,
            interface.positive.phy_net,
            phy.positive_pins,
            inline.positive_phy_pin,
            observed,
            reference_nets,
        ),
    )
    negative_shunts = (
        _mapped_net_shunts(
            net_members,
            interface.negative.connector_net,
            connector.negative_pins,
            inline.negative_connector_pin,
            observed,
            reference_nets,
        ),
        _mapped_net_shunts(
            net_members,
            interface.negative.phy_net,
            phy.negative_pins,
            inline.negative_phy_pin,
            observed,
            reference_nets,
        ),
    )
    if any(item is None for item in (*positive_shunts, *negative_shunts)):
        return None
    positive_branches = tuple(
        sorted(
            (branch for item in positive_shunts for branch in item or ()),
            key=lambda item: (item.data_pin.casefold(), item.data_pin),
        )
    )
    negative_branches = tuple(
        sorted(
            (branch for item in negative_shunts for branch in item or ()),
            key=lambda item: (item.data_pin.casefold(), item.data_pin),
        )
    )
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
        positive_shunt_branches=positive_branches,
        negative_shunt_branches=negative_branches,
        positive_inline_component=positive_inline,
        negative_inline_component=negative_inline,
        port_group=connector.port_group or phy.port_group or interface.data_port_group,
    )


def mapped_inline_usb_data_link(
    connector: UsbEndpoint,
    phy: UsbEndpoint,
    net_members: Mapping[str, AbstractSet[str]],
    observed: NetlistContract,
    path_map: UsbDataPathMap | None,
) -> UsbPeerDataLink | None:
    """Return a peer path only when one exact inline map matches current source evidence."""
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
        if _mapped_interface_matches(interface, connector, phy)
        and _current_inline_map(path_map, interface, observed)
    ]
    if len(matches) != 1:
        return None
    return _inline_data_link(connector, phy, net_members, observed, matches[0])
