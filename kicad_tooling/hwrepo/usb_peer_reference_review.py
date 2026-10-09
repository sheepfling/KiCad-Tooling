"""Review supported USB 2.0 connector-to-PHY links with separate references."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Literal, TypeVar

from .bus_heuristics import usb_data_function_identity
from .connector_pins import connector_candidate_references
from .models import NetlistContract, UsbDataPathLineRequirement, UsbDataPathMap
from .return_nets import is_return_like_net_name

_IC_REFERENCE = re.compile(r"^(?:U|IC)[0-9]+$", re.IGNORECASE)
_NON_SIGNAL_REFERENCE_MARKER = re.compile(
    r"(?:^|[^A-Z0-9])(?:CHASSIS|SHIELD|FRAME|PE)(?:$|[^A-Z0-9])",
    re.IGNORECASE,
)
_RETURN_PIN_TYPES = frozenset({"passive", "power_in"})
_EXTENDED_RETURN_PIN_FUNCTIONS = frozenset({"gnda", "gndd", "gndp", "vssa", "vssd", "vssp"})
_DIODE_REFERENCE = re.compile(r"^D[A-Z]*[0-9]+$", re.IGNORECASE)
_RESISTOR_SYMBOL = re.compile(r"^Device:R(?:_[A-Z0-9_]+)?$", re.IGNORECASE)
_Value = TypeVar("_Value")


@dataclass(frozen=True)
class UsbReferencePinAssignment:
    pin: str
    function: str
    electrical_type: str
    net: str


@dataclass(frozen=True)
class UsbPeerDataShuntBranch:
    data_pin: str
    reference_pin: str
    symbol: str
    data_net: str
    reference_net: str


@dataclass(frozen=True)
class UsbPeerDataSeriesResistor:
    reference: str
    symbol: str
    footprint: str
    value: str
    connector_pin: str
    phy_pin: str
    connector_net: str
    phy_net: str


@dataclass(frozen=True)
class UsbPeerDataLink:
    connector_positive_pin: str
    phy_positive_pin: str
    connector_positive_net: str
    phy_positive_net: str
    connector_negative_pin: str
    phy_negative_pin: str
    connector_negative_net: str
    phy_negative_net: str
    connector_positive_pins: tuple[str, ...]
    phy_positive_pins: tuple[str, ...]
    connector_negative_pins: tuple[str, ...]
    phy_negative_pins: tuple[str, ...]
    positive_shunt_branches: tuple[UsbPeerDataShuntBranch, ...] = ()
    negative_shunt_branches: tuple[UsbPeerDataShuntBranch, ...] = ()
    positive_series_resistor: UsbPeerDataSeriesResistor | None = None
    negative_series_resistor: UsbPeerDataSeriesResistor | None = None
    port_group: str | None = None


@dataclass(frozen=True)
class UsbPeerReferenceReview:
    connector_reference: str
    phy_reference: str
    connector_symbol: str
    phy_symbol: str
    connector_footprint: str
    phy_footprint: str
    connector_reference_net: str
    phy_reference_net: str
    connector_reference_pins: tuple[UsbReferencePinAssignment, ...]
    phy_reference_pins: tuple[UsbReferencePinAssignment, ...]
    data_link: UsbPeerDataLink


@dataclass(frozen=True)
class UsbPeerReferencePathCoverage:
    """One supported connector-to-PHY path and its reference disposition."""

    connector_reference: str
    phy_reference: str
    connector_symbol: str
    phy_symbol: str
    connector_footprint: str
    phy_footprint: str
    connector_reference_net: str
    phy_reference_net: str
    connector_reference_pins: tuple[UsbReferencePinAssignment, ...]
    phy_reference_pins: tuple[UsbReferencePinAssignment, ...]
    reference_disposition: Literal[
        "COMMON_REFERENCE",
        "SEPARATE_REFERENCE_REVIEW",
        "MAP_COVERED_SEPARATE_REFERENCE",
    ]
    data_link: UsbPeerDataLink


@dataclass(frozen=True)
class UsbPeerReferenceCoverage:
    """Bounded endpoint and data-path counts for the USB reference heuristic."""

    endpoint_groups: tuple[UsbPeerEndpointGroupCoverage, ...]
    path_entries: tuple[UsbPeerReferencePathCoverage, ...]
    recognized_connector_group_count: int
    supported_connector_group_count: int
    recognized_phy_group_count: int
    supported_phy_group_count: int
    dnp_group_count: int
    incomplete_group_count: int
    supported_data_path_count: int
    common_reference_path_count: int
    separate_reference_path_count: int
    mapped_separate_reference_path_count: int
    review_candidate_group_count: int


@dataclass(frozen=True)
class UsbPeerEndpointGroupCoverage:
    """Identity and bounded disposition for one recognized USB endpoint group."""

    endpoint_role: Literal["connector", "phy"]
    reference: str
    port_group: str | None
    disposition: Literal["SUPPORTED", "INCOMPLETE", "DNP"]


@dataclass(frozen=True)
class UsbPeerReferenceScan:
    """Review candidates and applicability counts from one deterministic scan."""

    reviews: tuple[UsbPeerReferenceReview, ...]
    coverage: UsbPeerReferenceCoverage


@dataclass(frozen=True)
class _Endpoint:
    reference: str
    symbol: str
    footprint: str
    positive_pins: tuple[str, ...]
    positive_net: str
    negative_pins: tuple[str, ...]
    negative_net: str
    reference_net: str
    reference_pins: tuple[UsbReferencePinAssignment, ...]
    port_group: str | None


def _keyed(items: Mapping[str, _Value]) -> dict[str, _Value]:
    return {key.casefold(): value for key, value in items.items()}


def _pin_net_index(observed: NetlistContract) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
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
    pin_nets, _ = _pin_net_index(observed)
    pin_inventories = _keyed(observed.component_pin_numbers)
    functions = _keyed(observed.pin_functions)
    electrical_types = _keyed(observed.pin_electrical_types)
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


def _endpoint(
    reference: str,
    observed: NetlistContract,
    *,
    connector: bool,
    pin_nets: dict[str, set[str]],
) -> tuple[_Endpoint, ...]:
    reference_key = reference.casefold()
    if reference_key in {item.casefold() for item in observed.dnp_components}:
        return ()
    if not connector and _IC_REFERENCE.fullmatch(reference) is None:
        return ()

    symbols = _keyed(observed.component_symbols)
    components = _keyed(observed.components)
    pin_inventories = _keyed(observed.component_pin_numbers)
    functions = _keyed(observed.pin_functions)
    electrical_types = _keyed(observed.pin_electrical_types)
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
    endpoints: list[_Endpoint] = []
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
            _Endpoint(
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


def _endpoints(
    references: Iterable[str],
    observed: NetlistContract,
    pin_nets: dict[str, set[str]],
    *,
    connector: bool,
) -> tuple[_Endpoint, ...]:
    endpoints: list[_Endpoint] = []
    for reference in references:
        endpoints.extend(_endpoint(reference, observed, connector=connector, pin_nets=pin_nets))
    return tuple(endpoints)


def _recognized_data_groups(
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


def _d_designated_shunt_branches(
    observed: NetlistContract,
    data_net: str,
    extra_pins: set[str],
    reference_nets: set[str],
) -> tuple[UsbPeerDataShuntBranch, ...] | None:
    """Accept complete two-pin passive D-designated branches to endpoint references."""
    if not extra_pins:
        return ()
    components = _keyed(observed.components)
    symbols = _keyed(observed.component_symbols)
    inventories = _keyed(observed.component_pin_numbers)
    electrical_types = _keyed(observed.pin_electrical_types)
    component_references = {reference.casefold(): reference for reference in observed.components}
    pin_nets, _net_members = _pin_net_index(observed)
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
    inventories = _keyed(observed.component_pin_numbers)
    components = _keyed(observed.components)
    symbols = _keyed(observed.component_symbols)
    electrical_types = _keyed(observed.pin_electrical_types)
    display_references = {reference.casefold(): reference for reference in observed.components}
    pin_nets, _net_members = _pin_net_index(observed)
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
    connector: _Endpoint,
    phy: _Endpoint,
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


def _data_link(
    connector: _Endpoint,
    phy: _Endpoint,
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


def _mapped_line_matches(
    requirement: UsbDataPathLineRequirement,
    connector_pins: tuple[str, ...],
    phy_pins: tuple[str, ...],
    connector_net: str,
    phy_net: str,
    series_resistor: UsbPeerDataSeriesResistor | None,
) -> bool:
    if (
        requirement.topology != ("series_resistor" if series_resistor is not None else "direct")
        or {pin.casefold() for pin in requirement.connector_pins}
        != {pin.casefold() for pin in connector_pins}
        or {pin.casefold() for pin in requirement.phy_pins} != {pin.casefold() for pin in phy_pins}
        or requirement.connector_net.casefold() != connector_net.casefold()
        or requirement.phy_net.casefold() != phy_net.casefold()
    ):
        return False
    mapped_resistor = requirement.series_resistor
    if series_resistor is None:
        return mapped_resistor is None
    return (
        mapped_resistor is not None
        and mapped_resistor.reference.casefold() == series_resistor.reference.casefold()
        and mapped_resistor.expected_symbol == series_resistor.symbol
        and mapped_resistor.expected_footprint == series_resistor.footprint
    )


def _mapped_reference_review(
    connector: _Endpoint,
    phy: _Endpoint,
    data_link: UsbPeerDataLink,
    path_map: UsbDataPathMap | None,
) -> bool:
    """Match a current bounded USB map with an explicit common/separate decision."""
    if path_map is None:
        return False
    observed_connector_references = {item.pin.casefold() for item in connector.reference_pins}
    observed_phy_references = {item.pin.casefold() for item in phy.reference_pins}
    for interface in path_map.interfaces:
        if interface.reference_policy is None:
            continue
        if (
            interface.data_port_group is not None
            and interface.data_port_group != data_link.port_group
        ):
            continue
        if (
            interface.connector_reference.casefold() != connector.reference.casefold()
            or interface.phy_reference.casefold() != phy.reference.casefold()
            or interface.expected_connector_symbol != connector.symbol
            or interface.expected_phy_symbol != phy.symbol
            or interface.expected_connector_footprint != connector.footprint
            or interface.expected_phy_footprint != phy.footprint
            or not _mapped_line_matches(
                interface.positive,
                data_link.connector_positive_pins,
                data_link.phy_positive_pins,
                data_link.connector_positive_net,
                data_link.phy_positive_net,
                data_link.positive_series_resistor,
            )
            or not _mapped_line_matches(
                interface.negative,
                data_link.connector_negative_pins,
                data_link.phy_negative_pins,
                data_link.connector_negative_net,
                data_link.phy_negative_net,
                data_link.negative_series_resistor,
            )
        ):
            continue
        mapped_connector_references = {
            item.pin.casefold() for item in interface.connector_reference_pins
        }
        mapped_phy_references = {item.pin.casefold() for item in interface.phy_reference_pins}
        if (
            mapped_connector_references == observed_connector_references
            and mapped_phy_references == observed_phy_references
        ):
            return True
    return False


def scan_usb_peer_reference_reviews(
    observed: NetlistContract,
    path_map: UsbDataPathMap | None = None,
    declared_connector_references: tuple[str, ...] = (),
) -> UsbPeerReferenceScan:
    """Scan supported USB peers and count bounded heuristic applicability.

    Both fitted endpoints need complete native pin inventories and one or more
    same-net positive and negative USB data pins within one port group, plus
    uniquely assigned passive/power_in reference pins on one net. Numbered
    DPn/DMn aliases pair only with the same number; unnumbered D+/D- aliases
    pair with each other or with one numbered endpoint group. Each data line must be direct
    or joined by exactly one fitted two-pin Device:R between endpoint nets.
    Complete two-pin passive diode-designated shunts to either endpoint
    reference may also appear on those nets. Longer series paths, extra data
    peers, DNP parts, multi-pin protection parts, and mixed reference domains
    remain outside this bounded topology check.
    """
    pin_nets, net_members = _pin_net_index(observed)
    connector_candidates = connector_candidate_references(observed, declared_connector_references)
    connector_references = {item.casefold() for item in connector_candidates}
    connectors = _endpoints(
        connector_candidates,
        observed,
        pin_nets,
        connector=True,
    )
    phy_references = tuple(
        reference
        for reference in sorted(observed.components, key=lambda item: (item.casefold(), item))
        if reference.casefold() not in connector_references
        and _IC_REFERENCE.fullmatch(reference) is not None
    )
    phy_endpoints = _endpoints(
        phy_references,
        observed,
        pin_nets,
        connector=False,
    )
    dnp = {reference.casefold() for reference in observed.dnp_components}
    supported_connector_groups = {
        (endpoint.reference.casefold(), endpoint.port_group) for endpoint in connectors
    }
    supported_phy_groups = {
        (endpoint.reference.casefold(), endpoint.port_group) for endpoint in phy_endpoints
    }

    def group_coverage(
        references: Iterable[str],
        *,
        endpoint_role: Literal["connector", "phy"],
        supported: set[tuple[str, str | None]],
    ) -> tuple[UsbPeerEndpointGroupCoverage, ...]:
        result: list[UsbPeerEndpointGroupCoverage] = []
        for reference in references:
            reference_key = reference.casefold()
            for port_group, _sides in _recognized_data_groups(observed, reference):
                disposition: Literal["SUPPORTED", "INCOMPLETE", "DNP"] = (
                    "DNP"
                    if reference_key in dnp
                    else "SUPPORTED"
                    if (reference_key, port_group) in supported
                    else "INCOMPLETE"
                )
                result.append(
                    UsbPeerEndpointGroupCoverage(
                        endpoint_role=endpoint_role,
                        reference=reference,
                        port_group=port_group,
                        disposition=disposition,
                    )
                )
        return tuple(result)

    endpoint_groups = tuple(
        sorted(
            (
                *group_coverage(
                    connector_candidates,
                    endpoint_role="connector",
                    supported=supported_connector_groups,
                ),
                *group_coverage(
                    phy_references,
                    endpoint_role="phy",
                    supported=supported_phy_groups,
                ),
            ),
            key=lambda item: (
                0 if item.endpoint_role == "connector" else 1,
                item.reference.casefold(),
                item.reference,
                item.port_group is not None,
                int(item.port_group) if item.port_group is not None else -1,
            ),
        )
    )
    recognized_connector_group_count = sum(
        item.endpoint_role == "connector" for item in endpoint_groups
    )
    recognized_phy_group_count = sum(item.endpoint_role == "phy" for item in endpoint_groups)
    dnp_group_count = sum(item.disposition == "DNP" for item in endpoint_groups)
    incomplete_group_count = sum(item.disposition == "INCOMPLETE" for item in endpoint_groups)

    findings: list[UsbPeerReferenceReview] = []
    path_entries: list[UsbPeerReferencePathCoverage] = []
    for connector in connectors:
        for phy in phy_endpoints:
            data_link = _data_link(connector, phy, net_members, observed)
            if data_link is None:
                continue
            common_reference = connector.reference_net.casefold() == phy.reference_net.casefold()
            mapped_separate_reference = not common_reference and _mapped_reference_review(
                connector, phy, data_link, path_map
            )
            reference_disposition: Literal[
                "COMMON_REFERENCE",
                "SEPARATE_REFERENCE_REVIEW",
                "MAP_COVERED_SEPARATE_REFERENCE",
            ] = (
                "COMMON_REFERENCE"
                if common_reference
                else "MAP_COVERED_SEPARATE_REFERENCE"
                if mapped_separate_reference
                else "SEPARATE_REFERENCE_REVIEW"
            )
            path_entries.append(
                UsbPeerReferencePathCoverage(
                    connector_reference=connector.reference,
                    phy_reference=phy.reference,
                    connector_symbol=connector.symbol,
                    phy_symbol=phy.symbol,
                    connector_footprint=connector.footprint,
                    phy_footprint=phy.footprint,
                    connector_reference_net=connector.reference_net,
                    phy_reference_net=phy.reference_net,
                    connector_reference_pins=connector.reference_pins,
                    phy_reference_pins=phy.reference_pins,
                    reference_disposition=reference_disposition,
                    data_link=data_link,
                )
            )
            if common_reference or mapped_separate_reference:
                continue
            findings.append(
                UsbPeerReferenceReview(
                    connector_reference=connector.reference,
                    phy_reference=phy.reference,
                    connector_symbol=connector.symbol,
                    phy_symbol=phy.symbol,
                    connector_footprint=connector.footprint,
                    phy_footprint=phy.footprint,
                    connector_reference_net=connector.reference_net,
                    phy_reference_net=phy.reference_net,
                    connector_reference_pins=connector.reference_pins,
                    phy_reference_pins=phy.reference_pins,
                    data_link=data_link,
                )
            )
    reviews = tuple(
        sorted(
            findings,
            key=lambda item: (
                item.connector_reference.casefold(),
                item.phy_reference.casefold(),
                item.connector_reference_net.casefold(),
                item.phy_reference_net.casefold(),
                item.data_link.port_group is not None,
                (int(item.data_link.port_group) if item.data_link.port_group is not None else -1),
            ),
        )
    )
    ordered_path_entries = tuple(
        sorted(
            path_entries,
            key=lambda item: (
                item.connector_reference.casefold(),
                item.connector_reference,
                item.phy_reference.casefold(),
                item.phy_reference,
                item.data_link.port_group is not None,
                item.data_link.port_group or "",
            ),
        )
    )
    common_reference_path_count = sum(
        item.reference_disposition == "COMMON_REFERENCE" for item in ordered_path_entries
    )
    separate_reference_path_count = sum(
        item.reference_disposition != "COMMON_REFERENCE" for item in ordered_path_entries
    )
    mapped_separate_reference_path_count = sum(
        item.reference_disposition == "MAP_COVERED_SEPARATE_REFERENCE"
        for item in ordered_path_entries
    )
    return UsbPeerReferenceScan(
        reviews=reviews,
        coverage=UsbPeerReferenceCoverage(
            endpoint_groups=endpoint_groups,
            path_entries=ordered_path_entries,
            recognized_connector_group_count=recognized_connector_group_count,
            supported_connector_group_count=sum(
                item.endpoint_role == "connector" and item.disposition == "SUPPORTED"
                for item in endpoint_groups
            ),
            recognized_phy_group_count=recognized_phy_group_count,
            supported_phy_group_count=sum(
                item.endpoint_role == "phy" and item.disposition == "SUPPORTED"
                for item in endpoint_groups
            ),
            dnp_group_count=dnp_group_count,
            incomplete_group_count=incomplete_group_count,
            supported_data_path_count=len(ordered_path_entries),
            common_reference_path_count=common_reference_path_count,
            separate_reference_path_count=separate_reference_path_count,
            mapped_separate_reference_path_count=mapped_separate_reference_path_count,
            review_candidate_group_count=len(reviews),
        ),
    )


def usb_peer_reference_reviews(
    observed: NetlistContract,
    path_map: UsbDataPathMap | None = None,
    declared_connector_references: tuple[str, ...] = (),
) -> tuple[UsbPeerReferenceReview, ...]:
    """Prompt on supported USB 2.0 peers with different explicit references."""
    return scan_usb_peer_reference_reviews(
        observed, path_map, declared_connector_references
    ).reviews
