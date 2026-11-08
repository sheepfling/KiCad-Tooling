"""Review two-contact I3C connectors without an identified reference return."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass

from .casefold_mapping_lookup import casefolded_unique_index
from .connector_coverage import source_matched_connector_pin_evidence
from .connector_coverage_models import ConnectorCoverageReport, ConnectorMappedPinEvidence
from .connector_identity import connector_candidate_references, pin_function_is_generic
from .connector_pin_metadata import connector_pin_metadata_matches_inventory
from .connector_return_pins import connector_pin_group_has_return_role
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .i3c_connector_map import i3c_source_map_covers_role
from .i3c_endpoint_pairs import I3cEndpointPair, i3c_endpoint_pairs
from .netlist_contract_models import NetlistContract

I3C_CONNECTOR_RETURN_RULE_ID: DesignLintRuleId = "connector.i3c_pair_without_return_review"


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
    endpoints = i3c_endpoint_pairs(observed)
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
    return i3c_source_map_covers_role(
        sda_pin, sda_net, "SDA", mapped
    ) and i3c_source_map_covers_role(scl_pin, scl_net, "SCL", mapped)
