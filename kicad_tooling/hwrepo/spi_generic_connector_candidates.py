"""Find generic connector contacts assigned to a recognized SPI role triad."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from collections.abc import Set as AbstractSet

from .casefold_mapping_lookup import casefolded_unique_index
from .connector_coverage import source_matched_connector_pin_evidence
from .connector_coverage_models import ConnectorCoverageReport, ConnectorMappedPinEvidence
from .connector_identity import connector_candidate_references, pin_function_is_generic
from .netlist_contract_models import ComponentContract, NetlistContract
from .spi_generic_connector_models import SpiGenericConnectorTriad, SpiGenericEndpointTriad
from .spi_participants import spi_signal_role_and_channel
from .spi_role_assignments import SpiRolePinAssignment, spi_role_assignment_groups

_ROLE_ORDER = ("clock", "data_input", "data_output")


def generic_spi_connector_triads(
    observed: NetlistContract,
    reviewed_connector_references: tuple[str, ...] = (),
    connector_coverage: ConnectorCoverageReport | None = None,
) -> tuple[SpiGenericConnectorTriad, ...]:
    """Find complete generic connector groups on exact native SPI triad nets.

    Native pin functions establish the fitted IC role triad. Generic connector
    functions establish only a review clue; this predicate does not infer that
    the connector belongs to SPI or establish an electrical requirement.
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
    mapped_by_pin = {pin.casefold(): evidence for pin, evidence in mapped.items()}
    not_applicable = {
        entry.reference.casefold()
        for entry in (() if connector_coverage is None else connector_coverage.entries)
        if entry.status == "NOT_APPLICABLE"
    }

    endpoints = _recognized_spi_endpoint_triads(
        observed,
        assignments,
        symbols,
        references,
        components,
        inventories,
        functions,
        electrical_types,
        dnp,
    )
    by_nets: dict[tuple[str, str, str], list[SpiGenericEndpointTriad]] = {}
    for endpoint in endpoints:
        key = (
            endpoint.clock_net.casefold(),
            endpoint.data_input_net.casefold(),
            endpoint.data_output_net.casefold(),
        )
        by_nets.setdefault(key, []).append(endpoint)

    findings: list[SpiGenericConnectorTriad] = []
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
        if not _metadata_matches_inventory(connector_key, numbers, functions, electrical_types):
            continue
        connector_functions = tuple(
            functions.get(f"{connector_key}.{number.casefold()}") for number in numbers
        )
        if any(function is None for function in connector_functions):
            continue

        for _net_keys, endpoint_group in sorted(by_nets.items()):
            endpoint = endpoint_group[0]
            nets_by_role = {
                "clock": endpoint.clock_net,
                "data_input": endpoint.data_input_net,
                "data_output": endpoint.data_output_net,
            }
            pins_by_role: dict[str, list[tuple[str, str]]] = {role: [] for role in _ROLE_ORDER}
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
                for role, endpoint_net in nets_by_role.items():
                    if net.casefold() == endpoint_net.casefold():
                        pins_by_role[role].append((pin, function or ""))
                        break

            if ambiguous or any(not pins_by_role[role] for role in _ROLE_ORDER):
                continue
            if _source_map_covers_triad(pins_by_role, nets_by_role, mapped_by_pin):
                continue
            findings.append(
                SpiGenericConnectorTriad(
                    connector_reference=references[connector_key],
                    connector_pin_count=len(numbers),
                    role_connector_pins={
                        role: _ordered(pin for pin, _function in pins_by_role[role])
                        for role in _ROLE_ORDER
                    },
                    role_connector_functions={
                        role: _ordered(function for _pin, function in pins_by_role[role])
                        for role in _ROLE_ORDER
                    },
                    role_nets=nets_by_role,
                    endpoint_triads=tuple(
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
                *(item.role_nets[role].casefold() for role in _ROLE_ORDER),
            ),
        )
    )


def _recognized_spi_endpoint_triads(
    observed: NetlistContract,
    assignments: Mapping[str, AbstractSet[str]],
    symbols: Mapping[str, str],
    references: Mapping[str, str],
    components: Mapping[str, ComponentContract],
    inventories: Mapping[str, tuple[str, ...]],
    functions: Mapping[str, str],
    electrical_types: Mapping[str, str],
    dnp: AbstractSet[str],
) -> tuple[SpiGenericEndpointTriad, ...]:
    result: list[SpiGenericEndpointTriad] = []
    for group in spi_role_assignment_groups(observed):
        reference_key = group.reference.casefold()
        if (
            reference_key in dnp
            or reference_key not in symbols
            or reference_key not in references
            or reference_key not in components
        ):
            continue
        numbers = inventories.get(reference_key)
        if not numbers or len({number.casefold() for number in numbers}) != len(numbers):
            continue
        if not _metadata_matches_inventory(reference_key, numbers, functions, electrical_types):
            continue
        role_pins = {role: group.roles.get(role, ()) for role in _ROLE_ORDER}
        if any(len(role_pins[role]) != 1 for role in _ROLE_ORDER):
            continue
        selected: dict[str, SpiRolePinAssignment] = {
            role: role_pins[role][0] for role in _ROLE_ORDER
        }
        if any(
            not pin.in_component_inventory or pin.electrical_type == "unknown" or len(pin.nets) != 1
            for pin in selected.values()
        ):
            continue
        nets = {role: selected[role].nets[0] for role in _ROLE_ORDER}
        if len({net.casefold() for net in nets.values()}) != len(_ROLE_ORDER):
            continue
        if any(
            len(assignments.get(selected[role].pin.casefold(), ())) != 1 for role in _ROLE_ORDER
        ):
            continue
        result.append(
            SpiGenericEndpointTriad(
                reference=references[reference_key],
                channel=group.channel,
                clock_pin=selected["clock"].pin,
                clock_net=nets["clock"],
                data_input_pin=selected["data_input"].pin,
                data_input_net=nets["data_input"],
                data_output_pin=selected["data_output"].pin,
                data_output_net=nets["data_output"],
            )
        )
    return tuple(result)


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
            if pin.rpartition(".")[0] == reference_key
        }
        if actual != expected:
            return False
    return all(
        functions.get(f"{reference_key}.{number.casefold()}")
        and electrical_types.get(f"{reference_key}.{number.casefold()}")
        for number in numbers
    )


def _source_map_covers_triad(
    pins_by_role: Mapping[str, list[tuple[str, str]]],
    nets_by_role: Mapping[str, str],
    mapped_by_pin: Mapping[str, ConnectorMappedPinEvidence],
) -> bool:
    for role in _ROLE_ORDER:
        for pin, _function in pins_by_role[role]:
            evidence = mapped_by_pin.get(pin.casefold())
            if evidence is None or len(evidence.nets) != 1:
                return False
            mapped_role = spi_signal_role_and_channel(evidence.interface_signal)
            if mapped_role is None or mapped_role[0] != role:
                return False
            if evidence.nets[0].casefold() != nets_by_role[role].casefold():
                return False
    return True


def _ordered(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted(values, key=lambda item: (item.casefold(), item)))
