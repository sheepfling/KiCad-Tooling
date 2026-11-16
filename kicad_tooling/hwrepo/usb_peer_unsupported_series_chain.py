"""Find complete, unbranched USB data paths with an unsupported resistor chain."""

from __future__ import annotations

import re
from collections import deque
from collections.abc import Iterable, Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass

from .casefold_mapping_lookup import casefolded_unique_index
from .connector_identity import connector_candidate_references
from .netlist_contract_models import NetlistContract
from .usb_data_path_models import UsbDataPathMap
from .usb_peer_endpoint_analysis import IC_REFERENCE, pin_net_index, usb_endpoints
from .usb_peer_map_identity import usb_data_interface_matches_endpoint_group
from .usb_peer_reference_types import UsbEndpoint
from .usb_peer_unsupported_series_chain_types import (
    UsbPeerUnsupportedSeriesChain,
    UsbSeriesLinePath,
    UsbSeriesResistorStage,
)

_RESISTOR_SYMBOL = re.compile(r"^Device:R(?:_[A-Z0-9_]+)?$", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class _ResistorEdge:
    reference: str
    symbol: str
    footprint: str
    value: str
    first_pin: str
    first_net: str
    second_pin: str
    second_net: str


def _fitted_resistor_edges(observed: NetlistContract) -> tuple[_ResistorEdge, ...]:
    """Keep only complete, fitted two-pin passive Device:R netlist assignments."""
    components = casefolded_unique_index(observed.components)
    symbols = casefolded_unique_index(observed.component_symbols)
    inventories = casefolded_unique_index(observed.component_pin_numbers)
    electrical_types = casefolded_unique_index(observed.pin_electrical_types)
    assignments = pin_net_index(observed)
    dnp = {reference.casefold() for reference in observed.dnp_components}
    result: list[_ResistorEdge] = []
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
        reference = next(
            (item for item in observed.components if item.casefold() == reference_key), None
        )
        if reference is None:
            continue
        assigned: list[tuple[str, str]] = []
        for number in numbers:
            pin = f"{reference}.{number}"
            pin_key = pin.casefold()
            nets = assignments.nets_by_pin_key.get(pin_key, frozenset())
            if electrical_types.get(pin_key, "").casefold() != "passive" or len(nets) != 1:
                break
            assigned.append((pin, next(iter(nets))))
        if len(assigned) != 2 or assigned[0][1].casefold() == assigned[1][1].casefold():
            continue
        component = components[reference_key]
        result.append(
            _ResistorEdge(
                reference=reference,
                symbol=symbol,
                footprint=component.footprint,
                value=component.value,
                first_pin=assigned[0][0],
                first_net=assigned[0][1],
                second_pin=assigned[1][0],
                second_net=assigned[1][1],
            )
        )
    return tuple(sorted(result, key=lambda item: (item.reference.casefold(), item.reference)))


def _line_path(
    connector_pins: Iterable[str],
    connector_net: str,
    phy_pins: Iterable[str],
    phy_net: str,
    net_members: Mapping[str, AbstractSet[str]],
    edges: tuple[_ResistorEdge, ...],
) -> UsbSeriesLinePath | None:
    """Return a closed direct/resistor path only when all pins on it are accounted for."""
    connector_key = connector_net.casefold()
    phy_key = phy_net.casefold()
    endpoint_connector_pins = {pin.casefold() for pin in connector_pins}
    endpoint_phy_pins = {pin.casefold() for pin in phy_pins}
    if connector_key == phy_key:
        expected = endpoint_connector_pins | endpoint_phy_pins
        if set(net_members.get(connector_key, ())) != expected:
            return None
        return UsbSeriesLinePath(connector_net, phy_net, ())

    adjacency: dict[str, list[_ResistorEdge]] = {}
    for edge in edges:
        first_key = edge.first_net.casefold()
        second_key = edge.second_net.casefold()
        adjacency.setdefault(first_key, []).append(edge)
        adjacency.setdefault(second_key, []).append(edge)
    if connector_key not in adjacency:
        return None

    reachable = {connector_key}
    pending = deque((connector_key,))
    while pending:
        current = pending.popleft()
        for edge in adjacency.get(current, ()):
            next_net = (
                edge.second_net.casefold()
                if edge.first_net.casefold() == current
                else edge.first_net.casefold()
            )
            if next_net not in reachable:
                reachable.add(next_net)
                pending.append(next_net)
    if phy_key not in reachable:
        return None
    reachable_edges = tuple(
        edge
        for edge in edges
        if edge.first_net.casefold() in reachable and edge.second_net.casefold() in reachable
    )
    if len(reachable_edges) != len(reachable) - 1:
        return None
    if any(
        len(adjacency.get(net, ())) != (1 if net in {connector_key, phy_key} else 2)
        for net in reachable
    ):
        return None

    ordered_edges: list[tuple[_ResistorEdge, str, str, str, str]] = []
    current = connector_key
    previous_reference: str | None = None
    while current != phy_key:
        candidates = tuple(
            edge for edge in adjacency[current] if edge.reference.casefold() != previous_reference
        )
        if len(candidates) != 1:
            return None
        edge = candidates[0]
        if edge.first_net.casefold() == current:
            next_key, current_net, next_net = (
                edge.second_net.casefold(),
                edge.first_net,
                edge.second_net,
            )
            current_pin, next_pin = edge.first_pin, edge.second_pin
        else:
            next_key, current_net, next_net = (
                edge.first_net.casefold(),
                edge.second_net,
                edge.first_net,
            )
            current_pin, next_pin = edge.second_pin, edge.first_pin
        ordered_edges.append((edge, current_pin, next_pin, current_net, next_net))
        previous_reference = edge.reference.casefold()
        current = next_key
        if len(ordered_edges) > len(reachable_edges):
            return None
    if len(ordered_edges) != len(reachable_edges):
        return None

    expected_by_net: dict[str, set[str]] = {net: set() for net in reachable}
    expected_by_net[connector_key].update(endpoint_connector_pins)
    expected_by_net[phy_key].update(endpoint_phy_pins)
    for edge in reachable_edges:
        expected_by_net[edge.first_net.casefold()].add(edge.first_pin.casefold())
        expected_by_net[edge.second_net.casefold()].add(edge.second_pin.casefold())
    if any(set(net_members.get(net, ())) != expected for net, expected in expected_by_net.items()):
        return None

    stages = tuple(
        UsbSeriesResistorStage(
            reference=edge.reference,
            symbol=edge.symbol,
            footprint=edge.footprint,
            value=edge.value,
            connector_pin=connector_pin,
            phy_pin=phy_pin,
            connector_net=current_net,
            phy_net=next_net,
        )
        for edge, connector_pin, phy_pin, current_net, next_net in ordered_edges
    )
    return UsbSeriesLinePath(connector_net, phy_net, stages)


def _mapped_endpoint_group(
    path_map: UsbDataPathMap | None, connector: UsbEndpoint, phy: UsbEndpoint
) -> bool:
    return bool(
        path_map
        and any(
            usb_data_interface_matches_endpoint_group(
                item,
                connector_reference=connector.reference,
                phy_reference=phy.reference,
                port_groups=frozenset((connector.port_group, phy.port_group)),
            )
            for item in path_map.interfaces
        )
    )


def unsupported_usb_series_chain_candidates(
    observed: NetlistContract,
    path_map: UsbDataPathMap | None,
    reviewed_connector_references: tuple[str, ...] = (),
) -> tuple[UsbPeerUnsupportedSeriesChain, ...]:
    """Find unmapped USB 2.0 pairs with a closed resistor-only multi-stage path."""
    assignments = pin_net_index(observed)
    connector_references = connector_candidate_references(observed, reviewed_connector_references)
    connector_keys = {item.casefold() for item in connector_references}
    phy_references = tuple(
        reference
        for reference in sorted(observed.components, key=lambda item: (item.casefold(), item))
        if reference.casefold() not in connector_keys and IC_REFERENCE.fullmatch(reference)
    )
    connectors = usb_endpoints(connector_references, observed, assignments, connector=True)
    phys = usb_endpoints(phy_references, observed, assignments, connector=False)
    edges = _fitted_resistor_edges(observed)
    net_members = assignments.pin_keys_by_net_key
    found: list[UsbPeerUnsupportedSeriesChain] = []
    for connector in connectors:
        if connector.signal_family != "USB 2.0 data":
            continue
        for phy in phys:
            if (
                phy.signal_family != "USB 2.0 data"
                or (
                    connector.port_group is not None
                    and phy.port_group is not None
                    and connector.port_group != phy.port_group
                )
                or _mapped_endpoint_group(path_map, connector, phy)
            ):
                continue
            positive = _line_path(
                connector.positive_pins,
                connector.positive_net,
                phy.positive_pins,
                phy.positive_net,
                net_members,
                edges,
            )
            negative = _line_path(
                connector.negative_pins,
                connector.negative_net,
                phy.negative_pins,
                phy.negative_net,
                net_members,
                edges,
            )
            if (
                positive is None
                or negative is None
                or max(len(positive.stages), len(negative.stages)) < 2
            ):
                continue
            found.append(
                UsbPeerUnsupportedSeriesChain(
                    connector_reference=connector.reference,
                    phy_reference=phy.reference,
                    port_group=connector.port_group or phy.port_group,
                    positive=positive,
                    negative=negative,
                )
            )
    return tuple(
        sorted(
            found,
            key=lambda item: (
                item.connector_reference.casefold(),
                item.connector_reference,
                item.phy_reference.casefold(),
                item.phy_reference,
                item.port_group or "",
            ),
        )
    )
