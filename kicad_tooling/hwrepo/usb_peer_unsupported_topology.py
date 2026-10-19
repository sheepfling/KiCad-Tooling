"""Find bounded USB multi-pin path candidates for coverage-only reporting."""

from __future__ import annotations

from collections.abc import Mapping

from .models import NetlistContract
from .usb_peer_reference_types import UsbEndpoint, UsbPeerUnsupportedMultiPinPath


def unsupported_usb_multi_pin_path_candidates(
    connector: UsbEndpoint,
    phy: UsbEndpoint,
    observed: NetlistContract,
    net_members: Mapping[str, set[str]],
    mapped_component_references: set[str],
) -> tuple[UsbPeerUnsupportedMultiPinPath, ...]:
    """Report shared multi-pin candidates without asserting that they pass data."""
    if (
        connector.signal_family != "USB 2.0 data"
        or phy.signal_family != "USB 2.0 data"
        or (
            connector.port_group is not None
            and phy.port_group is not None
            and connector.port_group != phy.port_group
        )
    ):
        return ()

    endpoint_nets = (
        connector.positive_net,
        phy.positive_net,
        connector.negative_net,
        phy.negative_net,
    )
    if len({net.casefold() for net in endpoint_nets}) != 4:
        return ()

    pin_owner: dict[str, tuple[str, str]] = {}
    component_pin_counts: dict[str, int] = {}
    for reference, raw_numbers in observed.component_pin_numbers.items():
        unique_numbers = {number.casefold() for number in raw_numbers}
        component_pin_counts[reference.casefold()] = len(unique_numbers)
        for number in raw_numbers:
            pin = f"{reference}.{number}"
            pin_owner[pin.casefold()] = (reference, pin)

    pins_by_component_net: dict[str, dict[str, list[str]]] = {}
    pin_net_counts: dict[str, int] = {}
    for net, members in net_members.items():
        for member in members:
            if owner := pin_owner.get(member.casefold()):
                reference, pin = owner
                reference_key = reference.casefold()
                pins_by_component_net.setdefault(reference_key, {}).setdefault(
                    net.casefold(), []
                ).append(pin)
                pin_net_counts[pin.casefold()] = pin_net_counts.get(pin.casefold(), 0) + 1

    endpoint_references = {connector.reference.casefold(), phy.reference.casefold()}
    excluded_references = {item.casefold() for item in mapped_component_references}
    dnp_references = {item.casefold() for item in observed.dnp_components}
    component_by_reference = {item.casefold(): item for item in observed.components}
    symbol_by_reference = {
        key.casefold(): value for key, value in observed.component_symbols.items()
    }
    candidates: list[UsbPeerUnsupportedMultiPinPath] = []
    for reference_key, by_net in pins_by_component_net.items():
        if (
            reference_key in endpoint_references
            or reference_key in excluded_references
            or reference_key in dnp_references
            or component_pin_counts.get(reference_key, 0) <= 2
        ):
            continue
        reference = component_by_reference.get(reference_key)
        if reference is None:
            continue
        component = observed.components.get(reference)
        symbol = symbol_by_reference.get(reference_key)
        if component is None or not symbol or not component.footprint:
            continue

        assigned_pins = (
            tuple(by_net.get(connector.positive_net.casefold(), ())),
            tuple(by_net.get(phy.positive_net.casefold(), ())),
            tuple(by_net.get(connector.negative_net.casefold(), ())),
            tuple(by_net.get(phy.negative_net.casefold(), ())),
        )
        if any(not group for group in assigned_pins):
            continue
        if any(pin_net_counts.get(pin.casefold()) != 1 for group in assigned_pins for pin in group):
            continue
        flattened_pins = tuple(pin.casefold() for group in assigned_pins for pin in group)
        if len(set(flattened_pins)) != len(flattened_pins):
            continue
        candidates.append(
            UsbPeerUnsupportedMultiPinPath(
                connector_reference=connector.reference,
                phy_reference=phy.reference,
                component_reference=reference,
                component_symbol=symbol,
                component_footprint=component.footprint,
                component_pin_count=component_pin_counts[reference_key],
                port_group=connector.port_group or phy.port_group,
                positive_connector_net=connector.positive_net,
                positive_phy_net=phy.positive_net,
                positive_connector_component_pins=assigned_pins[0],
                positive_phy_component_pins=assigned_pins[1],
                negative_connector_net=connector.negative_net,
                negative_phy_net=phy.negative_net,
                negative_connector_component_pins=assigned_pins[2],
                negative_phy_component_pins=assigned_pins[3],
            )
        )
    return tuple(
        sorted(
            candidates,
            key=lambda item: (
                item.connector_reference.casefold(),
                item.connector_reference,
                item.phy_reference.casefold(),
                item.phy_reference,
                item.port_group or "",
                item.component_reference.casefold(),
                item.component_reference,
            ),
        )
    )
