"""Find complete generic connectors on recognized I3C SDA/SCL net pairs."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping

from .casefold_mapping_lookup import casefolded_unique_index
from .connector_contact_evidence import collect_other_connector_contacts
from .connector_coverage import source_matched_connector_pin_evidence
from .connector_coverage_models import ConnectorCoverageReport, ConnectorMappedPinEvidence
from .connector_identity import connector_candidate_references, pin_function_is_generic
from .connector_pin_metadata import connector_pin_metadata_matches_inventory
from .i3c_connector_map import I3cSignalRole, i3c_source_map_covers_role
from .i3c_endpoint_pairs import I3cEndpointPair, i3c_endpoint_pairs
from .i3c_generic_connector_models import I3cGenericConnectorPair
from .netlist_contract_models import NetlistContract


def generic_i3c_connector_pairs(
    observed: NetlistContract,
    reviewed_connector_references: tuple[str, ...] = (),
    connector_coverage: ConnectorCoverageReport | None = None,
) -> tuple[I3cGenericConnectorPair, ...]:
    """Find fully inventoried connectors with generic pins on both I3C nets.

    Two-contact connectors are left to the existing missing-return review so
    one connector does not receive duplicate I3C prompts.
    """
    assignments: dict[str, set[str]] = defaultdict(set)
    for net, pins in observed.nets.items():
        for pin in pins:
            assignments[pin.casefold()].add(net)

    symbols = casefolded_unique_index(observed.component_symbols)
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

    by_bus: dict[tuple[str, str], list[I3cEndpointPair]] = defaultdict(list)
    for endpoint in i3c_endpoint_pairs(observed):
        by_bus[endpoint.sda_net.casefold(), endpoint.scl_net.casefold()].append(endpoint)

    findings: list[I3cGenericConnectorPair] = []
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
        if (
            numbers is None
            or len(numbers) <= 2
            or len({number.casefold() for number in numbers}) != len(numbers)
            or not connector_pin_metadata_matches_inventory(
                connector_key, numbers, functions, electrical_types
            )
        ):
            continue
        connector_functions = tuple(
            functions.get(f"{connector_key}.{number.casefold()}") for number in numbers
        )

        for bus_key, endpoints in sorted(by_bus.items()):
            sda_assignments: list[tuple[str, str]] = []
            scl_assignments: list[tuple[str, str]] = []
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
                if assigned_net.casefold() == bus_key[0]:
                    sda_assignments.append((pin, function or ""))
                elif assigned_net.casefold() == bus_key[1]:
                    scl_assignments.append((pin, function or ""))

            if ambiguous or not sda_assignments or not scl_assignments:
                continue
            if _source_map_covers_role(sda_assignments, endpoints, "SDA", mapped_by_pin) and (
                _source_map_covers_role(scl_assignments, endpoints, "SCL", mapped_by_pin)
            ):
                continue

            sda_net = _exact_net_name(endpoints, "SDA")
            scl_net = _exact_net_name(endpoints, "SCL")
            other_contacts = collect_other_connector_contacts(
                connector_reference,
                numbers,
                connector_functions,
                assignments,
                (pin for pin, _function in (*sda_assignments, *scl_assignments)),
            )
            findings.append(
                I3cGenericConnectorPair(
                    connector_reference=connector_reference,
                    connector_pin_count=len(numbers),
                    sda_connector_pins=_ordered(item[0] for item in sda_assignments),
                    sda_connector_functions=_functions_for(sda_assignments),
                    sda_net=sda_net,
                    scl_connector_pins=_ordered(item[0] for item in scl_assignments),
                    scl_connector_functions=_functions_for(scl_assignments),
                    scl_net=scl_net,
                    endpoint_pairs=tuple(_ordered_endpoints(endpoints)),
                    other_connector_contacts=other_contacts,
                )
            )

    return tuple(
        sorted(
            findings,
            key=lambda item: (
                item.connector_reference.casefold(),
                item.connector_reference,
                item.sda_net.casefold(),
                item.sda_net,
                item.scl_net.casefold(),
                item.scl_net,
            ),
        )
    )


def _source_map_covers_role(
    assignments: list[tuple[str, str]],
    endpoints: Iterable[I3cEndpointPair],
    expected_role: I3cSignalRole,
    mapped: Mapping[str, ConnectorMappedPinEvidence],
) -> bool:
    endpoint_nets = {
        (item.sda_net if expected_role == "SDA" else item.scl_net).casefold() for item in endpoints
    }
    if len(endpoint_nets) != 1:
        return False
    expected_net = next(iter(endpoint_nets))
    return bool(assignments) and all(
        i3c_source_map_covers_role(pin, expected_net, expected_role, mapped)
        for pin, _function in assignments
    )


def _exact_net_name(endpoints: Iterable[I3cEndpointPair], role: str) -> str:
    names = {item.sda_net if role == "SDA" else item.scl_net for item in endpoints}
    return min(names, key=lambda item: (item.casefold(), item))


def _ordered_endpoints(
    endpoints: Iterable[I3cEndpointPair],
) -> tuple[I3cEndpointPair, ...]:
    return tuple(
        sorted(
            endpoints,
            key=lambda item: (
                item.reference.casefold(),
                item.reference,
                item.channel is not None,
                item.channel or "",
                item.sda_pin.casefold(),
                item.sda_pin,
                item.scl_pin.casefold(),
                item.scl_pin,
            ),
        )
    )


def _ordered(pins: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted(pins, key=lambda item: (item.casefold(), item)))


def _functions_for(assignments: Iterable[tuple[str, str]]) -> tuple[str, ...]:
    by_pin = {pin.casefold(): function for pin, function in assignments}
    return tuple(by_pin[pin.casefold()] for pin in _ordered(by_pin))
