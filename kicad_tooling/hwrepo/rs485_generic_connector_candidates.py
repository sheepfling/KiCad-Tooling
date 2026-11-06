"""Find generic connector contacts assigned to an identified RS-485 pair."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from collections.abc import Set as AbstractSet

from .casefold_mapping_lookup import casefolded_unique_index
from .connector_coverage import source_matched_connector_pin_evidence
from .connector_coverage_models import ConnectorCoverageReport, ConnectorMappedPinEvidence
from .connector_identity import connector_candidate_references, pin_function_is_generic
from .connector_pin_metadata import connector_pin_metadata_matches_inventory
from .netlist_contract_models import ComponentContract, NetlistContract
from .rs485_data_functions import explicit_rs485_transceiver_identity
from .rs485_generic_connector_models import Rs485GenericConnectorPair, Rs485GenericEndpointPair
from .rs485_line_functions import rs485_bus_line_label_role, rs485_bus_line_role

_IC_REFERENCE = re.compile(r"^(?:U|IC)[0-9]+$", re.IGNORECASE)


def rs485_generic_connector_pairs(
    observed: NetlistContract,
    reviewed_connector_references: tuple[str, ...] = (),
    connector_coverage: ConnectorCoverageReport | None = None,
) -> tuple[Rs485GenericConnectorPair, ...]:
    """Find generic connector contacts on both exact nets of an RS-485 A/B pair.

    Native endpoint identity and pin functions establish only a possible
    transceiver line pair. Generic connector functions prompt a pinout review;
    they do not establish that the connector belongs to the bus.
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

    endpoint_pairs = _recognized_endpoint_pairs(
        observed=observed,
        symbols=symbols,
        reference_spellings=reference_spellings,
        components=components,
        inventories=inventories,
        functions=functions,
        electrical_types=electrical_types,
        assignments=assignments,
        dnp=dnp,
    )
    by_line_pair: dict[tuple[str, str], list[Rs485GenericEndpointPair]] = {}
    for endpoint in endpoint_pairs:
        by_line_pair.setdefault((endpoint.a_net.casefold(), endpoint.b_net.casefold()), []).append(
            endpoint
        )

    findings: list[Rs485GenericConnectorPair] = []
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
            functions.get(f"{connector_key}.{number.casefold()}") for number in numbers
        )
        if any(function is None for function in connector_functions):
            continue

        for net_keys, endpoints in sorted(by_line_pair.items()):
            a_net, b_net = endpoints[0].a_net, endpoints[0].b_net
            a_assignments: list[tuple[str, str]] = []
            b_assignments: list[tuple[str, str]] = []
            ambiguous = False
            for number, function in zip(numbers, connector_functions, strict=True):
                pin = f"{reference_spellings[connector_key]}.{number}"
                nets = assignments.get(pin.casefold(), set())
                if len(nets) > 1:
                    ambiguous = True
                    break
                if len(nets) != 1 or not pin_function_is_generic(function):
                    continue
                net = next(iter(nets))
                if net.casefold() == net_keys[0]:
                    a_assignments.append((pin, function or ""))
                elif net.casefold() == net_keys[1]:
                    b_assignments.append((pin, function or ""))

            if ambiguous or not a_assignments or not b_assignments:
                continue
            if _source_map_covers_role(a_assignments, a_net, "a", mapped_by_pin) and (
                _source_map_covers_role(b_assignments, b_net, "b", mapped_by_pin)
            ):
                continue
            ordered_a = _ordered(a_assignments)
            ordered_b = _ordered(b_assignments)
            findings.append(
                Rs485GenericConnectorPair(
                    connector_reference=reference_spellings[connector_key],
                    connector_pin_count=len(numbers),
                    a_connector_pins=tuple(pin for pin, _function in ordered_a),
                    a_connector_functions=tuple(function for _pin, function in ordered_a),
                    a_net=a_net,
                    b_connector_pins=tuple(pin for pin, _function in ordered_b),
                    b_connector_functions=tuple(function for _pin, function in ordered_b),
                    b_net=b_net,
                    endpoint_pairs=tuple(
                        sorted(
                            endpoints,
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
                item.a_net.casefold(),
                item.b_net.casefold(),
            ),
        )
    )


def _recognized_endpoint_pairs(
    *,
    observed: NetlistContract,
    symbols: Mapping[str, str],
    reference_spellings: Mapping[str, str],
    components: Mapping[str, ComponentContract],
    inventories: Mapping[str, tuple[str, ...]],
    functions: Mapping[str, str],
    electrical_types: Mapping[str, str],
    assignments: Mapping[str, AbstractSet[str]],
    dnp: AbstractSet[str],
) -> tuple[Rs485GenericEndpointPair, ...]:
    result: list[Rs485GenericEndpointPair] = []
    for reference_key in sorted(symbols):
        reference = reference_spellings.get(reference_key)
        if (
            reference is None
            or not _IC_REFERENCE.fullmatch(reference)
            or reference_key in dnp
            or reference_key not in components
            or explicit_rs485_transceiver_identity(observed, reference) is None
        ):
            continue
        numbers = inventories.get(reference_key)
        if not numbers or len({number.casefold() for number in numbers}) != len(numbers):
            continue
        if not connector_pin_metadata_matches_inventory(
            reference_key, numbers, functions, electrical_types
        ):
            continue

        by_role: dict[str, list[str]] = {"a": [], "b": []}
        for number in numbers:
            pin = f"{reference}.{number}"
            role = rs485_bus_line_role(functions[pin.casefold()])
            if role is not None:
                by_role[role].append(pin)
        if len(by_role["a"]) != 1 or len(by_role["b"]) != 1:
            continue
        a_pin, b_pin = by_role["a"][0], by_role["b"][0]
        a_nets, b_nets = (
            assignments.get(a_pin.casefold(), ()),
            assignments.get(b_pin.casefold(), ()),
        )
        if len(a_nets) != 1 or len(b_nets) != 1:
            continue
        a_net, b_net = next(iter(a_nets)), next(iter(b_nets))
        if a_net.casefold() == b_net.casefold():
            continue
        result.append(
            Rs485GenericEndpointPair(
                reference=reference,
                a_pin=a_pin,
                a_net=a_net,
                b_pin=b_pin,
                b_net=b_net,
            )
        )
    return tuple(result)


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
        observed_role = rs485_bus_line_role(evidence.interface_signal) or (
            rs485_bus_line_label_role(evidence.interface_signal)
        )
        if observed_role != expected_role:
            return False
        if tuple(net.casefold() for net in evidence.nets) != (expected_net.casefold(),):
            return False
    return bool(assignments)


def _ordered(assignments: Sequence[tuple[str, str]]) -> tuple[tuple[str, str], ...]:
    return tuple(sorted(assignments, key=lambda item: (item[0].casefold(), item[0])))
