"""Find generic connector contacts on the TCK/TMS nets of fitted ICs."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from collections.abc import Set as AbstractSet

from .casefold_mapping_lookup import casefolded_unique_index
from .connector_coverage import source_matched_connector_pin_evidence
from .connector_coverage_models import ConnectorCoverageReport, ConnectorMappedPinEvidence
from .connector_identity import connector_candidate_references, pin_function_is_generic
from .connector_pin_metadata import connector_pin_metadata_matches_inventory
from .jtag_generic_connector_models import JtagDebugEndpoint, JtagGenericConnector
from .netlist_contract_models import ComponentContract, NetlistContract
from .netlist_pin_assignments import netlist_pin_net_index

_IC_REFERENCE = re.compile(r"^(?:U|IC)[0-9]+$", re.IGNORECASE)
_FUNCTION_TOKENS = re.compile(r"[A-Z0-9]+", re.IGNORECASE)


def jtag_function_role(function: str) -> str | None:
    """Recognize only explicit TCK/TMS tokens; JTCK/JTMS can also describe SWD."""
    tokens = {token.casefold() for token in _FUNCTION_TOKENS.findall(function)}
    roles = {role for role in ("tck", "tms") if role in tokens}
    return next(iter(roles)) if len(roles) == 1 else None


def generic_jtag_connector_pairs(
    observed: NetlistContract,
    reviewed_connector_references: tuple[str, ...] = (),
    connector_coverage: ConnectorCoverageReport | None = None,
) -> tuple[JtagGenericConnector, ...]:
    """Identify generic connector contacts on both exact native TCK/TMS nets.

    Native pin functions and exact net assignments identify only a possible
    JTAG association. They do not establish connector purpose or pinout.
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

    endpoints = _recognized_jtag_endpoints(
        symbols=symbols,
        reference_spellings=reference_spellings,
        components=components,
        inventories=inventories,
        functions=functions,
        electrical_types=electrical_types,
        assignments=assignments,
        dnp=dnp,
    )
    endpoints_by_nets: dict[tuple[str, str], list[JtagDebugEndpoint]] = {}
    for endpoint in endpoints:
        endpoints_by_nets.setdefault(
            (endpoint.tck_net.casefold(), endpoint.tms_net.casefold()), []
        ).append(endpoint)

    findings: list[JtagGenericConnector] = []
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

        for (tck_key, tms_key), endpoint_group in sorted(endpoints_by_nets.items()):
            tck_net = endpoint_group[0].tck_net
            tms_net = endpoint_group[0].tms_net
            tck_assignments: list[tuple[str, str]] = []
            tms_assignments: list[tuple[str, str]] = []
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
                if assigned_net.casefold() == tck_key:
                    tck_assignments.append((pin, function))
                elif assigned_net.casefold() == tms_key:
                    tms_assignments.append((pin, function))

            if ambiguous or not tck_assignments or not tms_assignments:
                continue
            if _source_map_covers_role(tck_assignments, tck_net, "tck", mapped_by_pin) and (
                _source_map_covers_role(tms_assignments, tms_net, "tms", mapped_by_pin)
            ):
                continue
            findings.append(
                JtagGenericConnector(
                    connector_reference=connector_reference,
                    connector_pin_count=len(numbers),
                    tck_connector_pins=_ordered(item[0] for item in tck_assignments),
                    tck_connector_functions=_functions_for(tck_assignments),
                    tck_net=tck_net,
                    tms_connector_pins=_ordered(item[0] for item in tms_assignments),
                    tms_connector_functions=_functions_for(tms_assignments),
                    tms_net=tms_net,
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
                item.tck_net.casefold(),
                item.tms_net.casefold(),
            ),
        )
    )


def _recognized_jtag_endpoints(
    *,
    symbols: Mapping[str, str],
    reference_spellings: Mapping[str, str],
    components: Mapping[str, ComponentContract],
    inventories: Mapping[str, tuple[str, ...]],
    functions: Mapping[str, str],
    electrical_types: Mapping[str, str],
    assignments: Mapping[str, AbstractSet[str]],
    dnp: AbstractSet[str],
) -> tuple[JtagDebugEndpoint, ...]:
    endpoints: list[JtagDebugEndpoint] = []
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
            "tck": [],
            "tms": [],
        }
        for number in numbers:
            pin = f"{reference}.{number}"
            key = f"{reference_key}.{number.casefold()}"
            role = jtag_function_role(functions[key])
            if role is not None:
                by_role[role].append(
                    (
                        pin,
                        functions[key],
                        electrical_types[key],
                        assignments.get(pin.casefold(), frozenset()),
                    )
                )

        if any(len(by_role[role]) != 1 for role in by_role):
            continue
        tck_pin, tck_function, tck_type, tck_nets = by_role["tck"][0]
        tms_pin, tms_function, tms_type, tms_nets = by_role["tms"][0]
        if len(tck_nets) != 1 or len(tms_nets) != 1:
            continue
        tck_net = next(iter(tck_nets))
        tms_net = next(iter(tms_nets))
        if tck_net.casefold() == tms_net.casefold():
            continue
        endpoints.append(
            JtagDebugEndpoint(
                reference=reference,
                tck_pin=tck_pin,
                tck_function=tck_function,
                tck_electrical_type=tck_type,
                tck_net=tck_net,
                tms_pin=tms_pin,
                tms_function=tms_function,
                tms_electrical_type=tms_type,
                tms_net=tms_net,
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
        if jtag_function_role(evidence.interface_signal) != role:
            return False
        if tuple(net.casefold() for net in evidence.nets) != (expected_net.casefold(),):
            return False
    return bool(assignments)


def _ordered(pins: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted(pins, key=lambda item: (item.casefold(), item)))


def _functions_for(assignments: Iterable[tuple[str, str]]) -> tuple[str, ...]:
    by_pin = {pin.casefold(): function for pin, function in assignments}
    return tuple(by_pin[pin.casefold()] for pin in _ordered(by_pin))
