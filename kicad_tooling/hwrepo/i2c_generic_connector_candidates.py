"""Find generic connector contacts assigned to recognized I2C line pairs."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from collections.abc import Set as AbstractSet

from .bus_signal_roles import i2c_signal_role
from .casefold_mapping_lookup import casefolded_unique_index
from .connector_coverage import source_matched_connector_pin_evidence
from .connector_coverage_models import (
    ConnectorCoverageReport,
    ConnectorMappedPinEvidence,
)
from .connector_identity import connector_candidate_references, pin_function_is_generic
from .i2c_generic_connector_models import I2cGenericConnectorPair, I2cGenericEndpointPair
from .netlist_contract_models import ComponentContract, NetlistContract

_IC_REFERENCE = re.compile(r"^(?:U|IC)[0-9]+$", re.IGNORECASE)


def generic_i2c_connector_pairs(
    observed: NetlistContract,
    reviewed_connector_references: tuple[str, ...] = (),
    connector_coverage: ConnectorCoverageReport | None = None,
) -> tuple[I2cGenericConnectorPair, ...]:
    """Identify complete generic connector groups on exact native SDA/SCL nets.

    Native I2C function pins establish the observed line pair. Generic pin
    functions establish only that the connector pinout merits review; the
    predicate does not infer connector identity or intended wiring.
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

    endpoints = _recognized_i2c_endpoint_pairs(
        symbols=symbols,
        reference_spellings=reference_spellings,
        components=components,
        inventories=inventories,
        functions=functions,
        electrical_types=electrical_types,
        assignments=assignments,
        dnp=dnp,
    )
    by_bus: dict[tuple[str, str], list[I2cGenericEndpointPair]] = {}
    for endpoint in endpoints:
        by_bus.setdefault((endpoint.sda_net.casefold(), endpoint.scl_net.casefold()), []).append(
            endpoint
        )

    findings: list[I2cGenericConnectorPair] = []
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
        if not _metadata_matches_inventory(connector_key, numbers, functions, electrical_types):
            continue
        connector_functions = tuple(
            functions.get(f"{connector_key}.{number.casefold()}") for number in numbers
        )

        for (sda_net_key, scl_net_key), bus_endpoints in sorted(by_bus.items()):
            sda_net = bus_endpoints[0].sda_net
            scl_net = bus_endpoints[0].scl_net
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
                if assigned_net.casefold() == sda_net_key:
                    sda_assignments.append((pin, function or ""))
                elif assigned_net.casefold() == scl_net_key:
                    scl_assignments.append((pin, function or ""))

            if ambiguous or not sda_assignments or not scl_assignments:
                continue
            if _source_map_covers_role(sda_assignments, sda_net, "SDA", mapped_by_pin) and (
                _source_map_covers_role(scl_assignments, scl_net, "SCL", mapped_by_pin)
            ):
                continue
            findings.append(
                I2cGenericConnectorPair(
                    connector_reference=connector_reference,
                    connector_pin_count=len(numbers),
                    sda_connector_pins=_ordered(item[0] for item in sda_assignments),
                    sda_connector_functions=_functions_for(sda_assignments),
                    sda_net=sda_net,
                    scl_connector_pins=_ordered(item[0] for item in scl_assignments),
                    scl_connector_functions=_functions_for(scl_assignments),
                    scl_net=scl_net,
                    endpoint_pairs=tuple(
                        sorted(
                            bus_endpoints,
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
                item.sda_net.casefold(),
                item.scl_net.casefold(),
            ),
        )
    )


def _recognized_i2c_endpoint_pairs(
    *,
    symbols: Mapping[str, str],
    reference_spellings: Mapping[str, str],
    components: Mapping[str, ComponentContract],
    inventories: Mapping[str, tuple[str, ...]],
    functions: Mapping[str, str],
    electrical_types: Mapping[str, str],
    assignments: Mapping[str, AbstractSet[str]],
    dnp: AbstractSet[str],
) -> tuple[I2cGenericEndpointPair, ...]:
    endpoints: list[I2cGenericEndpointPair] = []
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
        if not _metadata_matches_inventory(reference_key, numbers, functions, electrical_types):
            continue
        by_role: dict[str, list[str]] = {"SDA": [], "SCL": []}
        for number in numbers:
            pin = f"{reference}.{number}"
            function = functions[f"{reference_key}.{number.casefold()}"]
            role = i2c_signal_role(function)
            if role is not None:
                by_role[role].append(pin)
        if len(by_role["SDA"]) != 1 or len(by_role["SCL"]) != 1:
            continue
        sda_pin = by_role["SDA"][0]
        scl_pin = by_role["SCL"][0]
        sda_nets = assignments.get(sda_pin.casefold(), set())
        scl_nets = assignments.get(scl_pin.casefold(), set())
        if len(sda_nets) != 1 or len(scl_nets) != 1:
            continue
        sda_net = next(iter(sda_nets))
        scl_net = next(iter(scl_nets))
        if sda_net.casefold() == scl_net.casefold():
            continue
        endpoints.append(
            I2cGenericEndpointPair(
                reference=reference,
                sda_pin=sda_pin,
                sda_net=sda_net,
                scl_pin=scl_pin,
                scl_net=scl_net,
            )
        )
    return tuple(endpoints)


def _metadata_matches_inventory(
    reference_key: str,
    numbers: tuple[str, ...],
    functions: Mapping[str, str],
    electrical_types: Mapping[str, str],
) -> bool:
    expected = {number.casefold() for number in numbers}
    for metadata in (functions, electrical_types):
        actual = {
            pin.rsplit(".", 1)[1].casefold()
            for pin in metadata
            if pin.rpartition(".")[0].casefold() == reference_key
        }
        if actual != expected:
            return False
    return all(
        functions.get(f"{reference_key}.{number.casefold()}")
        and electrical_types.get(f"{reference_key}.{number.casefold()}")
        for number in numbers
    )


def _source_map_covers_role(
    assignments: Sequence[tuple[str, str]],
    expected_net: str,
    expected_role: str,
    mapped: Mapping[str, ConnectorMappedPinEvidence],
) -> bool:
    for pin, _function in assignments:
        evidence = mapped.get(pin.casefold())
        if evidence is None:
            return False
        if i2c_signal_role(evidence.interface_signal) != expected_role:
            return False
        if tuple(net.casefold() for net in evidence.nets) != (expected_net.casefold(),):
            return False
    return bool(assignments)


def _ordered(pins: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted(pins, key=lambda item: (item.casefold(), item)))


def _functions_for(assignments: Iterable[tuple[str, str]]) -> tuple[str, ...]:
    by_pin = {pin.casefold(): function for pin, function in assignments}
    return tuple(by_pin[pin.casefold()] for pin in _ordered(by_pin))
