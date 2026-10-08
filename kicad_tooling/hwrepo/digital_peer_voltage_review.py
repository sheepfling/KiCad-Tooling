"""Review source-bound digital peers that use different voltage-named rails."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from itertools import combinations
from typing import Literal

from .models import (
    DigitalPeerPinRequirement,
    DigitalPeerVoltageAnalysis,
    NetlistContract,
)
from .return_nets import is_return_like_net_name
from .serial_participants import serial_function_role_and_channel

_IC_REFERENCE = re.compile(r"^(?:U|IC)[0-9]+$", re.IGNORECASE)
_SPI_CLOCK = frozenset({"sck", "sclk"})
_SPI_DATA = frozenset({"mosi", "sdi", "copi", "miso", "sdo", "cipo"})
_SPI_SELECT = frozenset({"cs", "csn", "ncs", "nss", "ss", "ssel", "ce0", "ce1"})
_SPI_FUNCTIONS = _SPI_CLOCK | _SPI_DATA | _SPI_SELECT
_OUTPUT_TYPES = frozenset({"output", "tri_state", "bidirectional"})
_INPUT_TYPES = frozenset({"input", "bidirectional"})
_RAIL_TOKEN = re.compile(
    r"(?<![A-Z0-9+-])\+?(?P<whole>\d+)"
    r"(?:V(?P<suffix_fraction>\d+)|\.(?P<decimal_fraction>\d+)V|V)"
    r"(?![A-Z0-9])",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class VoltageNamedRail:
    net: str
    voltage_v: Decimal


@dataclass(frozen=True)
class DigitalPeerLink:
    interface: Literal["SPI", "serial"]
    output_role: str | None
    output_reference: str
    output_pin: str
    output_function: str
    output_type: str
    input_reference: str
    input_role: str | None
    input_pin: str
    input_function: str
    input_type: str
    net: str


@dataclass
class _PeerGroup:
    interface: Literal["SPI", "serial"]
    output_rail: VoltageNamedRail
    input_rail: VoltageNamedRail
    links: set[DigitalPeerLink] = field(default_factory=lambda: set[DigitalPeerLink]())


@dataclass(frozen=True)
class DigitalPeerVoltageReview:
    interface: Literal["SPI", "serial"]
    output_reference: str
    input_reference: str
    output_rail: VoltageNamedRail
    input_rail: VoltageNamedRail
    links: tuple[DigitalPeerLink, ...]


@dataclass(frozen=True)
class DigitalPeerVoltageCoverage:
    """Counts the supported direct-peer links examined by one interface rule."""

    interface: Literal["SPI", "serial"]
    recognized_endpoint_count: int
    assigned_endpoint_count: int
    direct_peer_link_count: int
    voltage_comparison_count: int
    same_voltage_link_count: int
    different_voltage_link_count: int
    mapped_mismatch_link_count: int
    review_candidate_group_count: int


@dataclass(frozen=True)
class DigitalPeerVoltageScan:
    """Grouped review candidates plus bounded applicability counts."""

    reviews: tuple[DigitalPeerVoltageReview, ...]
    coverage: tuple[DigitalPeerVoltageCoverage, ...]


def _canonical_spi_function(value: str) -> str:
    function = re.sub(r"[^a-z0-9]", "", value.casefold())
    if function.startswith("spi"):
        function = function[3:].lstrip("0123456789")
    return function


def _interface_and_role(
    value: str,
) -> tuple[Literal["SPI", "serial"], str | None] | None:
    if _canonical_spi_function(value) in _SPI_FUNCTIONS:
        return "SPI", None
    role_channel = serial_function_role_and_channel(value)
    if role_channel is not None:
        return "serial", role_channel[0]
    return None


def _nominal_voltage_from_net_name(name: str) -> Decimal | None:
    """Read only explicit positive-voltage tokens; names remain review clues."""
    matches = tuple(_RAIL_TOKEN.finditer(name))
    if len(matches) != 1:
        return None
    match = matches[0]
    whole = Decimal(match.group("whole"))
    suffix_fraction = match.group("suffix_fraction")
    decimal_fraction = match.group("decimal_fraction")
    fraction = suffix_fraction or decimal_fraction
    if fraction is not None:
        whole += Decimal(fraction).scaleb(-len(fraction))
    if whole <= 0:
        return None
    return whole.normalize()


def _pin_assignment_index(
    observed: NetlistContract,
) -> tuple[dict[str, set[str]], dict[str, str], dict[str, str]]:
    pin_nets: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin.casefold(), set()).add(net)
    references = {reference.casefold(): reference for reference in observed.components}
    symbols = {
        reference.casefold(): symbol for reference, symbol in observed.component_symbols.items()
    }
    return pin_nets, references, symbols


def _is_return_assignment(net: str, function: str) -> bool:
    """Recognize return labels and functions with optional trailing pin indices."""
    return any(
        is_return_like_net_name(re.sub(r"\d+$", "", value.strip())) for value in (net, function)
    )


def _unambiguous_voltage_named_supply(
    reference: str,
    observed: NetlistContract,
    pin_nets: dict[str, set[str]],
) -> VoltageNamedRail | None:
    """Require complete native pin types and exactly one assigned positive rail."""
    reference_key = reference.casefold()
    pin_numbers = next(
        (
            numbers
            for component, numbers in observed.component_pin_numbers.items()
            if component.casefold() == reference_key
        ),
        (),
    )
    if not pin_numbers:
        return None

    types = {
        pin.casefold(): pin_type.casefold()
        for pin, pin_type in observed.pin_electrical_types.items()
    }
    functions = {pin.casefold(): function for pin, function in observed.pin_functions.items()}
    if any(f"{reference}.{number}".casefold() not in types for number in pin_numbers):
        return None

    assigned_positive: dict[str, Decimal] = {}
    found_power_input = False
    for number in pin_numbers:
        pin = f"{reference}.{number}"
        if types.get(pin.casefold()) != "power_in":
            continue
        found_power_input = True
        nets = pin_nets.get(pin.casefold(), set())
        if len(nets) != 1:
            return None
        net = next(iter(nets))
        if _is_return_assignment(net, functions.get(pin.casefold(), "")):
            continue
        nominal = _nominal_voltage_from_net_name(net)
        if nominal is None:
            return None
        assigned_positive[net] = nominal

    if not found_power_input or len(assigned_positive) != 1:
        return None
    net, voltage = next(iter(assigned_positive.items()))
    return VoltageNamedRail(net=net, voltage_v=voltage)


def _endpoint_matches_native(
    endpoint: DigitalPeerPinRequirement,
    observed: NetlistContract,
    pin_nets: dict[str, set[str]],
    references: dict[str, str],
    symbols: dict[str, str],
) -> bool:
    reference = endpoint.reference
    reference_key = reference.casefold()
    canonical_reference = references.get(reference_key)
    if canonical_reference is None or canonical_reference.casefold() in {
        item.casefold() for item in observed.dnp_components
    }:
        return False
    component = next(
        (
            item
            for component_reference, item in observed.components.items()
            if component_reference.casefold() == reference_key
        ),
        None,
    )
    if (
        component is None
        or symbols.get(reference_key) != endpoint.symbol
        or component.footprint != endpoint.footprint
    ):
        return False
    pin = endpoint.pin
    net = endpoint.net
    return pin_nets.get(pin.casefold(), set()) == {net}


def _fully_mapped_link(
    link: DigitalPeerLink,
    analysis: DigitalPeerVoltageAnalysis | None,
    observed: NetlistContract,
    pin_nets: dict[str, set[str]],
    references: dict[str, str],
    symbols: dict[str, str],
) -> bool:
    if analysis is None:
        return False
    for reviewed in analysis.links:
        output_limits = reviewed.output_limits
        input_limits = reviewed.input_limits
        driver = reviewed.driver
        receiver = reviewed.receiver
        if output_limits is None or input_limits is None:
            continue
        if (
            driver.reference.casefold() != link.output_reference.casefold()
            or driver.pin.casefold() != link.output_pin.casefold()
            or receiver.reference.casefold() != link.input_reference.casefold()
            or receiver.pin.casefold() != link.input_pin.casefold()
            or driver.net != link.net
            or receiver.net != link.net
        ):
            continue
        if _endpoint_matches_native(
            driver, observed, pin_nets, references, symbols
        ) and _endpoint_matches_native(receiver, observed, pin_nets, references, symbols):
            return True
    return False


def scan_digital_peer_voltage_reviews(
    observed: NetlistContract,
    analysis: DigitalPeerVoltageAnalysis | None = None,
) -> DigitalPeerVoltageScan:
    """Find voltage-domain hints and count the supported scope examined.

    The rail parser supplies a review clue only. It deliberately skips missing
    pin-type inventories, ambiguous supplies, unconnected supplies, unsupported
    signal functions, open-drain electrical types, and fully mapped peer links.
    """
    pin_nets, references, symbols = _pin_assignment_index(observed)
    dnp = {reference.casefold() for reference in observed.dnp_components}
    by_net: dict[
        str,
        list[tuple[str, str, str, str, Literal["SPI", "serial"], str | None]],
    ] = {}
    counts: dict[Literal["SPI", "serial"], dict[str, int]] = {
        interface: {
            "recognized_endpoint_count": 0,
            "assigned_endpoint_count": 0,
            "direct_peer_link_count": 0,
            "voltage_comparison_count": 0,
            "same_voltage_link_count": 0,
            "different_voltage_link_count": 0,
            "mapped_mismatch_link_count": 0,
            "review_candidate_group_count": 0,
        }
        for interface in ("SPI", "serial")
    }

    for pin, raw_function in observed.pin_functions.items():
        reference, separator, _number = pin.rpartition(".")
        reference_key = reference.casefold()
        canonical_reference = references.get(reference_key)
        if (
            not separator
            or canonical_reference is None
            or not _IC_REFERENCE.fullmatch(canonical_reference)
            or reference_key in dnp
        ):
            continue
        recognized = _interface_and_role(raw_function)
        if recognized is None:
            continue
        interface, role = recognized
        counts[interface]["recognized_endpoint_count"] += 1
        electrical_type = observed.pin_electrical_types.get(pin)
        if electrical_type is None:
            electrical_type = next(
                (
                    value
                    for candidate, value in observed.pin_electrical_types.items()
                    if candidate.casefold() == pin.casefold()
                ),
                None,
            )
        if electrical_type is None or electrical_type.casefold() not in (
            _OUTPUT_TYPES | _INPUT_TYPES
        ):
            continue
        assigned = pin_nets.get(pin.casefold(), set())
        if len(assigned) != 1:
            continue
        counts[interface]["assigned_endpoint_count"] += 1
        net = next(iter(assigned))
        by_net.setdefault(net, []).append(
            (canonical_reference, pin, raw_function, electrical_type.casefold(), interface, role)
        )

    rails: dict[str, VoltageNamedRail | None] = {}
    groups: dict[tuple[str, str, str], _PeerGroup] = {}
    for net, endpoints in sorted(by_net.items()):
        if is_return_like_net_name(net) or _nominal_voltage_from_net_name(net) is not None:
            continue
        for left, right in combinations(sorted(endpoints), 2):
            (
                left_reference,
                left_pin,
                left_function,
                left_type,
                left_interface,
                left_role,
            ) = left
            (
                right_reference,
                right_pin,
                right_function,
                right_type,
                right_interface,
                right_role,
            ) = right
            if left_reference.casefold() == right_reference.casefold():
                continue
            if left_interface != right_interface:
                continue
            interface = left_interface
            directions: list[DigitalPeerLink] = []
            left_can_output = left_type in _OUTPUT_TYPES and (
                interface == "SPI" or left_role == "tx"
            )
            right_can_output = right_type in _OUTPUT_TYPES and (
                interface == "SPI" or right_role == "tx"
            )
            left_can_input = left_type in _INPUT_TYPES and (interface == "SPI" or left_role == "rx")
            right_can_input = right_type in _INPUT_TYPES and (
                interface == "SPI" or right_role == "rx"
            )
            if left_can_output and right_can_input:
                directions.append(
                    DigitalPeerLink(
                        interface=interface,
                        output_role=left_role,
                        output_reference=left_reference,
                        output_pin=left_pin,
                        output_function=left_function,
                        output_type=left_type,
                        input_reference=right_reference,
                        input_role=right_role,
                        input_pin=right_pin,
                        input_function=right_function,
                        input_type=right_type,
                        net=net,
                    )
                )
            if right_can_output and left_can_input:
                directions.append(
                    DigitalPeerLink(
                        interface=interface,
                        output_role=right_role,
                        output_reference=right_reference,
                        output_pin=right_pin,
                        output_function=right_function,
                        output_type=right_type,
                        input_reference=left_reference,
                        input_role=left_role,
                        input_pin=left_pin,
                        input_function=left_function,
                        input_type=left_type,
                        net=net,
                    )
                )
            # Two bidirectional pins do not provide an unambiguous direction.
            if len(directions) != 1:
                continue
            link = directions[0]
            counts[interface]["direct_peer_link_count"] += 1
            if link.output_reference not in rails:
                rails[link.output_reference] = _unambiguous_voltage_named_supply(
                    link.output_reference, observed, pin_nets
                )
            if link.input_reference not in rails:
                rails[link.input_reference] = _unambiguous_voltage_named_supply(
                    link.input_reference, observed, pin_nets
                )
            output_rail = rails[link.output_reference]
            input_rail = rails[link.input_reference]
            if output_rail is None or input_rail is None:
                continue
            counts[interface]["voltage_comparison_count"] += 1
            if output_rail.voltage_v == input_rail.voltage_v:
                counts[interface]["same_voltage_link_count"] += 1
                continue
            counts[interface]["different_voltage_link_count"] += 1
            if _fully_mapped_link(link, analysis, observed, pin_nets, references, symbols):
                counts[interface]["mapped_mismatch_link_count"] += 1
                continue
            key = (
                link.interface,
                link.output_reference.casefold(),
                link.input_reference.casefold(),
            )
            group = groups.get(key)
            if group is None:
                group = _PeerGroup(
                    interface=link.interface,
                    output_rail=output_rail,
                    input_rail=input_rail,
                )
                groups[key] = group
            group.links.add(link)

    result = tuple(
        DigitalPeerVoltageReview(
            interface=group.interface,
            output_reference=next(
                endpoint for endpoint in references.values() if endpoint.casefold() == key[1]
            ),
            input_reference=next(
                endpoint for endpoint in references.values() if endpoint.casefold() == key[2]
            ),
            output_rail=group.output_rail,
            input_rail=group.input_rail,
            links=tuple(
                sorted(
                    group.links,
                    key=lambda item: (
                        item.net.casefold(),
                        item.output_pin.casefold(),
                        item.input_pin.casefold(),
                    ),
                )
            ),
        )
        for key, group in sorted(groups.items())
    )
    for peer in result:
        counts[peer.interface]["review_candidate_group_count"] += 1
    coverage = tuple(
        DigitalPeerVoltageCoverage(interface=interface, **counts[interface])
        for interface in ("SPI", "serial")
    )
    return DigitalPeerVoltageScan(reviews=result, coverage=coverage)


def unmapped_digital_peer_voltage_reviews(
    observed: NetlistContract,
    analysis: DigitalPeerVoltageAnalysis | None = None,
) -> tuple[DigitalPeerVoltageReview, ...]:
    """Return grouped voltage-domain review hints."""
    return scan_digital_peer_voltage_reviews(observed, analysis).reviews


def unmapped_spi_peer_voltage_reviews(
    observed: NetlistContract,
    analysis: DigitalPeerVoltageAnalysis | None = None,
) -> tuple[DigitalPeerVoltageReview, ...]:
    """Return only SPI findings from the shared digital-peer analyzer."""
    return tuple(
        item
        for item in scan_digital_peer_voltage_reviews(observed, analysis).reviews
        if item.interface == "SPI"
    )


def unmapped_serial_peer_voltage_reviews(
    observed: NetlistContract,
    analysis: DigitalPeerVoltageAnalysis | None = None,
) -> tuple[DigitalPeerVoltageReview, ...]:
    """Return UART-like findings from the shared digital-peer analyzer."""
    return tuple(
        item
        for item in scan_digital_peer_voltage_reviews(observed, analysis).reviews
        if item.interface == "serial"
    )


def format_nominal_voltage(voltage_v: Decimal) -> str:
    """Format a parsed label value without insignificant trailing zeroes."""
    return f"{format(voltage_v.normalize(), 'f')} V"
