"""Typed sources and report projection for mapped stateful connector contacts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeAlias

from .connector_stateful_contact_models import (
    ConnectorStatefulContactMap,
    ConnectorStatefulContactPair,
    ConnectorStatefulContactRequirement,
)
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .netlist_contract_models import NetlistContract
from .netlist_pin_assignments import netlist_pin_net_index

StatefulContactTopologyState: TypeAlias = Literal[
    "unassigned",
    "ambiguous_assignment",
    "permanently_bypassed",
]

RULE_ID: DesignLintRuleId = "connector.stateful_contact_topology_mismatch"


def stateful_contact_identity_issues(
    requirement: ConnectorStatefulContactRequirement,
    observed: NetlistContract,
) -> tuple[str, ...]:
    """Compare an authored contact requirement with current native identity."""
    reference_key = requirement.reference.casefold()
    components = {key.casefold(): value for key, value in observed.components.items()}
    symbols = {key.casefold(): value for key, value in observed.component_symbols.items()}
    inventories = {
        key.casefold(): {pin.casefold() for pin in values}
        for key, values in observed.component_pin_numbers.items()
    }
    component = components.get(reference_key)
    issues: list[str] = []
    if component is None:
        issues.append(f"{requirement.reference} is absent from the native netlist")
    else:
        if symbols.get(reference_key) != requirement.expected_symbol:
            issues.append(
                f"symbol is {symbols.get(reference_key) or 'unknown'}; "
                f"expected {requirement.expected_symbol}"
            )
        if component.value != requirement.expected_value:
            issues.append(f"value is {component.value}; expected {requirement.expected_value}")
        if component.footprint != requirement.expected_footprint:
            issues.append(
                f"footprint is {component.footprint or 'empty'}; "
                f"expected {requirement.expected_footprint}"
            )
        if component.part_id != requirement.expected_part_id:
            issues.append(
                f"PART_ID is {component.part_id or 'missing'}; "
                f"expected {requirement.expected_part_id}"
            )

    expected_pins = {pin.casefold() for pin in requirement.native_pin_numbers}
    actual_pins = inventories.get(reference_key)
    if actual_pins != expected_pins:
        issues.append(
            "native pin inventory is "
            f"{', '.join(sorted(actual_pins or ())) or 'unknown'}; "
            f"expected {', '.join(sorted(expected_pins))}"
        )
    return tuple(issues)


def _requirement_is_in_map(
    requirement: ConnectorStatefulContactRequirement,
    contact_map: ConnectorStatefulContactMap,
) -> bool:
    return any(item == requirement for item in contact_map.requirements)


@dataclass(frozen=True, slots=True)
class StatefulContactMapMismatchEvidence:
    """Authored map requirement and exact current identity mismatch details."""

    observed: NetlistContract
    contact_map: ConnectorStatefulContactMap
    requirement: ConnectorStatefulContactRequirement
    identity_issues: tuple[str, ...]

    def __post_init__(self) -> None:
        if not _requirement_is_in_map(self.requirement, self.contact_map):
            raise ValueError("Stateful contact requirement must belong to the retained map")
        expected = stateful_contact_identity_issues(self.requirement, self.observed)
        if not expected or expected != self.identity_issues:
            raise ValueError("Stateful contact identity issues must match the current netlist")


@dataclass(frozen=True, slots=True)
class StatefulContactTopologyEvidence:
    """Mapped contact pair and exact native assignments for its two terminals."""

    observed: NetlistContract
    contact_map: ConnectorStatefulContactMap
    requirement: ConnectorStatefulContactRequirement
    pair: ConnectorStatefulContactPair
    first_nets: tuple[str, ...]
    second_nets: tuple[str, ...]
    topology_state: StatefulContactTopologyState

    @property
    def first_pin(self) -> str:
        return f"{self.requirement.reference}.{self.pair.first_pin}"

    @property
    def second_pin(self) -> str:
        return f"{self.requirement.reference}.{self.pair.second_pin}"

    def __post_init__(self) -> None:
        if not _requirement_is_in_map(self.requirement, self.contact_map):
            raise ValueError("Stateful contact requirement must belong to the retained map")
        if not any(item == self.pair for item in self.requirement.contact_pairs):
            raise ValueError("Stateful contact pair must belong to the retained requirement")
        if stateful_contact_identity_issues(self.requirement, self.observed):
            raise ValueError("Stateful contact topology requires current component identity")
        if self.requirement.reference.casefold() in {
            reference.casefold() for reference in self.observed.dnp_components
        }:
            raise ValueError("Unpopulated connectors cannot support contact topology findings")

        pin_nets = netlist_pin_net_index(self.observed)
        expected_first = tuple(sorted(pin_nets.get(self.first_pin.casefold(), ())))
        expected_second = tuple(sorted(pin_nets.get(self.second_pin.casefold(), ())))
        if self.first_nets != expected_first or self.second_nets != expected_second:
            raise ValueError("Stateful contact pin assignments must match the current netlist")

        if not self.first_nets or not self.second_nets:
            expected_state: StatefulContactTopologyState = "unassigned"
        elif len(self.first_nets) != 1 or len(self.second_nets) != 1:
            expected_state = "ambiguous_assignment"
        elif self.first_nets[0] == self.second_nets[0]:
            expected_state = "permanently_bypassed"
        else:
            raise ValueError("Distinct assigned contact nets cannot produce topology findings")
        if self.topology_state != expected_state:
            raise ValueError("Stateful contact topology state must match exact pin assignments")


StatefulContactFindingSource: TypeAlias = (
    StatefulContactMapMismatchEvidence | StatefulContactTopologyEvidence
)


def project_stateful_contact_evidence(
    source: StatefulContactFindingSource,
) -> CandidateEvidenceProjection:
    """Project either source mismatch or contact topology into report fields."""
    requirement = source.requirement
    if isinstance(source, StatefulContactMapMismatchEvidence):
        evidence = {
            "requirement_id": (requirement.id,),
            "reference": (requirement.reference,),
            "identity_issues": source.identity_issues,
            "map_basis": (source.contact_map.basis,),
        }
    else:
        evidence = {
            "requirement_id": (requirement.id,),
            "reference": (requirement.reference,),
            "contact_pair": (source.pair.id,),
            "first_pin": (source.first_pin,),
            "second_pin": (source.second_pin,),
            "first_nets": source.first_nets,
            "second_nets": source.second_nets,
            "closed_when": (source.pair.closed_when,),
            "source_basis": (source.pair.source_basis,),
            "map_basis": (source.contact_map.basis,),
            "topology_state": (source.topology_state,),
        }
    return CandidateEvidenceProjection(rule_id=RULE_ID, evidence=evidence)


@dataclass(frozen=True, slots=True)
class StatefulConnectorContactCandidate(Candidate):
    """Candidate retaining the authored map and the relevant native evidence."""

    source_evidence: StatefulContactFindingSource

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: StatefulContactFindingSource,
        *,
        subject: str,
        message: str,
    ) -> StatefulConnectorContactCandidate:
        projection = project_stateful_contact_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_stateful_contact_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("Stateful contact candidate must match its typed source projection")
