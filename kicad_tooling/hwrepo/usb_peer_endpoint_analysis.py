"""Recognize bounded USB connector and PHY endpoint pin groups."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import TypeVar

from .bus_signal_pairs import usb_data_function_identity
from .models import NetlistContract
from .return_nets import is_return_like_net_name
from .usb_peer_reference_types import (
    UsbEndpoint,
    UsbReferencePinAssignment,
)

IC_REFERENCE = re.compile(r"^(?:U|IC)[0-9]+$", re.IGNORECASE)


_NON_SIGNAL_REFERENCE_MARKER = re.compile(
    r"(?:^|[^A-Z0-9])(?:CHASSIS|SHIELD|FRAME|PE)(?:$|[^A-Z0-9])",
    re.IGNORECASE,
)


_RETURN_PIN_TYPES = frozenset({"passive", "power_in"})


_EXTENDED_RETURN_PIN_FUNCTIONS = frozenset({"gnda", "gndd", "gndp", "vssa", "vssd", "vssp"})


ValueT = TypeVar("ValueT")


def casefold_mapping(items: Mapping[str, ValueT]) -> dict[str, ValueT]:
    return {key.casefold(): value for key, value in items.items()}


def pin_net_index(observed: NetlistContract) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    by_pin: dict[str, set[str]] = {}
    by_net: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        net_key = net.casefold()
        for pin in pins:
            pin_key = pin.casefold()
            by_pin.setdefault(pin_key, set()).add(net)
            by_net.setdefault(net_key, set()).add(pin_key)
    return by_pin, by_net


def _return_pin_function(function: str) -> bool:
    normalized = re.sub(r"\d+$", "", function.strip())
    compact = re.sub(r"[^a-z0-9]", "", normalized.casefold())
    return not _NON_SIGNAL_REFERENCE_MARKER.search(normalized) and (
        compact in _EXTENDED_RETURN_PIN_FUNCTIONS or is_return_like_net_name(normalized)
    )


def usb_endpoint_reference_pins(
    observed: NetlistContract, reference: str
) -> tuple[UsbReferencePinAssignment, ...] | None:
    """Return complete, uniquely assigned explicit signal-reference pins for one endpoint."""
    pin_nets, _ = pin_net_index(observed)
    pin_inventories = casefold_mapping(observed.component_pin_numbers)
    functions = casefold_mapping(observed.pin_functions)
    electrical_types = casefold_mapping(observed.pin_electrical_types)
    numbers = pin_inventories.get(reference.casefold())
    if not numbers:
        return None
    assignments: list[UsbReferencePinAssignment] = []
    for raw_number in numbers:
        pin = f"{reference}.{raw_number}"
        pin_key = pin.casefold()
        function = functions.get(pin_key)
        electrical_type = electrical_types.get(pin_key)
        if function is None or electrical_type is None:
            return None
        if not _return_pin_function(function):
            continue
        normalized_type = electrical_type.casefold()
        nets = pin_nets.get(pin_key, set())
        if normalized_type not in _RETURN_PIN_TYPES or len(nets) != 1:
            return None
        assignments.append(
            UsbReferencePinAssignment(
                pin=pin,
                function=function,
                electrical_type=normalized_type,
                net=next(iter(nets)),
            )
        )
    if not assignments or len({item.net.casefold() for item in assignments}) != 1:
        return None
    return tuple(sorted(assignments, key=lambda item: (item.pin.casefold(), item.pin)))


def usb_endpoint(
    reference: str,
    observed: NetlistContract,
    *,
    connector: bool,
    pin_nets: dict[str, set[str]],
) -> tuple[UsbEndpoint, ...]:
    reference_key = reference.casefold()
    if reference_key in {item.casefold() for item in observed.dnp_components}:
        return ()
    if not connector and IC_REFERENCE.fullmatch(reference) is None:
        return ()

    symbols = casefold_mapping(observed.component_symbols)
    components = casefold_mapping(observed.components)
    pin_inventories = casefold_mapping(observed.component_pin_numbers)
    functions = casefold_mapping(observed.pin_functions)
    electrical_types = casefold_mapping(observed.pin_electrical_types)
    symbol = symbols.get(reference_key)
    component = components.get(reference_key)
    numbers = pin_inventories.get(reference_key)
    if symbol is None or component is None or not numbers:
        return ()

    roles: dict[str | None, dict[str, list[tuple[str, str]]]] = {}
    invalid_groups: set[str | None] = set()
    for raw_number in numbers:
        pin = f"{reference}.{raw_number}"
        pin_key = pin.casefold()
        function = functions.get(pin_key)
        electrical_type = electrical_types.get(pin_key)
        if function is None or electrical_type is None:
            return ()
        identity = usb_data_function_identity(function)
        if identity is not None:
            port_group, side = identity
            group = roles.setdefault(port_group, {"positive": [], "negative": []})
            nets = pin_nets.get(pin_key, set())
            if len(nets) != 1:
                invalid_groups.add(port_group)
                continue
            group[side].append((pin, next(iter(nets))))

    reference_pins = usb_endpoint_reference_pins(observed, reference)
    if not reference_pins:
        return ()
    reference_nets = {item.net.casefold() for item in reference_pins}
    if len(reference_nets) != 1:
        return ()
    endpoints: list[UsbEndpoint] = []
    for port_group, side_roles in roles.items():
        if port_group in invalid_groups:
            continue
        if not side_roles["positive"] or not side_roles["negative"]:
            continue
        positive_nets = {net.casefold() for _pin, net in side_roles["positive"]}
        negative_nets = {net.casefold() for _pin, net in side_roles["negative"]}
        if len(positive_nets) != 1 or len(negative_nets) != 1:
            continue
        positive_pins = tuple(
            sorted(
                (pin for pin, _net in side_roles["positive"]),
                key=lambda item: (item.casefold(), item),
            )
        )
        negative_pins = tuple(
            sorted(
                (pin for pin, _net in side_roles["negative"]),
                key=lambda item: (item.casefold(), item),
            )
        )
        positive_net = side_roles["positive"][0][1]
        negative_net = side_roles["negative"][0][1]
        if positive_net.casefold() == negative_net.casefold():
            continue
        endpoints.append(
            UsbEndpoint(
                reference=reference,
                symbol=symbol,
                footprint=component.footprint,
                positive_pins=positive_pins,
                positive_net=positive_net,
                negative_pins=negative_pins,
                negative_net=negative_net,
                reference_net=reference_pins[0].net,
                reference_pins=reference_pins,
                port_group=port_group,
            )
        )
    return tuple(
        sorted(
            endpoints,
            key=lambda item: (
                item.port_group is not None,
                int(item.port_group) if item.port_group is not None else -1,
            ),
        )
    )


def usb_endpoints(
    references: Iterable[str],
    observed: NetlistContract,
    pin_nets: dict[str, set[str]],
    *,
    connector: bool,
) -> tuple[UsbEndpoint, ...]:
    endpoints: list[UsbEndpoint] = []
    for reference in references:
        endpoints.extend(usb_endpoint(reference, observed, connector=connector, pin_nets=pin_nets))
    return tuple(endpoints)


def recognized_usb_data_groups(
    observed: NetlistContract, reference: str
) -> tuple[tuple[str | None, frozenset[str]], ...]:
    groups: dict[str | None, set[str]] = {}
    for pin, function in observed.pin_functions.items():
        pin_reference, separator, _number = pin.rpartition(".")
        if not separator or pin_reference.casefold() != reference.casefold():
            continue
        identity = usb_data_function_identity(function)
        if identity is not None:
            port_group, side = identity
            groups.setdefault(port_group, set()).add(side)
    return tuple(
        (port_group, frozenset(sides))
        for port_group, sides in sorted(
            groups.items(),
            key=lambda item: (
                item[0] is not None,
                int(item[0]) if item[0] is not None else -1,
            ),
        )
    )
