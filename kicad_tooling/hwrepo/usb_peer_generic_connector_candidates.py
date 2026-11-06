"""Find generic connector contacts assigned to recognized USB PHY data pairs."""

from __future__ import annotations

from collections.abc import Iterable

from .casefold_mapping_lookup import casefolded_unique_index
from .connector_identity import connector_candidate_references, pin_function_is_generic
from .netlist_contract_models import NetlistContract
from .usb_peer_endpoint_analysis import pin_net_index, usb_endpoint
from .usb_peer_generic_connector_models import UsbGenericConnectorDataPair


def generic_usb_connector_data_pair_candidates(
    observed: NetlistContract,
    reviewed_connector_references: tuple[str, ...] = (),
) -> tuple[UsbGenericConnectorDataPair, ...]:
    """Identify complete generic connector pin groups sharing one PHY's exact D+/D- nets.

    This is a coverage prompt predicate. It does not infer connector purpose or
    prove that a USB data path exists.
    """
    assignments = pin_net_index(observed)
    symbols = casefolded_unique_index(observed.component_symbols)
    components = casefolded_unique_index(observed.components)
    inventories = casefolded_unique_index(observed.component_pin_numbers)
    functions = casefolded_unique_index(observed.pin_functions)
    electrical_types = casefolded_unique_index(observed.pin_electrical_types)
    dnp = {reference.casefold() for reference in observed.dnp_components}
    connectors = connector_candidate_references(observed, reviewed_connector_references)
    found: list[UsbGenericConnectorDataPair] = []

    phy_endpoints = (
        endpoint
        for reference in observed.component_symbols
        for endpoint in usb_endpoint(reference, observed, connector=False, assignments=assignments)
        if endpoint.signal_family == "USB 2.0 data"
    )
    for endpoint in phy_endpoints:
        if len(endpoint.positive_pins) != 1 or len(endpoint.negative_pins) != 1:
            continue
        positive_net_key = endpoint.positive_net.casefold()
        negative_net_key = endpoint.negative_net.casefold()
        for connector_reference in connectors:
            connector_key = connector_reference.casefold()
            if connector_key == endpoint.reference.casefold() or connector_key in dnp:
                continue
            if connector_key not in symbols or connector_key not in components:
                continue
            numbers = inventories.get(connector_key)
            if not numbers or len({number.casefold() for number in numbers}) != len(numbers):
                continue
            connector_functions = tuple(
                functions.get(f"{connector_reference}.{number}".casefold()) for number in numbers
            )
            connector_types = tuple(
                electrical_types.get(f"{connector_reference}.{number}".casefold())
                for number in numbers
            )
            if any(function is None for function in connector_functions) or any(
                pin_type is None for pin_type in connector_types
            ):
                continue

            positive: list[tuple[str, str]] = []
            negative: list[tuple[str, str]] = []
            ambiguous = False
            for number, function in zip(numbers, connector_functions, strict=True):
                pin = f"{connector_reference}.{number}"
                nets = assignments.nets_by_pin_key.get(pin.casefold(), frozenset())
                if len(nets) > 1:
                    ambiguous = True
                    break
                if len(nets) != 1 or not pin_function_is_generic(function):
                    continue
                net = next(iter(nets))
                if net.casefold() == positive_net_key:
                    positive.append((pin, function or ""))
                elif net.casefold() == negative_net_key:
                    negative.append((pin, function or ""))
            if ambiguous or not positive or not negative:
                continue
            positive_pins = tuple(sorted((item[0] for item in positive), key=_sort_key))
            negative_pins = tuple(sorted((item[0] for item in negative), key=_sort_key))
            if {pin.casefold() for pin in positive_pins} & {
                pin.casefold() for pin in negative_pins
            }:
                continue
            positive_functions = _functions_for(positive_pins, positive)
            negative_functions = _functions_for(negative_pins, negative)
            found.append(
                UsbGenericConnectorDataPair(
                    connector_reference=connector_reference,
                    phy_reference=endpoint.reference,
                    port_group=endpoint.port_group,
                    positive_pins=positive_pins,
                    positive_functions=positive_functions,
                    positive_net=endpoint.positive_net,
                    negative_pins=negative_pins,
                    negative_functions=negative_functions,
                    negative_net=endpoint.negative_net,
                    connector_pin_count=len(numbers),
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


def _sort_key(value: str) -> tuple[str, str]:
    return value.casefold(), value


def _functions_for(
    pins: tuple[str, ...], assignments: Iterable[tuple[str, str]]
) -> tuple[str, ...]:
    by_pin = {pin.casefold(): function for pin, function in assignments}
    return tuple(by_pin[pin.casefold()] for pin in pins)
