"""Recognize USB paths with exact project-mapped multi-pin protection shunts."""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet

from .netlist_contract_models import NetlistContract
from .usb_data_path_models import UsbDataInterfaceRequirement, UsbDataPathMap
from .usb_data_paths import usb_data_path_mismatches
from .usb_peer_endpoint_analysis import pin_net_index
from .usb_peer_mapped_protection_evidence import mapped_protection_shunt_evidence
from .usb_peer_path_analysis import d_designated_shunt_branches, series_resistor_between_nets
from .usb_peer_reference_types import (
    UsbEndpoint,
    UsbPeerDataLink,
    UsbPeerDataSeriesResistor,
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
    if (
        interface.positive.topology != interface.negative.topology
        or interface.positive.topology
        not in {
            "direct",
            "series_resistor",
        }
    ):
        return False
    return (
        interface.positive.connector_net.casefold() == connector.positive_net.casefold()
        and interface.positive.phy_net.casefold() == phy.positive_net.casefold()
        and {pin.casefold() for pin in interface.positive.connector_pins}
        == {pin.casefold() for pin in connector.positive_pins}
        and {pin.casefold() for pin in interface.positive.phy_pins}
        == {pin.casefold() for pin in phy.positive_pins}
        and interface.negative.connector_net.casefold() == connector.negative_net.casefold()
        and interface.negative.phy_net.casefold() == phy.negative_net.casefold()
        and {pin.casefold() for pin in interface.negative.connector_pins}
        == {pin.casefold() for pin in connector.negative_pins}
        and {pin.casefold() for pin in interface.negative.phy_pins}
        == {pin.casefold() for pin in phy.negative_pins}
    )


def _series_line_shunt_branches(
    interface: UsbDataInterfaceRequirement,
    line: str,
    connector_pins: tuple[str, ...],
    phy_pins: tuple[str, ...],
    connector_net: str,
    phy_net: str,
    resistor: UsbPeerDataSeriesResistor,
    net_members: Mapping[str, AbstractSet[str]],
    observed: NetlistContract,
    reference_nets: AbstractSet[str],
) -> tuple[UsbPeerDataShuntBranch, ...] | None:
    def expected_members(net: str, endpoint_pins: tuple[str, ...], resistor_pin: str) -> set[str]:
        return {
            *(pin.casefold() for pin in endpoint_pins),
            resistor_pin.casefold(),
            *(
                item.pin.casefold()
                for shunt in interface.protection_shunts
                for item in shunt.data_pins
                if item.line == line and item.net.casefold() == net.casefold()
            ),
        }

    connector_expected = expected_members(connector_net, connector_pins, resistor.connector_pin)
    phy_expected = expected_members(phy_net, phy_pins, resistor.phy_pin)
    connector_members = net_members.get(connector_net.casefold(), frozenset())
    phy_members = net_members.get(phy_net.casefold(), frozenset())
    if not connector_expected <= connector_members or not phy_expected <= phy_members:
        return None
    connector_branches = d_designated_shunt_branches(
        observed,
        connector_net,
        connector_members - connector_expected,
        reference_nets,
    )
    phy_branches = d_designated_shunt_branches(
        observed,
        phy_net,
        phy_members - phy_expected,
        reference_nets,
    )
    if connector_branches is None or phy_branches is None:
        return None
    return tuple(
        sorted(
            (*connector_branches, *phy_branches),
            key=lambda item: (item.data_pin.casefold(), item.data_pin),
        )
    )


def _mapped_series_path_with_shunts(
    connector: UsbEndpoint,
    phy: UsbEndpoint,
    observed: NetlistContract,
    interface: UsbDataInterfaceRequirement,
) -> UsbPeerDataLink | None:
    positive_resistor = series_resistor_between_nets(
        observed, connector.positive_net, phy.positive_net
    )
    negative_resistor = series_resistor_between_nets(
        observed, connector.negative_net, phy.negative_net
    )
    if positive_resistor is None or negative_resistor is None:
        return None
    for requirement, actual in (
        (interface.positive.series_resistor, positive_resistor),
        (interface.negative.series_resistor, negative_resistor),
    ):
        if (
            requirement is None
            or requirement.reference.casefold() != actual.reference.casefold()
            or requirement.expected_symbol != actual.symbol
            or requirement.expected_footprint != actual.footprint
        ):
            return None
    assignments = pin_net_index(observed)
    reference_nets = {connector.reference_net.casefold(), phy.reference_net.casefold()}
    positive_branches = _series_line_shunt_branches(
        interface,
        "D+",
        connector.positive_pins,
        phy.positive_pins,
        connector.positive_net,
        phy.positive_net,
        positive_resistor,
        assignments.pin_keys_by_net_key,
        observed,
        reference_nets,
    )
    negative_branches = _series_line_shunt_branches(
        interface,
        "D-",
        connector.negative_pins,
        phy.negative_pins,
        connector.negative_net,
        phy.negative_net,
        negative_resistor,
        assignments.pin_keys_by_net_key,
        observed,
        reference_nets,
    )
    if positive_branches is None or negative_branches is None:
        return None
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
        positive_series_resistor=positive_resistor,
        negative_series_resistor=negative_resistor,
        protection_shunts=mapped_protection_shunt_evidence(interface),
        port_group=connector.port_group or phy.port_group or interface.data_port_group,
    )


def _mapped_data_pins(interface: UsbDataInterfaceRequirement, line: str) -> set[str]:
    return {
        item.pin.casefold()
        for shunt in interface.protection_shunts
        for item in shunt.data_pins
        if item.line == line
    }


def _direct_shunt_path(
    connector: UsbEndpoint,
    phy: UsbEndpoint,
    observed: NetlistContract,
    interface: UsbDataInterfaceRequirement,
) -> UsbPeerDataLink | None:
    assignments = pin_net_index(observed)
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
        members = assignments.pin_keys_by_net_key.get(net.casefold(), frozenset())
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
        protection_shunts=mapped_protection_shunt_evidence(interface),
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
    interface = matches[0]
    if interface.positive.topology == "series_resistor":
        return _mapped_series_path_with_shunts(connector, phy, observed, interface)
    return _direct_shunt_path(connector, phy, observed, interface)
