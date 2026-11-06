"""Find generic connector contacts assigned to recognized USB PHY data pairs."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .casefold_mapping_lookup import casefolded_unique_index
from .connector_identity import connector_candidate_references, pin_function_is_generic
from .netlist_contract_models import NetlistContract
from .usb_data_path_models import UsbDataPathMap
from .usb_peer_endpoint_analysis import pin_net_index, usb_endpoint, usb_superspeed_endpoints
from .usb_peer_generic_connector_models import (
    UsbGenericConnectorDataPair,
    UsbGenericConnectorSuperspeedPair,
)
from .usb_peer_reference_types import UsbEndpoint, UsbReferencePinAssignment


def generic_usb_connector_data_pair_candidates(
    observed: NetlistContract,
    reviewed_connector_references: tuple[str, ...] = (),
) -> tuple[UsbGenericConnectorDataPair, ...]:
    """Identify complete generic connector pin groups sharing one PHY's exact D+/D- nets.

    This is a coverage prompt predicate. It does not infer connector purpose or
    prove that a USB data path exists.
    """
    index = _GenericConnectorPinIndex(observed)
    dnp = {reference.casefold() for reference in observed.dnp_components}
    connectors = connector_candidate_references(observed, reviewed_connector_references)
    found: list[UsbGenericConnectorDataPair] = []

    phy_endpoints = (
        endpoint
        for reference in observed.component_symbols
        for endpoint in usb_endpoint(
            reference, observed, connector=False, assignments=index.assignments
        )
        if endpoint.signal_family == "USB 2.0 data"
    )
    for endpoint in phy_endpoints:
        if len(endpoint.positive_pins) != 1 or len(endpoint.negative_pins) != 1:
            continue
        for connector_reference in connectors:
            connector_key = connector_reference.casefold()
            if connector_key == endpoint.reference.casefold() or connector_key in dnp:
                continue
            contacts = index.contacts_for_pair(
                connector_reference, endpoint.positive_net, endpoint.negative_net
            )
            if contacts is None:
                continue
            found.append(
                UsbGenericConnectorDataPair(
                    connector_reference=connector_reference,
                    phy_reference=endpoint.reference,
                    port_group=endpoint.port_group,
                    positive_pins=contacts.positive_pins,
                    positive_functions=contacts.positive_functions,
                    positive_net=endpoint.positive_net,
                    negative_pins=contacts.negative_pins,
                    negative_functions=contacts.negative_functions,
                    negative_net=endpoint.negative_net,
                    connector_pin_count=contacts.connector_pin_count,
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
                tuple(pin.casefold() for pin in item.positive_pins),
                tuple(pin.casefold() for pin in item.negative_pins),
            ),
        )
    )


def generic_usb_connector_superspeed_pair_candidates(
    observed: NetlistContract,
    reviewed_connector_references: tuple[str, ...] = (),
) -> tuple[UsbGenericConnectorSuperspeedPair, ...]:
    """Identify generic contacts on the exact P/N nets of a recognized USB SS PHY pair."""
    index = _GenericConnectorPinIndex(observed)
    dnp = {reference.casefold() for reference in observed.dnp_components}
    connectors = connector_candidate_references(observed, reviewed_connector_references)
    phy_endpoints = (
        endpoint
        for reference in observed.component_symbols
        for endpoint in usb_superspeed_endpoints(
            (reference,), observed, index.assignments, connector=False
        )
    )
    found: list[UsbGenericConnectorSuperspeedPair] = []
    for endpoint in phy_endpoints:
        if endpoint.signal_family == "USB 2.0 data":
            continue
        for connector_reference in connectors:
            if connector_reference.casefold() in dnp or (
                connector_reference.casefold() == endpoint.reference.casefold()
            ):
                continue
            contacts = index.contacts_for_pair(
                connector_reference, endpoint.positive_net, endpoint.negative_net
            )
            if contacts is None:
                continue
            found.append(
                UsbGenericConnectorSuperspeedPair(
                    connector_reference=connector_reference,
                    phy_reference=endpoint.reference,
                    signal_family=endpoint.signal_family,
                    phy_positive_pin=endpoint.positive_pins[0],
                    positive_pins=contacts.positive_pins,
                    positive_functions=contacts.positive_functions,
                    positive_net=endpoint.positive_net,
                    negative_pins=contacts.negative_pins,
                    negative_functions=contacts.negative_functions,
                    negative_net=endpoint.negative_net,
                    phy_negative_pin=endpoint.negative_pins[0],
                    connector_pin_count=contacts.connector_pin_count,
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
                item.signal_family,
                tuple(pin.casefold() for pin in item.positive_pins),
                tuple(pin.casefold() for pin in item.negative_pins),
            ),
        )
    )


def mapped_generic_usb_superspeed_connector_endpoints(
    observed: NetlistContract,
    path_map: UsbDataPathMap | None,
) -> tuple[UsbEndpoint, ...]:
    """Use exact authored USB maps to recognize otherwise-generic connector pins.

    The map supplies endpoint roles and reference-pin identities; every net,
    component identity, and pin inventory value in the returned endpoint is
    still read from the current native netlist. Mismatched assignments remain
    visible to the USB path contract checker.
    """
    if path_map is None or not path_map.superspeed_interfaces:
        return ()

    index = _GenericConnectorPinIndex(observed)
    dnp = {reference.casefold() for reference in observed.dnp_components}
    mapped_references = tuple(item.connector_reference for item in path_map.superspeed_interfaces)
    connector_references = {
        item.casefold() for item in connector_candidate_references(observed, mapped_references)
    }
    endpoints: list[UsbEndpoint] = []
    for requirement in path_map.superspeed_interfaces:
        reference = requirement.connector_reference
        reference_key = reference.casefold()
        if reference_key in dnp or reference_key not in connector_references:
            continue
        symbol = index.symbols.get(reference_key)
        component = index.components.get(reference_key)
        numbers = index.inventories.get(reference_key)
        if symbol is None or component is None or not numbers:
            continue
        if len({number.casefold() for number in numbers}) != len(numbers):
            continue
        if any(
            index.functions.get(f"{reference}.{number}".casefold()) is None for number in numbers
        ) or any(
            index.electrical_types.get(f"{reference}.{number}".casefold()) is None
            for number in numbers
        ):
            continue
        positive_function = index.functions.get(requirement.connector_positive_pin.casefold())
        negative_function = index.functions.get(requirement.connector_negative_pin.casefold())
        if not pin_function_is_generic(positive_function) or not pin_function_is_generic(
            negative_function
        ):
            continue

        positive_nets = index.assignments.nets_by_pin_key.get(
            requirement.connector_positive_pin.casefold(), frozenset()
        )
        negative_nets = index.assignments.nets_by_pin_key.get(
            requirement.connector_negative_pin.casefold(), frozenset()
        )
        if len(positive_nets) != 1 or len(negative_nets) != 1:
            continue
        positive_net = next(iter(positive_nets))
        negative_net = next(iter(negative_nets))
        if positive_net.casefold() == negative_net.casefold():
            continue

        reference_pins: list[UsbReferencePinAssignment] = []
        for reference_pin in requirement.connector_reference_pins:
            pin_key = reference_pin.pin.casefold()
            function = index.functions.get(pin_key)
            electrical_type = index.electrical_types.get(pin_key)
            nets = index.assignments.nets_by_pin_key.get(pin_key, frozenset())
            if function is None or electrical_type is None or len(nets) != 1:
                break
            reference_pins.append(
                UsbReferencePinAssignment(
                    pin=reference_pin.pin,
                    function=function,
                    electrical_type=electrical_type,
                    net=next(iter(nets)),
                )
            )
        if len(reference_pins) != len(requirement.connector_reference_pins):
            continue
        reference_nets = {item.net.casefold() for item in reference_pins}
        if len(reference_nets) != 1:
            continue

        endpoints.append(
            UsbEndpoint(
                reference=reference,
                symbol=symbol,
                footprint=component.footprint,
                positive_pins=(requirement.connector_positive_pin,),
                positive_net=positive_net,
                negative_pins=(requirement.connector_negative_pin,),
                negative_net=negative_net,
                reference_net=reference_pins[0].net,
                reference_pins=tuple(reference_pins),
                port_group=None,
                signal_family=requirement.connector_signal_family,
            )
        )
    return tuple(
        sorted(
            endpoints,
            key=lambda item: (
                item.reference.casefold(),
                item.reference,
                item.signal_family,
            ),
        )
    )


@dataclass(frozen=True, slots=True)
class _GenericConnectorContacts:
    positive_pins: tuple[str, ...]
    positive_functions: tuple[str, ...]
    negative_pins: tuple[str, ...]
    negative_functions: tuple[str, ...]
    connector_pin_count: int


class _GenericConnectorPinIndex:
    """Index complete generic connector inventories for exact USB line nets."""

    def __init__(self, observed: NetlistContract) -> None:
        self.assignments = pin_net_index(observed)
        self.symbols = casefolded_unique_index(observed.component_symbols)
        self.components = casefolded_unique_index(observed.components)
        self.inventories = casefolded_unique_index(observed.component_pin_numbers)
        self.functions = casefolded_unique_index(observed.pin_functions)
        self.electrical_types = casefolded_unique_index(observed.pin_electrical_types)

    def contacts_for_pair(
        self,
        connector_reference: str,
        positive_net: str,
        negative_net: str,
    ) -> _GenericConnectorContacts | None:
        connector_key = connector_reference.casefold()
        if connector_key not in self.symbols or connector_key not in self.components:
            return None
        numbers = self.inventories.get(connector_key)
        if not numbers or len({number.casefold() for number in numbers}) != len(numbers):
            return None
        pin_functions = tuple(
            self.functions.get(f"{connector_reference}.{number}".casefold()) for number in numbers
        )
        pin_types = tuple(
            self.electrical_types.get(f"{connector_reference}.{number}".casefold())
            for number in numbers
        )
        if any(function is None for function in pin_functions) or any(
            pin_type is None for pin_type in pin_types
        ):
            return None

        positive_net_key = positive_net.casefold()
        negative_net_key = negative_net.casefold()
        positive: list[tuple[str, str]] = []
        negative: list[tuple[str, str]] = []
        for number, function in zip(numbers, pin_functions, strict=True):
            pin = f"{connector_reference}.{number}"
            nets = self.assignments.nets_by_pin_key.get(pin.casefold(), frozenset())
            if len(nets) > 1:
                return None
            if len(nets) != 1 or not pin_function_is_generic(function):
                continue
            net = next(iter(nets))
            if net.casefold() == positive_net_key:
                positive.append((pin, function or ""))
            elif net.casefold() == negative_net_key:
                negative.append((pin, function or ""))
        positive_pins = tuple(sorted((item[0] for item in positive), key=_sort_key))
        negative_pins = tuple(sorted((item[0] for item in negative), key=_sort_key))
        if (
            not positive_pins
            or not negative_pins
            or {pin.casefold() for pin in positive_pins} & {pin.casefold() for pin in negative_pins}
        ):
            return None
        return _GenericConnectorContacts(
            positive_pins=positive_pins,
            positive_functions=_functions_for(positive_pins, positive),
            negative_pins=negative_pins,
            negative_functions=_functions_for(negative_pins, negative),
            connector_pin_count=len(numbers),
        )


def _sort_key(value: str) -> tuple[str, str]:
    return value.casefold(), value


def _functions_for(
    pins: tuple[str, ...], assignments: Iterable[tuple[str, str]]
) -> tuple[str, ...]:
    by_pin = {pin.casefold(): function for pin, function in assignments}
    return tuple(by_pin[pin.casefold()] for pin in pins)
