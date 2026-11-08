"""Find generic connector contacts assigned to recognized Ethernet PHY pairs."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from collections.abc import Set as AbstractSet
from typing import Literal, cast

from .bus_signal_pairs import ethernet_data_pair_function_role
from .casefold_mapping_lookup import casefolded_unique_index
from .connector_contact_evidence import collect_other_connector_contacts
from .connector_coverage import source_matched_connector_pin_evidence
from .connector_coverage_models import (
    ConnectorCoverageReport,
    ConnectorMappedPinEvidence,
)
from .connector_identity import connector_candidate_references, pin_function_is_generic
from .connector_pin_metadata import connector_pin_metadata_matches_inventory
from .ethernet_generic_connector_models import (
    EthernetGenericConnectorPair,
    EthernetGenericEndpointPair,
    EthernetPairDirection,
)
from .netlist_contract_models import ComponentContract, NetlistContract
from .netlist_pin_assignments import netlist_pin_net_index

_IC_REFERENCE = re.compile(r"^(?:U|IC)[0-9]+$", re.IGNORECASE)
EthernetPairSide = Literal["positive", "negative"]
_ETHERNET_PAIR_DIRECTIONS: tuple[EthernetPairDirection, ...] = ("TX", "RX")


def generic_ethernet_connector_pairs(
    observed: NetlistContract,
    reviewed_connector_references: tuple[str, ...] = (),
    connector_coverage: ConnectorCoverageReport | None = None,
) -> tuple[EthernetGenericConnectorPair, ...]:
    """Identify generic contacts on the exact nets of recognized Ethernet PHY pairs.

    Native `TD`/`RD` pin functions establish the bounded endpoint pair. Generic
    connector functions establish only that the pinout merits review; the
    predicate does not infer connector identity or intended wiring.
    """
    symbols = casefolded_unique_index(observed.component_symbols)
    reference_spellings = casefolded_unique_index(
        {reference: reference for reference in observed.component_symbols}
    )
    components = casefolded_unique_index(observed.components)
    inventories = casefolded_unique_index(observed.component_pin_numbers)
    functions = casefolded_unique_index(observed.pin_functions)
    electrical_types = casefolded_unique_index(observed.pin_electrical_types)
    assignments = netlist_pin_net_index(observed)
    dnp = {reference.casefold() for reference in observed.dnp_components}
    mapped = source_matched_connector_pin_evidence(observed, connector_coverage)
    mapped_by_pin = {pin.casefold(): evidence for pin, evidence in mapped.items()}
    not_applicable = {
        entry.reference.casefold()
        for entry in (() if connector_coverage is None else connector_coverage.entries)
        if entry.status == "NOT_APPLICABLE"
    }

    endpoint_pairs = _recognized_ethernet_endpoint_pairs(
        symbols=symbols,
        reference_spellings=reference_spellings,
        components=components,
        inventories=inventories,
        functions=functions,
        electrical_types=electrical_types,
        assignments=assignments,
        dnp=dnp,
    )
    by_pair: dict[tuple[EthernetPairDirection, str, str], list[EthernetGenericEndpointPair]] = {}
    for endpoint in endpoint_pairs:
        by_pair.setdefault(
            (
                endpoint.direction,
                endpoint.positive_net.casefold(),
                endpoint.negative_net.casefold(),
            ),
            [],
        ).append(endpoint)

    findings: list[EthernetGenericConnectorPair] = []
    for connector_reference in connector_candidate_references(
        observed, reviewed_connector_references
    ):
        connector_key = connector_reference.casefold()
        if (
            connector_key in dnp
            or connector_key in not_applicable
            or connector_key not in symbols
            or connector_key not in components
        ):
            continue
        numbers = inventories.get(connector_key)
        if not numbers or len({number.casefold() for number in numbers}) != len(numbers):
            continue
        if not connector_pin_metadata_matches_inventory(
            connector_key, numbers, functions, electrical_types
        ):
            continue
        connector_functions = tuple(
            functions[f"{connector_key}.{number.casefold()}"] for number in numbers
        )

        for (direction, positive_key, negative_key), endpoints in sorted(by_pair.items()):
            positive_net = endpoints[0].positive_net
            negative_net = endpoints[0].negative_net
            positive_assignments: list[tuple[str, str]] = []
            negative_assignments: list[tuple[str, str]] = []
            ambiguous = False
            for number, function in zip(numbers, connector_functions, strict=True):
                pin = f"{connector_reference}.{number}"
                nets = assignments.get(pin.casefold(), frozenset())
                if len(nets) > 1:
                    ambiguous = True
                    break
                if len(nets) != 1 or not pin_function_is_generic(function):
                    continue
                assigned_net = next(iter(nets))
                if assigned_net.casefold() == positive_key:
                    positive_assignments.append((pin, function))
                elif assigned_net.casefold() == negative_key:
                    negative_assignments.append((pin, function))

            if ambiguous or not positive_assignments or not negative_assignments:
                continue
            if _source_map_covers_side(
                positive_assignments, positive_net, direction, "positive", mapped_by_pin
            ) and _source_map_covers_side(
                negative_assignments, negative_net, direction, "negative", mapped_by_pin
            ):
                continue
            findings.append(
                EthernetGenericConnectorPair(
                    connector_reference=connector_reference,
                    connector_pin_count=len(numbers),
                    direction=direction,
                    positive_connector_pins=_ordered(item[0] for item in positive_assignments),
                    positive_connector_functions=_functions_for(positive_assignments),
                    positive_net=positive_net,
                    negative_connector_pins=_ordered(item[0] for item in negative_assignments),
                    negative_connector_functions=_functions_for(negative_assignments),
                    negative_net=negative_net,
                    endpoint_pairs=tuple(
                        sorted(
                            endpoints,
                            key=lambda item: (item.reference.casefold(), item.reference),
                        )
                    ),
                    other_connector_contacts=collect_other_connector_contacts(
                        connector_reference,
                        numbers,
                        connector_functions,
                        assignments,
                        (
                            pin
                            for pin, _function in (
                                *positive_assignments,
                                *negative_assignments,
                            )
                        ),
                    ),
                )
            )

    return tuple(
        sorted(
            findings,
            key=lambda item: (
                item.connector_reference.casefold(),
                item.connector_reference,
                item.direction,
                item.positive_net.casefold(),
                item.negative_net.casefold(),
            ),
        )
    )


def _recognized_ethernet_endpoint_pairs(
    *,
    symbols: Mapping[str, str],
    reference_spellings: Mapping[str, str],
    components: Mapping[str, ComponentContract],
    inventories: Mapping[str, tuple[str, ...]],
    functions: Mapping[str, str],
    electrical_types: Mapping[str, str],
    assignments: Mapping[str, AbstractSet[str]],
    dnp: AbstractSet[str],
) -> tuple[EthernetGenericEndpointPair, ...]:
    pairs: list[EthernetGenericEndpointPair] = []
    for reference_key in sorted(symbols):
        reference = reference_spellings.get(reference_key)
        if (
            reference is None
            or not _IC_REFERENCE.fullmatch(reference)
            or reference_key in dnp
            or reference_key not in components
        ):
            continue
        numbers = inventories.get(reference_key)
        if not numbers or len({number.casefold() for number in numbers}) != len(numbers):
            continue
        if not connector_pin_metadata_matches_inventory(
            reference_key, numbers, functions, electrical_types
        ):
            continue
        by_role: dict[
            tuple[EthernetPairDirection, EthernetPairSide], list[tuple[str, AbstractSet[str]]]
        ] = {}
        for number in numbers:
            pin = f"{reference}.{number}"
            function = functions[f"{reference_key}.{number.casefold()}"]
            role = ethernet_data_pair_function_role(function)
            if role is None:
                continue
            direction = cast(EthernetPairDirection, role[0])
            side = cast(EthernetPairSide, role[1])
            assigned_nets = assignments.get(pin.casefold(), frozenset())
            by_role.setdefault((direction, side), []).append((pin, assigned_nets))

        for direction in _ETHERNET_PAIR_DIRECTIONS:
            positive = by_role.get((direction, "positive"), ())
            negative = by_role.get((direction, "negative"), ())
            if len(positive) != 1 or len(negative) != 1:
                continue
            positive_pin, positive_nets = positive[0]
            negative_pin, negative_nets = negative[0]
            if len(positive_nets) != 1 or len(negative_nets) != 1:
                continue
            positive_net = next(iter(positive_nets))
            negative_net = next(iter(negative_nets))
            if positive_net.casefold() == negative_net.casefold():
                continue
            pairs.append(
                EthernetGenericEndpointPair(
                    reference=reference,
                    direction=direction,
                    positive_pin=positive_pin,
                    positive_net=positive_net,
                    negative_pin=negative_pin,
                    negative_net=negative_net,
                )
            )
    return tuple(pairs)


def _source_map_covers_side(
    assignments: Sequence[tuple[str, str]],
    expected_net: str,
    direction: EthernetPairDirection,
    side: EthernetPairSide,
    mapped: Mapping[str, ConnectorMappedPinEvidence],
) -> bool:
    for pin, _function in assignments:
        evidence = mapped.get(pin.casefold())
        if evidence is None:
            return False
        if ethernet_data_pair_function_role(evidence.interface_signal) != (direction, side):
            return False
        if tuple(net.casefold() for net in evidence.nets) != (expected_net.casefold(),):
            return False
    return bool(assignments)


def _ordered(pins: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted(pins, key=lambda item: (item.casefold(), item)))


def _functions_for(assignments: Iterable[tuple[str, str]]) -> tuple[str, ...]:
    by_pin = {pin.casefold(): function for pin, function in assignments}
    return tuple(by_pin[pin.casefold()] for pin in _ordered(by_pin))
