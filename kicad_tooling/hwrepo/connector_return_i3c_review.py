"""Review two-contact I3C connectors without an identified reference return."""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from typing import Literal

from .bus_signal_roles import i3c_signal_identity
from .casefold_mapping_lookup import casefolded_unique_index
from .connector_coverage import source_matched_connector_pin_evidence
from .connector_coverage_models import ConnectorCoverageReport, ConnectorMappedPinEvidence
from .connector_identity import connector_candidate_references, pin_function_is_generic
from .connector_pin_metadata import connector_pin_metadata_matches_inventory
from .connector_return_pins import connector_pin_group_has_return_role
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .netlist_contract_models import ComponentContract, NetlistContract

I3C_CONNECTOR_RETURN_RULE_ID: DesignLintRuleId = "connector.i3c_pair_without_return_review"
_IC_REFERENCE = re.compile(r"^(?:U|IC)[0-9]+$", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class I3cEndpointPair:
    """One fitted U/IC with a unique native I3C SDA/SCL pair."""

    reference: str
    sda_pin: str
    sda_net: str
    scl_pin: str
    scl_net: str


@dataclass(frozen=True, slots=True)
class I3cConnectorPair:
    """One complete two-contact generic connector on an exact I3C bus."""

    connector_reference: str
    sda_pin: str
    sda_net: str
    scl_pin: str
    scl_net: str
    endpoint_pairs: tuple[I3cEndpointPair, ...]


@dataclass(frozen=True, slots=True)
class I3cConnectorReturnEvidence:
    """Source-bound I3C connector observation for one review prompt."""

    pair: I3cConnectorPair


def _project_evidence(
    source: I3cConnectorReturnEvidence,
) -> CandidateEvidenceProjection:
    pair = source.pair
    return CandidateEvidenceProjection(
        rule_id=I3C_CONNECTOR_RETURN_RULE_ID,
        evidence={
            "connector": (pair.connector_reference,),
            "connector_native_pin_count": ("2",),
            "connected_contact_count": ("2",),
            "SDA_net": (pair.sda_net,),
            "SDA_generic_connector_pins": (pair.sda_pin,),
            "SCL_net": (pair.scl_net,),
            "SCL_generic_connector_pins": (pair.scl_pin,),
            "I3C_endpoint_pairs": tuple(
                f"{item.reference}:{item.sda_pin}=SDA/{item.sda_net};"
                f"{item.scl_pin}=SCL/{item.scl_net}"
                for item in pair.endpoint_pairs
            ),
            "identified_connector_return_role": (),
        },
    )


@dataclass(frozen=True, slots=True)
class I3cConnectorReturnCandidate(Candidate):
    """Review prompt for a two-pin generic I3C connector's reference."""

    source_evidence: I3cConnectorReturnEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: I3cConnectorReturnEvidence,
    ) -> I3cConnectorReturnCandidate:
        projection = _project_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=(
                f"{source_evidence.pair.connector_reference}: two-pin I3C connector "
                "has no identified reference return"
            ),
            message=(
                "Native U/IC pin functions identify this complete two-pin connector as a "
                "generic I3C SDA/SCL pair, and no connector contact function or current, "
                "source-matched pin map identifies a return. Review whether the signal "
                "reference is provided elsewhere, the interface is intentionally isolated, "
                "or the connector pinout needs a return contact. This prompt does not require "
                "connection to board ground or establish external wiring or PCB copper."
            ),
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = _project_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("I3C connector return evidence must match its source projection")


def i3c_connector_missing_return_candidates(
    observed: NetlistContract,
    reviewed_connector_references: tuple[str, ...] = (),
    connector_coverage: ConnectorCoverageReport | None = None,
) -> tuple[Candidate, ...]:
    """Prompt on exact two-pin generic I3C connectors lacking a return role.

    The cue asks whether reference is supplied elsewhere, intentionally
    isolated, or omitted from a reviewed pinout. It never requires board ground.
    """
    assignments = _pin_assignments(observed)
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
    endpoints = _i3c_endpoint_pairs(
        symbols=symbols,
        references=references,
        components=components,
        inventories=inventories,
        functions=functions,
        electrical_types=electrical_types,
        assignments=assignments,
        dnp=dnp,
    )
    by_bus: dict[tuple[str, str], list[I3cEndpointPair]] = defaultdict(list)
    for endpoint in endpoints:
        by_bus[endpoint.sda_net.casefold(), endpoint.scl_net.casefold()].append(endpoint)

    findings: list[Candidate] = []
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
            or len(numbers) != 2
            or len({number.casefold() for number in numbers}) != 2
            or not connector_pin_metadata_matches_inventory(
                connector_key, numbers, functions, electrical_types
            )
        ):
            continue
        connector_functions = tuple(
            functions.get(f"{connector_key}.{number.casefold()}") for number in numbers
        )
        for bus_key, bus_endpoints in sorted(by_bus.items()):
            assignment = _generic_bus_contacts(
                connector_reference,
                numbers,
                connector_functions,
                assignments,
                bus_key,
            )
            if assignment is None:
                continue
            sda_pin, sda_net, scl_pin, scl_net = assignment
            connector_pins = (sda_pin, scl_pin)
            if connector_pin_group_has_return_role(
                connector_pins,
                observed.pin_functions,
                mapped,
            ) or _source_map_covers_pair(
                sda_pin,
                sda_net,
                scl_pin,
                scl_net,
                mapped_by_pin,
            ):
                continue
            endpoints_for_bus = tuple(
                sorted(
                    bus_endpoints,
                    key=lambda item: (item.reference.casefold(), item.reference),
                )
            )
            findings.append(
                I3cConnectorReturnCandidate.from_source_evidence(
                    I3cConnectorReturnEvidence(
                        I3cConnectorPair(
                            connector_reference=connector_reference,
                            sda_pin=sda_pin,
                            sda_net=sda_net,
                            scl_pin=scl_pin,
                            scl_net=scl_net,
                            endpoint_pairs=endpoints_for_bus,
                        )
                    )
                )
            )
    return tuple(
        sorted(
            findings,
            key=lambda item: (
                item.subject.casefold(),
                item.subject,
                tuple(sorted((key, value) for key, value in item.evidence.items())),
            ),
        )
    )


def _pin_assignments(observed: NetlistContract) -> dict[str, set[str]]:
    assignments: dict[str, set[str]] = defaultdict(set)
    for net, pins in observed.nets.items():
        for pin in pins:
            assignments[pin.casefold()].add(net)
    return assignments


def _i3c_endpoint_pairs(
    *,
    symbols: Mapping[str, str],
    references: Mapping[str, str],
    components: Mapping[str, ComponentContract],
    inventories: Mapping[str, tuple[str, ...]],
    functions: Mapping[str, str],
    electrical_types: Mapping[str, str],
    assignments: Mapping[str, AbstractSet[str]],
    dnp: AbstractSet[str],
) -> tuple[I3cEndpointPair, ...]:
    endpoints: list[I3cEndpointPair] = []
    for reference_key in sorted(symbols):
        reference = references.get(reference_key)
        if (
            reference is None
            or not _IC_REFERENCE.fullmatch(reference)
            or reference_key in dnp
            or reference_key not in components
        ):
            continue
        numbers = inventories.get(reference_key)
        if (
            numbers is None
            or len({number.casefold() for number in numbers}) != len(numbers)
            or not connector_pin_metadata_matches_inventory(
                reference_key, numbers, functions, electrical_types
            )
        ):
            continue
        by_channel: dict[str | None, dict[str, list[str]]] = defaultdict(
            lambda: {"SDA": [], "SCL": []}
        )
        for number in numbers:
            pin = f"{reference}.{number}"
            identity = i3c_signal_identity(functions[f"{reference_key}.{number.casefold()}"])
            if identity is not None:
                by_channel[identity.channel][identity.role].append(pin)
        for channel_roles in by_channel.values():
            if len(channel_roles["SDA"]) != 1 or len(channel_roles["SCL"]) != 1:
                continue
            sda_pin, scl_pin = channel_roles["SDA"][0], channel_roles["SCL"][0]
            sda_nets = assignments.get(sda_pin.casefold(), set())
            scl_nets = assignments.get(scl_pin.casefold(), set())
            if len(sda_nets) != 1 or len(scl_nets) != 1:
                continue
            sda_net, scl_net = next(iter(sda_nets)), next(iter(scl_nets))
            if sda_net.casefold() == scl_net.casefold():
                continue
            endpoints.append(I3cEndpointPair(reference, sda_pin, sda_net, scl_pin, scl_net))
    return tuple(sorted(endpoints, key=lambda item: (item.reference.casefold(), item.reference)))


def _generic_bus_contacts(
    connector_reference: str,
    numbers: tuple[str, ...],
    functions: tuple[str | None, ...],
    assignments: Mapping[str, AbstractSet[str]],
    bus_key: tuple[str, str],
) -> tuple[str, str, str, str] | None:
    matches: dict[str, list[tuple[str, str]]] = {"SDA": [], "SCL": []}
    for number, function in zip(numbers, functions, strict=True):
        if not pin_function_is_generic(function):
            continue
        pin = f"{connector_reference}.{number}"
        nets = assignments.get(pin.casefold(), set())
        if len(nets) != 1:
            continue
        net = next(iter(nets))
        if net.casefold() == bus_key[0]:
            matches["SDA"].append((pin, net))
        elif net.casefold() == bus_key[1]:
            matches["SCL"].append((pin, net))
    if len(matches["SDA"]) != 1 or len(matches["SCL"]) != 1:
        return None
    sda_pin, sda_net = matches["SDA"][0]
    scl_pin, scl_net = matches["SCL"][0]
    return sda_pin, sda_net, scl_pin, scl_net


def _source_map_covers_pair(
    sda_pin: str,
    sda_net: str,
    scl_pin: str,
    scl_net: str,
    mapped: Mapping[str, ConnectorMappedPinEvidence],
) -> bool:
    return _source_map_covers_role(sda_pin, sda_net, "SDA", mapped) and _source_map_covers_role(
        scl_pin, scl_net, "SCL", mapped
    )


def _source_map_covers_role(
    pin: str,
    expected_net: str,
    expected_role: Literal["SDA", "SCL"],
    mapped: Mapping[str, ConnectorMappedPinEvidence],
) -> bool:
    evidence = mapped.get(pin.casefold())
    if evidence is None or _mapped_signal_role(evidence.interface_signal) != expected_role:
        return False
    return tuple(net.casefold() for net in evidence.nets) == (expected_net.casefold(),)


def _mapped_signal_role(signal: str) -> str | None:
    identity = i3c_signal_identity(signal)
    if identity is not None:
        return identity.role
    compact = re.sub(r"[^a-z0-9]", "", signal.casefold())
    return compact.upper() if compact in {"sda", "scl"} else None
