"""Find generic connector contacts assigned to a recognized CANH/CANL pair."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from collections.abc import Set as AbstractSet

from .bus_signal_roles import can_function_role
from .can_generic_connector_models import (
    CanGenericConnectorPair,
    CanGenericEndpointPair,
)
from .casefold_mapping_lookup import casefolded_unique_index
from .connector_contact_evidence import collect_other_connector_contacts
from .connector_coverage import source_matched_connector_pin_evidence
from .connector_coverage_models import (
    ConnectorCoverageReport,
    ConnectorMappedPinEvidence,
)
from .connector_identity import connector_candidate_references, pin_function_is_generic
from .connector_pin_metadata import connector_pin_metadata_matches_inventory
from .netlist_contract_models import ComponentContract, NetlistContract

_IC_REFERENCE = re.compile(r"^(?:U|IC)[0-9]+$", re.IGNORECASE)


def generic_can_connector_pairs(
    observed: NetlistContract,
    reviewed_connector_references: tuple[str, ...] = (),
    connector_coverage: ConnectorCoverageReport | None = None,
) -> tuple[CanGenericConnectorPair, ...]:
    """Identify complete generic connector pin groups on exact CANH/CANL nets.

    Native pin functions establish the CAN endpoint pair. Generic connector
    functions only establish a reason to review the connector pinout; this
    predicate does not infer that the connector is part of the CAN interface.
    """
    assignments: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            assignments.setdefault(pin.casefold(), set()).add(net)

    symbols = casefolded_unique_index(observed.component_symbols)
    reference_spellings = casefolded_unique_index(
        {reference: reference for reference in observed.component_symbols}
    )
    components = casefolded_unique_index(observed.components)
    inventories = casefolded_unique_index(observed.component_pin_numbers)
    functions = casefolded_unique_index(observed.pin_functions)
    electrical_types = casefolded_unique_index(observed.pin_electrical_types)
    dnp = {reference.casefold() for reference in observed.dnp_components}
    connectors = connector_candidate_references(observed, reviewed_connector_references)
    mapped = source_matched_connector_pin_evidence(observed, connector_coverage)
    mapped_by_pin = {pin.casefold(): evidence for pin, evidence in mapped.items()}
    not_applicable = {
        entry.reference.casefold()
        for entry in (() if connector_coverage is None else connector_coverage.entries)
        if entry.status == "NOT_APPLICABLE"
    }

    endpoint_pairs = _recognized_can_endpoint_pairs(
        symbols=symbols,
        components=components,
        inventories=inventories,
        functions=functions,
        electrical_types=electrical_types,
        assignments=assignments,
        dnp=dnp,
        reference_spellings=reference_spellings,
    )
    by_bus: dict[tuple[str, str], list[CanGenericEndpointPair]] = {}
    for endpoint in endpoint_pairs:
        by_bus.setdefault((endpoint.canh_net.casefold(), endpoint.canl_net.casefold()), []).append(
            endpoint
        )

    findings: list[CanGenericConnectorPair] = []
    for connector_reference in connectors:
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
            functions.get(f"{connector_reference}.{number}".casefold()) for number in numbers
        )
        connector_types = tuple(
            electrical_types.get(f"{connector_reference}.{number}".casefold()) for number in numbers
        )
        if any(function is None for function in connector_functions) or any(
            pin_type is None for pin_type in connector_types
        ):
            continue

        for (canh_net_key, canl_net_key), endpoints in sorted(by_bus.items()):
            canh_net = endpoints[0].canh_net
            canl_net = endpoints[0].canl_net
            canh_assignments: list[tuple[str, str]] = []
            canl_assignments: list[tuple[str, str]] = []
            ambiguous = False
            for number, function in zip(numbers, connector_functions, strict=True):
                pin = f"{connector_reference}.{number}"
                nets = assignments.get(pin.casefold(), set())
                if len(nets) > 1:
                    ambiguous = True
                    break
                if len(nets) != 1 or not pin_function_is_generic(function):
                    continue
                assigned_net = next(iter(nets))
                if assigned_net.casefold() == canh_net_key:
                    canh_assignments.append((pin, function or ""))
                elif assigned_net.casefold() == canl_net_key:
                    canl_assignments.append((pin, function or ""))

            if ambiguous or not canh_assignments or not canl_assignments:
                continue
            if _source_map_covers_pair(
                canh_assignments,
                canh_net,
                "CANH",
                mapped_by_pin,
            ) and _source_map_covers_pair(
                canl_assignments,
                canl_net,
                "CANL",
                mapped_by_pin,
            ):
                continue
            other_contacts = collect_other_connector_contacts(
                connector_reference,
                numbers,
                connector_functions,
                assignments,
                (pin for pin, _function in (*canh_assignments, *canl_assignments)),
            )
            findings.append(
                CanGenericConnectorPair(
                    connector_reference=connector_reference,
                    connector_pin_count=len(numbers),
                    canh_connector_pins=_ordered(item[0] for item in canh_assignments),
                    canh_connector_functions=_functions_for(canh_assignments),
                    canh_net=canh_net,
                    canl_connector_pins=_ordered(item[0] for item in canl_assignments),
                    canl_connector_functions=_functions_for(canl_assignments),
                    canl_net=canl_net,
                    endpoint_pairs=tuple(
                        sorted(
                            endpoints, key=lambda item: (item.reference.casefold(), item.reference)
                        )
                    ),
                    other_connector_contacts=other_contacts,
                )
            )

    return tuple(
        sorted(
            findings,
            key=lambda item: (
                item.connector_reference.casefold(),
                item.connector_reference,
                item.canh_net.casefold(),
                item.canl_net.casefold(),
            ),
        )
    )


def _recognized_can_endpoint_pairs(
    *,
    symbols: Mapping[str, str],
    components: Mapping[str, ComponentContract],
    inventories: Mapping[str, tuple[str, ...]],
    functions: Mapping[str, str],
    electrical_types: Mapping[str, str],
    assignments: Mapping[str, AbstractSet[str]],
    dnp: AbstractSet[str],
    reference_spellings: Mapping[str, str],
) -> tuple[CanGenericEndpointPair, ...]:
    endpoint_pairs: list[CanGenericEndpointPair] = []
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
        by_role: dict[str, list[tuple[str, str]]] = {"CANH": [], "CANL": []}
        for number in numbers:
            pin = f"{reference}.{number}"
            function = functions[pin.casefold()]
            role = can_function_role(function)
            if role is None:
                continue
            nets = assignments.get(pin.casefold(), set())
            if len(nets) != 1:
                continue
            by_role[role].append((pin, next(iter(nets))))
        if len(by_role["CANH"]) != 1 or len(by_role["CANL"]) != 1:
            continue
        canh_pin, canh_net = by_role["CANH"][0]
        canl_pin, canl_net = by_role["CANL"][0]
        if canh_net.casefold() == canl_net.casefold():
            continue
        endpoint_pairs.append(
            CanGenericEndpointPair(
                reference=reference,
                canh_pin=canh_pin,
                canh_net=canh_net,
                canl_pin=canl_pin,
                canl_net=canl_net,
            )
        )
    return tuple(endpoint_pairs)


def _source_map_covers_pair(
    assignments: Sequence[tuple[str, str]],
    expected_net: str,
    expected_role: str,
    mapped: Mapping[str, ConnectorMappedPinEvidence],
) -> bool:
    for pin, _function in assignments:
        evidence = mapped.get(pin.casefold())
        if evidence is None:
            return False
        if can_function_role(evidence.interface_signal) != expected_role:
            return False
        if tuple(net.casefold() for net in evidence.nets) != (expected_net.casefold(),):
            return False
    return bool(assignments)


def _ordered(pins: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted(pins, key=lambda item: (item.casefold(), item)))


def _functions_for(assignments: Iterable[tuple[str, str]]) -> tuple[str, ...]:
    by_pin = {pin.casefold(): function for pin, function in assignments}
    return tuple(by_pin[pin.casefold()] for pin in _ordered(by_pin))
