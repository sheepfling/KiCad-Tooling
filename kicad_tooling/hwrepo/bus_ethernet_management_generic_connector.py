"""Find generic connector contacts assigned to Ethernet MDC/MDIO endpoints."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from collections.abc import Set as AbstractSet

from .bus_signal_pairs import ethernet_management_function_role
from .casefold_mapping_lookup import casefolded_unique_index
from .connector_contact_evidence import collect_other_connector_contacts
from .connector_coverage import source_matched_connector_pin_evidence
from .connector_coverage_models import ConnectorCoverageReport, ConnectorMappedPinEvidence
from .connector_identity import connector_candidate_references, pin_function_is_generic
from .connector_pin_metadata import connector_pin_metadata_matches_inventory
from .ethernet_management_generic_connector_models import (
    EthernetManagementEndpoint,
    EthernetManagementGenericConnector,
)
from .netlist_contract_models import ComponentContract, NetlistContract
from .netlist_pin_assignments import netlist_pin_net_index

_IC_REFERENCE = re.compile(r"^(?:U|IC)[0-9]+$", re.IGNORECASE)
_MANAGEMENT_ROLES = ("clock", "data")


def generic_ethernet_management_connector_pairs(
    observed: NetlistContract,
    reviewed_connector_references: tuple[str, ...] = (),
    connector_coverage: ConnectorCoverageReport | None = None,
) -> tuple[EthernetManagementGenericConnector, ...]:
    """Identify generic connector contacts on both native MDC/MDIO endpoint nets.

    Native endpoint pin functions establish the bounded management interface.
    The connector prompt asks for review and does not infer its purpose.
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

    endpoints = _recognized_ethernet_management_endpoints(
        symbols=symbols,
        reference_spellings=reference_spellings,
        components=components,
        inventories=inventories,
        functions=functions,
        electrical_types=electrical_types,
        assignments=assignments,
        dnp=dnp,
    )
    endpoints_by_nets: dict[tuple[str, str], list[EthernetManagementEndpoint]] = {}
    for endpoint in endpoints:
        endpoints_by_nets.setdefault(
            (endpoint.mdc_net.casefold(), endpoint.mdio_net.casefold()), []
        ).append(endpoint)

    findings: list[EthernetManagementGenericConnector] = []
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

        for (mdc_key, mdio_key), endpoint_group in sorted(endpoints_by_nets.items()):
            mdc_net = endpoint_group[0].mdc_net
            mdio_net = endpoint_group[0].mdio_net
            mdc_assignments: list[tuple[str, str]] = []
            mdio_assignments: list[tuple[str, str]] = []
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
                if assigned_net.casefold() == mdc_key:
                    mdc_assignments.append((pin, function))
                elif assigned_net.casefold() == mdio_key:
                    mdio_assignments.append((pin, function))

            if ambiguous or not mdc_assignments or not mdio_assignments:
                continue
            if _source_map_covers_role(mdc_assignments, mdc_net, "clock", mapped_by_pin) and (
                _source_map_covers_role(mdio_assignments, mdio_net, "data", mapped_by_pin)
            ):
                continue
            findings.append(
                EthernetManagementGenericConnector(
                    connector_reference=connector_reference,
                    connector_pin_count=len(numbers),
                    mdc_connector_pins=_ordered(item[0] for item in mdc_assignments),
                    mdc_connector_functions=_functions_for(mdc_assignments),
                    mdc_net=mdc_net,
                    mdio_connector_pins=_ordered(item[0] for item in mdio_assignments),
                    mdio_connector_functions=_functions_for(mdio_assignments),
                    mdio_net=mdio_net,
                    endpoint_pairs=tuple(
                        sorted(
                            endpoint_group,
                            key=lambda item: (item.reference.casefold(), item.reference),
                        )
                    ),
                    other_connector_contacts=collect_other_connector_contacts(
                        connector_reference,
                        numbers,
                        connector_functions,
                        assignments,
                        (pin for pin, _function in (*mdc_assignments, *mdio_assignments)),
                    ),
                )
            )

    return tuple(
        sorted(
            findings,
            key=lambda item: (
                item.connector_reference.casefold(),
                item.connector_reference,
                item.mdc_net.casefold(),
                item.mdio_net.casefold(),
            ),
        )
    )


def _recognized_ethernet_management_endpoints(
    *,
    symbols: Mapping[str, str],
    reference_spellings: Mapping[str, str],
    components: Mapping[str, ComponentContract],
    inventories: Mapping[str, tuple[str, ...]],
    functions: Mapping[str, str],
    electrical_types: Mapping[str, str],
    assignments: Mapping[str, AbstractSet[str]],
    dnp: AbstractSet[str],
) -> tuple[EthernetManagementEndpoint, ...]:
    endpoints: list[EthernetManagementEndpoint] = []
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
        by_role: dict[str, list[tuple[str, AbstractSet[str]]]] = {
            role: [] for role in _MANAGEMENT_ROLES
        }
        for number in numbers:
            pin = f"{reference}.{number}"
            role = ethernet_management_function_role(
                functions[f"{reference_key}.{number.casefold()}"]
            )
            if role is not None:
                by_role[role].append((pin, assignments.get(pin.casefold(), frozenset())))

        if any(len(by_role[role]) != 1 for role in _MANAGEMENT_ROLES):
            continue
        mdc_pin, mdc_nets = by_role["clock"][0]
        mdio_pin, mdio_nets = by_role["data"][0]
        if len(mdc_nets) != 1 or len(mdio_nets) != 1:
            continue
        mdc_net = next(iter(mdc_nets))
        mdio_net = next(iter(mdio_nets))
        if mdc_net.casefold() == mdio_net.casefold():
            continue
        endpoints.append(
            EthernetManagementEndpoint(
                reference=reference,
                mdc_pin=mdc_pin,
                mdc_net=mdc_net,
                mdio_pin=mdio_pin,
                mdio_net=mdio_net,
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
        if ethernet_management_function_role(evidence.interface_signal) != role:
            return False
        if tuple(net.casefold() for net in evidence.nets) != (expected_net.casefold(),):
            return False
    return bool(assignments)


def _ordered(pins: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted(pins, key=lambda item: (item.casefold(), item)))


def _functions_for(assignments: Iterable[tuple[str, str]]) -> tuple[str, ...]:
    by_pin = {pin.casefold(): function for pin, function in assignments}
    return tuple(by_pin[pin.casefold()] for pin in _ordered(by_pin))
