"""Find generic connector contacts assigned to exact native UART TX/RX pairs."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from collections.abc import Set as AbstractSet

from .casefold_mapping_lookup import casefolded_unique_index
from .connector_coverage import source_matched_connector_pin_evidence
from .connector_coverage_models import ConnectorCoverageReport, ConnectorMappedPinEvidence
from .connector_identity import connector_candidate_references, pin_function_is_generic
from .connector_pin_metadata import connector_pin_metadata_matches_inventory
from .netlist_contract_models import ComponentContract, NetlistContract
from .serial_generic_connector_models import (
    SerialGenericConnectorContact,
    SerialGenericConnectorPair,
    SerialGenericEndpointPair,
)
from .serial_participants import is_serial_ic_reference, serial_function_role_and_channel

_TX_TYPES = frozenset({"output", "tri_state", "bidirectional"})
_RX_TYPES = frozenset({"input", "bidirectional"})


def serial_generic_connector_pairs(
    observed: NetlistContract,
    reviewed_connector_references: tuple[str, ...] = (),
    connector_coverage: ConnectorCoverageReport | None = None,
) -> tuple[SerialGenericConnectorPair, ...]:
    """Find complete generic connectors on exact fitted-IC UART TX/RX nets.

    Native endpoint pin functions and electrical types establish the observed
    UART pair. Generic connector functions establish only a pinout-review
    question; no net label or reference name supplies electrical intent.
    """
    assignments: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            assignments.setdefault(pin.casefold(), set()).add(net)

    symbols = casefolded_unique_index(observed.component_symbols)
    references = casefolded_unique_index(
        {reference: reference for reference in observed.component_symbols}
    )
    components = casefolded_unique_index(observed.components)
    inventories = casefolded_unique_index(observed.component_pin_numbers)
    functions = casefolded_unique_index(observed.pin_functions)
    electrical_types = casefolded_unique_index(observed.pin_electrical_types)
    dnp = {reference.casefold() for reference in observed.dnp_components}
    connectors = connector_candidate_references(observed, reviewed_connector_references)
    mapped = source_matched_connector_pin_evidence(observed, connector_coverage)
    mapped_by_pin = {pin.casefold(): item for pin, item in mapped.items()}
    not_applicable = {
        entry.reference.casefold()
        for entry in (() if connector_coverage is None else connector_coverage.entries)
        if entry.status == "NOT_APPLICABLE"
    }

    endpoint_pairs = _recognized_serial_endpoint_pairs(
        symbols=symbols,
        references=references,
        components=components,
        inventories=inventories,
        functions=functions,
        electrical_types=electrical_types,
        assignments=assignments,
        dnp=dnp,
    )
    by_net_pair: dict[tuple[str, str], list[SerialGenericEndpointPair]] = {}
    for endpoint in endpoint_pairs:
        key = (endpoint.tx_net.casefold(), endpoint.rx_net.casefold())
        by_net_pair.setdefault(key, []).append(endpoint)

    findings: list[SerialGenericConnectorPair] = []
    for connector in connectors:
        connector_key = connector.casefold()
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

        for net_keys, endpoints in sorted(by_net_pair.items()):
            tx_net, rx_net = endpoints[0].tx_net, endpoints[0].rx_net
            tx_assignments: list[tuple[str, str]] = []
            rx_assignments: list[tuple[str, str]] = []
            ambiguous = False
            for number, function in zip(numbers, connector_functions, strict=True):
                pin = f"{references[connector_key]}.{number}"
                nets = assignments.get(pin.casefold(), set())
                if len(nets) > 1:
                    ambiguous = True
                    break
                if len(nets) != 1 or not pin_function_is_generic(function):
                    continue
                net = next(iter(nets))
                if net.casefold() == net_keys[0]:
                    tx_assignments.append((pin, function or ""))
                elif net.casefold() == net_keys[1]:
                    rx_assignments.append((pin, function or ""))

            if ambiguous or not tx_assignments or not rx_assignments:
                continue
            if _source_map_covers_pair(
                tx_assignments, tx_net, "tx", mapped_by_pin
            ) and _source_map_covers_pair(rx_assignments, rx_net, "rx", mapped_by_pin):
                continue
            pair_pin_keys = {
                pin.casefold() for pin, _function in (*tx_assignments, *rx_assignments)
            }
            other_contacts = tuple(
                sorted(
                    (
                        SerialGenericConnectorContact(
                            pin=f"{references[connector_key]}.{number}",
                            function=function or "",
                            nets=tuple(
                                sorted(
                                    assignments.get(
                                        f"{references[connector_key]}.{number}".casefold(),
                                        set(),
                                    ),
                                    key=lambda item: (item.casefold(), item),
                                )
                            ),
                        )
                        for number, function in zip(numbers, connector_functions, strict=True)
                        if f"{references[connector_key]}.{number}".casefold() not in pair_pin_keys
                    ),
                    key=lambda item: (item.pin.casefold(), item.pin),
                )
            )
            findings.append(
                SerialGenericConnectorPair(
                    connector_reference=references[connector_key],
                    connector_pin_count=len(numbers),
                    tx_connector_pins=_ordered(pin for pin, _function in tx_assignments),
                    tx_connector_functions=_ordered(function for _pin, function in tx_assignments),
                    tx_net=tx_net,
                    rx_connector_pins=_ordered(pin for pin, _function in rx_assignments),
                    rx_connector_functions=_ordered(function for _pin, function in rx_assignments),
                    rx_net=rx_net,
                    endpoint_pairs=tuple(
                        sorted(
                            endpoints,
                            key=lambda item: (
                                item.reference.casefold(),
                                item.reference,
                                item.channel.casefold(),
                            ),
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
                item.tx_net.casefold(),
                item.rx_net.casefold(),
            ),
        )
    )


def _recognized_serial_endpoint_pairs(
    *,
    symbols: Mapping[str, str],
    references: Mapping[str, str],
    components: Mapping[str, ComponentContract],
    inventories: Mapping[str, tuple[str, ...]],
    functions: Mapping[str, str],
    electrical_types: Mapping[str, str],
    assignments: Mapping[str, AbstractSet[str]],
    dnp: AbstractSet[str],
) -> tuple[SerialGenericEndpointPair, ...]:
    result: list[SerialGenericEndpointPair] = []
    for reference_key in sorted(symbols):
        reference = references.get(reference_key)
        if (
            reference is None
            or not is_serial_ic_reference(reference)
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

        role_pins: dict[tuple[str, str], list[tuple[str, str]]] = {}
        for number in numbers:
            pin = f"{reference}.{number}"
            function = functions[pin.casefold()]
            role_channel = serial_function_role_and_channel(function)
            if role_channel is not None:
                role_pins.setdefault(role_channel, []).append(
                    (pin, electrical_types[pin.casefold()])
                )

        channels = sorted({channel for _role, channel in role_pins})
        for channel in channels:
            tx_pins = role_pins.get(("tx", channel), ())
            rx_pins = role_pins.get(("rx", channel), ())
            if len(tx_pins) != 1 or len(rx_pins) != 1:
                continue
            tx_pin, tx_type = tx_pins[0]
            rx_pin, rx_type = rx_pins[0]
            if tx_type not in _TX_TYPES or rx_type not in _RX_TYPES:
                continue
            tx_nets = assignments.get(tx_pin.casefold(), ())
            rx_nets = assignments.get(rx_pin.casefold(), ())
            if len(tx_nets) != 1 or len(rx_nets) != 1:
                continue
            tx_net, rx_net = next(iter(tx_nets)), next(iter(rx_nets))
            if tx_net.casefold() == rx_net.casefold():
                continue
            result.append(
                SerialGenericEndpointPair(
                    reference=reference,
                    channel=channel,
                    tx_pin=tx_pin,
                    tx_net=tx_net,
                    rx_pin=rx_pin,
                    rx_net=rx_net,
                )
            )
    return tuple(result)


def _source_map_covers_pair(
    assignments: Sequence[tuple[str, str]],
    expected_net: str,
    expected_role: str,
    mapped: Mapping[str, ConnectorMappedPinEvidence],
) -> bool:
    for pin, _function in assignments:
        evidence = mapped.get(pin.casefold())
        if evidence is None or tuple(net.casefold() for net in evidence.nets) != (
            expected_net.casefold(),
        ):
            return False
        role_channel = serial_function_role_and_channel(evidence.interface_signal)
        if role_channel is None or role_channel[0] != expected_role:
            return False
    return bool(assignments)


def _ordered(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted(values, key=lambda item: (item.casefold(), item)))
