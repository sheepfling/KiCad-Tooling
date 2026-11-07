"""Find generic connector contacts assigned to a native SWD endpoint pair."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from collections.abc import Set as AbstractSet

from .casefold_mapping_lookup import casefolded_unique_index
from .connector_coverage import source_matched_connector_pin_evidence
from .connector_coverage_models import ConnectorCoverageReport, ConnectorMappedPinEvidence
from .connector_identity import connector_candidate_references, pin_function_is_generic
from .connector_pin_metadata import connector_pin_metadata_matches_inventory
from .netlist_contract_models import ComponentContract, NetlistContract
from .netlist_pin_assignments import netlist_pin_net_index
from .swd_generic_connector_models import SwdDebugEndpoint, SwdGenericConnector

_IC_REFERENCE = re.compile(r"^(?:U|IC)[0-9]+$", re.IGNORECASE)
_FUNCTION_TOKENS = re.compile(r"[A-Z0-9]+", re.IGNORECASE)


def swd_function_role(function: str) -> str | None:
    """Return a bounded native SWD role, including the pre-rename SWDCLK alias."""
    tokens = {token.casefold() for token in _FUNCTION_TOKENS.findall(function)}
    roles: set[str] = set()
    if "swdio" in tokens:
        roles.add("swdio")
    if tokens & {"swclk", "swdclk"}:
        roles.add("swclk")
    return next(iter(roles)) if len(roles) == 1 else None


def generic_swd_connector_pairs(
    observed: NetlistContract,
    reviewed_connector_references: tuple[str, ...] = (),
    connector_coverage: ConnectorCoverageReport | None = None,
) -> tuple[SwdGenericConnector, ...]:
    """Identify generic connector contacts on both exact SWD endpoint nets.

    Pin functions identify only a possible SWD association. This does not
    establish that a connector is a debug header or that its pinout is correct.
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
    mapped_by_pin = {
        pin.casefold(): evidence
        for pin, evidence in source_matched_connector_pin_evidence(
            observed, connector_coverage
        ).items()
    }
    not_applicable = {
        entry.reference.casefold()
        for entry in (() if connector_coverage is None else connector_coverage.entries)
        if entry.status == "NOT_APPLICABLE"
    }

    endpoints = _recognized_swd_endpoints(
        symbols=symbols,
        reference_spellings=reference_spellings,
        components=components,
        inventories=inventories,
        functions=functions,
        electrical_types=electrical_types,
        assignments=assignments,
        dnp=dnp,
    )
    endpoints_by_nets: dict[tuple[str, str], list[SwdDebugEndpoint]] = {}
    for endpoint in endpoints:
        endpoints_by_nets.setdefault(
            (endpoint.swdio_net.casefold(), endpoint.swclk_net.casefold()), []
        ).append(endpoint)

    findings: list[SwdGenericConnector] = []
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

        for (swdio_key, swclk_key), endpoint_group in sorted(endpoints_by_nets.items()):
            swdio_net = endpoint_group[0].swdio_net
            swclk_net = endpoint_group[0].swclk_net
            swdio_assignments: list[tuple[str, str]] = []
            swclk_assignments: list[tuple[str, str]] = []
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
                if assigned_net.casefold() == swdio_key:
                    swdio_assignments.append((pin, function))
                elif assigned_net.casefold() == swclk_key:
                    swclk_assignments.append((pin, function))

            if ambiguous or not swdio_assignments or not swclk_assignments:
                continue
            if _source_map_covers_role(swdio_assignments, swdio_net, "swdio", mapped_by_pin) and (
                _source_map_covers_role(swclk_assignments, swclk_net, "swclk", mapped_by_pin)
            ):
                continue
            findings.append(
                SwdGenericConnector(
                    connector_reference=connector_reference,
                    connector_pin_count=len(numbers),
                    swdio_connector_pins=_ordered(item[0] for item in swdio_assignments),
                    swdio_connector_functions=_functions_for(swdio_assignments),
                    swdio_net=swdio_net,
                    swclk_connector_pins=_ordered(item[0] for item in swclk_assignments),
                    swclk_connector_functions=_functions_for(swclk_assignments),
                    swclk_net=swclk_net,
                    endpoints=tuple(
                        sorted(
                            endpoint_group,
                            key=lambda item: (item.reference.casefold(), item.reference),
                        )
                    ),
                )
            )

    return tuple(
        sorted(
            findings,
            key=lambda item: (
                item.connector_reference.casefold(),
                item.connector_reference,
                item.swdio_net.casefold(),
                item.swclk_net.casefold(),
            ),
        )
    )


def _recognized_swd_endpoints(
    *,
    symbols: Mapping[str, str],
    reference_spellings: Mapping[str, str],
    components: Mapping[str, ComponentContract],
    inventories: Mapping[str, tuple[str, ...]],
    functions: Mapping[str, str],
    electrical_types: Mapping[str, str],
    assignments: Mapping[str, AbstractSet[str]],
    dnp: AbstractSet[str],
) -> tuple[SwdDebugEndpoint, ...]:
    endpoints: list[SwdDebugEndpoint] = []
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
        by_role: dict[str, list[tuple[str, str, str, AbstractSet[str]]]] = {
            "swdio": [],
            "swclk": [],
        }
        for number in numbers:
            pin = f"{reference}.{number}"
            function = functions[f"{reference_key}.{number.casefold()}"]
            role = swd_function_role(function)
            if role is not None:
                by_role[role].append(
                    (
                        pin,
                        function,
                        electrical_types[f"{reference_key}.{number.casefold()}"],
                        assignments.get(pin.casefold(), frozenset()),
                    )
                )

        if any(len(by_role[role]) != 1 for role in by_role):
            continue
        swdio_pin, swdio_function, swdio_type, swdio_nets = by_role["swdio"][0]
        swclk_pin, swclk_function, swclk_type, swclk_nets = by_role["swclk"][0]
        if len(swdio_nets) != 1 or len(swclk_nets) != 1:
            continue
        swdio_net = next(iter(swdio_nets))
        swclk_net = next(iter(swclk_nets))
        if swdio_net.casefold() == swclk_net.casefold():
            continue
        endpoints.append(
            SwdDebugEndpoint(
                reference=reference,
                swdio_pin=swdio_pin,
                swdio_function=swdio_function,
                swdio_electrical_type=swdio_type,
                swdio_net=swdio_net,
                swclk_pin=swclk_pin,
                swclk_function=swclk_function,
                swclk_electrical_type=swclk_type,
                swclk_net=swclk_net,
            )
        )
    return tuple(endpoints)


def _source_map_covers_role(
    assignments: Sequence[tuple[str, str]],
    expected_net: str,
    role: str,
    mapped: Mapping[str, ConnectorMappedPinEvidence],
) -> bool:
    for pin, _function in assignments:
        evidence = mapped.get(pin.casefold())
        if evidence is None:
            return False
        if swd_function_role(evidence.interface_signal) != role:
            return False
        if tuple(net.casefold() for net in evidence.nets) != (expected_net.casefold(),):
            return False
    return bool(assignments)


def _ordered(pins: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted(pins, key=lambda item: (item.casefold(), item)))


def _functions_for(assignments: Iterable[tuple[str, str]]) -> tuple[str, ...]:
    by_pin = {pin.casefold(): function for pin, function in assignments}
    return tuple(by_pin[pin.casefold()] for pin in _ordered(by_pin))
