"""Scan mapped digital peers and assemble voltage-domain review hints."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from itertools import combinations
from typing import Literal

from .digital_peer_voltage_analysis import (
    IC_REFERENCE,
    INPUT_TYPES,
    OUTPUT_TYPES,
    fully_mapped_link,
    interface_and_role,
    nominal_voltage_from_net_name,
    pin_assignment_index,
    unambiguous_voltage_named_supply,
)
from .digital_peer_voltage_models import DigitalPeerVoltageAnalysis
from .digital_peer_voltage_types import (
    DigitalPeerLink,
    DigitalPeerVoltageCoverage,
    DigitalPeerVoltageReview,
    DigitalPeerVoltageScan,
    VoltageNamedRail,
)
from .models import NetlistContract
from .return_nets import is_return_like_net_name


@dataclass
class _PeerGroup:
    interface: Literal["SPI", "serial"]
    output_rail: VoltageNamedRail
    input_rail: VoltageNamedRail
    links: set[DigitalPeerLink] = field(default_factory=lambda: set[DigitalPeerLink]())


def scan_digital_peer_voltage_reviews(
    observed: NetlistContract,
    analysis: DigitalPeerVoltageAnalysis | None = None,
) -> DigitalPeerVoltageScan:
    """Find voltage-domain hints and count the supported scope examined.

    The rail parser supplies a review clue only. It deliberately skips missing
    pin-type inventories, ambiguous supplies, unconnected supplies, unsupported
    signal functions, open-drain electrical types, and fully mapped peer links.
    """
    pin_nets, references, symbols = pin_assignment_index(observed)
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
            or not IC_REFERENCE.fullmatch(canonical_reference)
            or reference_key in dnp
        ):
            continue
        recognized = interface_and_role(raw_function)
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
            OUTPUT_TYPES | INPUT_TYPES
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
        if is_return_like_net_name(net) or nominal_voltage_from_net_name(net) is not None:
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
            left_can_output = left_type in OUTPUT_TYPES and (
                interface == "SPI" or left_role == "tx"
            )
            right_can_output = right_type in OUTPUT_TYPES and (
                interface == "SPI" or right_role == "tx"
            )
            left_can_input = left_type in INPUT_TYPES and (interface == "SPI" or left_role == "rx")
            right_can_input = right_type in INPUT_TYPES and (
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
                rails[link.output_reference] = unambiguous_voltage_named_supply(
                    link.output_reference, observed, pin_nets
                )
            if link.input_reference not in rails:
                rails[link.input_reference] = unambiguous_voltage_named_supply(
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
            if fully_mapped_link(link, analysis, observed, pin_nets, references, symbols):
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
