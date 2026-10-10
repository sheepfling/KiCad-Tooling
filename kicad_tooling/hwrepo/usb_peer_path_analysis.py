"""Trace direct, resistor-linked, and bounded shunted USB data paths."""

from __future__ import annotations

import re

from .models import NetlistContract
from .usb_peer_endpoint_analysis import casefold_mapping, pin_net_index
from .usb_peer_reference_types import (
    UsbEndpoint,
    UsbPeerDataLink,
    UsbPeerDataSeriesResistor,
    UsbPeerDataShuntBranch,
)

_DIODE_REFERENCE = re.compile(r"^D[A-Z]*[0-9]+$", re.IGNORECASE)


_RESISTOR_SYMBOL = re.compile(r"^Device:R(?:_[A-Z0-9_]+)?$", re.IGNORECASE)


def _d_designated_shunt_branches(
    observed: NetlistContract,
    data_net: str,
    extra_pins: set[str],
    reference_nets: set[str],
) -> tuple[UsbPeerDataShuntBranch, ...] | None:
    """Accept complete two-pin passive D-designated branches to endpoint references."""
    if not extra_pins:
        return ()
    components = casefold_mapping(observed.components)
    symbols = casefold_mapping(observed.component_symbols)
    inventories = casefold_mapping(observed.component_pin_numbers)
    electrical_types = casefold_mapping(observed.pin_electrical_types)
    component_references = {reference.casefold(): reference for reference in observed.components}
    pin_nets, _net_members = pin_net_index(observed)
    dnp = {reference.casefold() for reference in observed.dnp_components}
    extras_by_reference: dict[str, set[str]] = {}
    display_references: dict[str, str] = {}
    for pin in extra_pins:
        reference, separator, number = pin.rpartition(".")
        if not separator:
            return None
        key = reference.casefold()
        extras_by_reference.setdefault(key, set()).add(number.casefold())
        display_references[key] = component_references.get(key, reference)

    branches: list[UsbPeerDataShuntBranch] = []
    for reference_key, extra_numbers in extras_by_reference.items():
        reference = display_references[reference_key]
        if (
            _DIODE_REFERENCE.fullmatch(reference) is None
            or reference_key in dnp
            or reference_key not in components
            or reference_key not in symbols
        ):
            return None
        numbers = inventories.get(reference_key)
        if numbers is None or len(numbers) != 2 or len({item.casefold() for item in numbers}) != 2:
            return None
        normalized_numbers = {number.casefold() for number in numbers}
        display_numbers = {number.casefold(): number for number in numbers}
        if len(extra_numbers) != 1 or not extra_numbers <= normalized_numbers:
            return None
        assigned_nets: dict[str, tuple[str, str]] = {}
        for number in numbers:
            pin = f"{reference}.{number}"
            pin_key = pin.casefold()
            if electrical_types.get(pin_key, "").casefold() != "passive":
                return None
            nets = pin_nets.get(pin_key, set())
            if len(nets) != 1:
                return None
            actual_net = next(iter(nets))
            assigned_nets[number.casefold()] = (actual_net, actual_net.casefold())
        signal_numbers = {
            number
            for number, (_actual_net, net_key) in assigned_nets.items()
            if net_key == data_net.casefold()
        }
        if signal_numbers != extra_numbers:
            return None
        other_numbers = normalized_numbers - signal_numbers
        if len(other_numbers) != 1:
            return None
        other_number = next(iter(other_numbers))
        other_actual_net, other_net_key = assigned_nets[other_number]
        if other_net_key not in reference_nets:
            return None
        signal_number = next(iter(signal_numbers))
        signal_actual_net, _signal_net_key = assigned_nets[signal_number]
        branches.append(
            UsbPeerDataShuntBranch(
                data_pin=f"{reference}.{display_numbers[signal_number]}",
                reference_pin=f"{reference}.{display_numbers[other_number]}",
                symbol=symbols[reference_key],
                data_net=signal_actual_net,
                reference_net=other_actual_net,
            )
        )
    return tuple(sorted(branches, key=lambda item: (item.data_pin.casefold(), item.data_pin)))


def _series_resistor_between_nets(
    observed: NetlistContract,
    connector_net: str,
    phy_net: str,
) -> UsbPeerDataSeriesResistor | None:
    """Find one complete, fitted Device:R connecting the endpoint data nets."""
    if connector_net.casefold() == phy_net.casefold():
        return None
    inventories = casefold_mapping(observed.component_pin_numbers)
    components = casefold_mapping(observed.components)
    symbols = casefold_mapping(observed.component_symbols)
    electrical_types = casefold_mapping(observed.pin_electrical_types)
    display_references = {reference.casefold(): reference for reference in observed.components}
    pin_nets, _net_members = pin_net_index(observed)
    dnp = {reference.casefold() for reference in observed.dnp_components}
    wanted_nets = {connector_net.casefold(), phy_net.casefold()}
    candidates: list[UsbPeerDataSeriesResistor] = []
    for reference_key, symbol in symbols.items():
        if (
            _RESISTOR_SYMBOL.fullmatch(symbol) is None
            or reference_key in dnp
            or reference_key not in components
        ):
            continue
        numbers = inventories.get(reference_key)
        if numbers is None or len(numbers) != 2 or len({item.casefold() for item in numbers}) != 2:
            continue
        reference = display_references.get(reference_key)
        if reference is None:
            continue
        assignments: list[tuple[str, str]] = []
        for number in numbers:
            pin = f"{reference}.{number}"
            pin_key = pin.casefold()
            if electrical_types.get(pin_key, "").casefold() != "passive":
                break
            nets = pin_nets.get(pin_key, set())
            if len(nets) != 1:
                break
            assignments.append((pin, next(iter(nets))))
        if len(assignments) != 2 or {net.casefold() for _pin, net in assignments} != wanted_nets:
            continue
        component = components[reference_key]
        connector_pin, actual_connector_net = next(
            (pin, net) for pin, net in assignments if net.casefold() == connector_net.casefold()
        )
        phy_pin, actual_phy_net = next(
            (pin, net) for pin, net in assignments if net.casefold() == phy_net.casefold()
        )
        candidates.append(
            UsbPeerDataSeriesResistor(
                reference=reference,
                symbol=symbol,
                footprint=component.footprint,
                value=component.value,
                connector_pin=connector_pin,
                phy_pin=phy_pin,
                connector_net=actual_connector_net,
                phy_net=actual_phy_net,
            )
        )
    return candidates[0] if len(candidates) == 1 else None


def _data_line_path(
    connector: UsbEndpoint,
    phy: UsbEndpoint,
    *,
    positive: bool,
    net_members: dict[str, set[str]],
    observed: NetlistContract,
    reference_nets: set[str],
) -> tuple[UsbPeerDataSeriesResistor | None, tuple[UsbPeerDataShuntBranch, ...]] | None:
    connector_pins = connector.positive_pins if positive else connector.negative_pins
    phy_pins = phy.positive_pins if positive else phy.negative_pins
    connector_net = connector.positive_net if positive else connector.negative_net
    phy_net = phy.positive_net if positive else phy.negative_net
    if connector_net.casefold() == phy_net.casefold():
        members = net_members.get(connector_net.casefold(), set())
        endpoint_pins = {
            *(pin.casefold() for pin in connector_pins),
            *(pin.casefold() for pin in phy_pins),
        }
        if not endpoint_pins <= members:
            return None
        shunts = _d_designated_shunt_branches(
            observed,
            connector_net,
            members - endpoint_pins,
            reference_nets,
        )
        return None if shunts is None else (None, shunts)

    series_resistor = _series_resistor_between_nets(observed, connector_net, phy_net)
    if series_resistor is None:
        return None
    connector_members = net_members.get(connector_net.casefold(), set())
    phy_members = net_members.get(phy_net.casefold(), set())
    connector_expected = {
        *(pin.casefold() for pin in connector_pins),
        series_resistor.connector_pin.casefold(),
    }
    phy_expected = {
        *(pin.casefold() for pin in phy_pins),
        series_resistor.phy_pin.casefold(),
    }
    if not connector_expected <= connector_members or not phy_expected <= phy_members:
        return None
    connector_shunts = _d_designated_shunt_branches(
        observed,
        connector_net,
        connector_members - connector_expected,
        reference_nets,
    )
    phy_shunts = _d_designated_shunt_branches(
        observed,
        phy_net,
        phy_members - phy_expected,
        reference_nets,
    )
    if connector_shunts is None or phy_shunts is None:
        return None
    shunts = tuple(
        sorted(
            (*connector_shunts, *phy_shunts),
            key=lambda item: (item.data_pin.casefold(), item.data_pin),
        )
    )
    return series_resistor, shunts


def usb_data_link(
    connector: UsbEndpoint,
    phy: UsbEndpoint,
    net_members: dict[str, set[str]],
    observed: NetlistContract,
) -> UsbPeerDataLink | None:
    if (
        connector.port_group is not None
        and phy.port_group is not None
        and connector.port_group != phy.port_group
    ):
        return None
    reference_nets = {connector.reference_net.casefold(), phy.reference_net.casefold()}
    positive_path = _data_line_path(
        connector,
        phy,
        positive=True,
        net_members=net_members,
        observed=observed,
        reference_nets=reference_nets,
    )
    negative_path = _data_line_path(
        connector,
        phy,
        positive=False,
        net_members=net_members,
        observed=observed,
        reference_nets=reference_nets,
    )
    if positive_path is None or negative_path is None:
        return None
    positive_series, positive_shunts = positive_path
    negative_series, negative_shunts = negative_path
    connector_positive_pins = connector.positive_pins
    phy_positive_pins = phy.positive_pins
    connector_negative_pins = connector.negative_pins
    phy_negative_pins = phy.negative_pins
    return UsbPeerDataLink(
        connector_positive_pin=connector_positive_pins[0],
        phy_positive_pin=phy_positive_pins[0],
        connector_positive_net=connector.positive_net,
        phy_positive_net=phy.positive_net,
        connector_negative_pin=connector_negative_pins[0],
        phy_negative_pin=phy_negative_pins[0],
        connector_negative_net=connector.negative_net,
        phy_negative_net=phy.negative_net,
        connector_positive_pins=connector_positive_pins,
        phy_positive_pins=phy_positive_pins,
        connector_negative_pins=connector_negative_pins,
        phy_negative_pins=phy_negative_pins,
        positive_shunt_branches=positive_shunts,
        negative_shunt_branches=negative_shunts,
        positive_series_resistor=positive_series,
        negative_series_resistor=negative_series,
        port_group=connector.port_group or phy.port_group,
    )
