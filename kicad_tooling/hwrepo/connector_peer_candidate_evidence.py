"""Review messages and source evidence for repeated connector-pin findings."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import TypeAlias

from .connector_coverage_models import ConnectorMappedPinEvidence
from .connector_identity import power_function_key
from .connector_peer_pin_models import SimilarConnectorPinGroup
from .connector_peer_pin_scan import (
    ConnectorPeerPinAssignmentDivergence,
    ConnectorPeerPinAssignmentOutlier,
)
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .netlist_contract_models import NetlistContract


def connector_group_message(group: SimilarConnectorPinGroup) -> str:
    """Describe why a repeated-pin group needs review without declaring intent."""
    if group.return_comparison_group is not None:
        scope = (
            " This comparison is scoped to source-reviewed return-comparison group "
            f"{group.return_comparison_group}; grouping scopes comparisons only and does not "
            "establish continuity, bonding, or electrical isolation."
        )
    elif group.supply_comparison_group is not None:
        scope = (
            " This comparison is scoped to source-reviewed supply-comparison group "
            f"{group.supply_comparison_group}; grouping scopes comparisons only and does not "
            "require common power nets or assert that other domains are isolated."
        )
    elif group.peer_assignment_group is not None:
        scope = (
            " This comparison is scoped to source-reviewed peer-assignment group "
            f"{group.peer_assignment_group}."
        )
    else:
        scope = ""
    if group.reviewed_role == "supply" and group.reviewed_voltage_domain is not None:
        return (
            "Connector supply contacts with the same source-reviewed voltage domain "
            f"({group.reviewed_voltage_domain}) use different or missing nets. Review whether "
            "they share a rail, are intentionally switched or isolated, or have independent "
            "sources; this role and domain classification does not require commonality." + scope
        )
    if group.function == "ground/return":
        return (
            "Connector return pins identified by symbol functions or the source-matched project "
            "interface map use different or missing nets. Review whether the domains should be "
            "common, bonded, or intentionally isolated; role classification alone does not "
            "require commonality." + scope
        )
    if power_function_key(group.function) is not None:
        return (
            "Matching connector supply pins use different or missing nets. Review whether they "
            "share a rail, are intentionally separate, or have independent supplies." + scope
        )
    return (
        "Matching connector pin functions use different or missing nets. Review the intended "
        "pinout and signal relationship." + scope
    )


def connector_group_evidence(
    group: SimilarConnectorPinGroup,
    observed: NetlistContract,
    reviewed_connector_pins: Mapping[str, ConnectorMappedPinEvidence],
) -> dict[str, tuple[str, ...]]:
    """Add authored comparison-scope and mapped-role evidence to a lint finding."""
    evidence: dict[str, tuple[str, ...]] = {}
    if group.peer_assignment_group is not None:
        evidence.update(
            {
                "peer_assignment_group": (group.peer_assignment_group,),
                "peer_assignment_basis": group.peer_assignment_basis,
            }
        )
    if group.return_comparison_group is not None:
        evidence.update(
            {
                "return_comparison_group": (group.return_comparison_group,),
                "return_comparison_basis": group.return_comparison_basis,
            }
        )
    if group.supply_comparison_group is not None:
        evidence.update(
            {
                "supply_comparison_group": (group.supply_comparison_group,),
                "supply_comparison_basis": group.supply_comparison_basis,
            }
        )
    evidence.update(_connector_group_role_source_evidence(group, observed, reviewed_connector_pins))
    return evidence


def _connector_group_role_source_evidence(
    group: SimilarConnectorPinGroup,
    observed: NetlistContract,
    reviewed_connector_pins: Mapping[str, ConnectorMappedPinEvidence],
) -> dict[str, tuple[str, ...]]:
    if group.reviewed_role == "supply" and group.reviewed_voltage_domain is not None:
        domain = str(group.reviewed_voltage_domain)
        sources = [
            f"{pin}: project interface catalog role=supply; "
            f"voltage_domain={domain}; "
            f"native symbol function={observed.pin_functions.get(pin) or '<unnamed>'}"
            for pin in sorted(group.pins)
        ]
        return {
            "role_classification_sources": tuple(sources),
            "reviewed_voltage_domain": (domain,),
        }
    if group.function != "ground/return":
        return {}

    sources: list[str] = []
    has_catalog_role = False
    for pin in sorted(group.pins):
        native_function = observed.pin_functions.get(pin) or "<unnamed>"
        mapped = reviewed_connector_pins.get(pin)
        if mapped is not None and mapped.role == "return":
            has_catalog_role = True
            sources.append(
                f"{pin}: project interface catalog role=return; "
                f"native symbol function={native_function}"
            )
        else:
            sources.append(f"{pin}: native symbol function={native_function}")
    if not has_catalog_role:
        return {}
    return {"role_classification_sources": tuple(sources)}


@dataclass(frozen=True, slots=True)
class RepeatedConnectorPinFindingEvidence:
    """A repeated-function scan record with its native and reviewed role context."""

    group: SimilarConnectorPinGroup
    observed: NetlistContract
    reviewed_connector_pins: Mapping[str, ConnectorMappedPinEvidence]
    pin_assignments: Mapping[str, tuple[str, ...]] = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "reviewed_connector_pins",
            MappingProxyType(dict(self.reviewed_connector_pins)),
        )
        object.__setattr__(
            self,
            "pin_assignments",
            MappingProxyType({pin: tuple(nets) for pin, nets in self.group.pins.items()}),
        )


def project_repeated_connector_pin_evidence(
    source: RepeatedConnectorPinFindingEvidence,
) -> CandidateEvidenceProjection:
    """Project a repeated-function record and its role context to stable wire fields."""
    if dict(source.group.pins) != dict(source.pin_assignments):
        raise ValueError("Repeated connector pin assignments changed after source capture")
    evidence = dict(source.pin_assignments)
    evidence.update(
        connector_group_evidence(source.group, source.observed, source.reviewed_connector_pins)
    )
    return CandidateEvidenceProjection(
        rule_id="connector.repeated_pin_function",
        evidence=evidence,
    )


@dataclass(frozen=True, slots=True)
class RepeatedConnectorPinCandidate(Candidate):
    """Internal repeated-function finding retaining its scan and role context."""

    source_evidence: RepeatedConnectorPinFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: RepeatedConnectorPinFindingEvidence,
        *,
        subject: str,
        message: str,
    ) -> RepeatedConnectorPinCandidate:
        projection = project_repeated_connector_pin_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_repeated_connector_pin_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id:
            raise ValueError("Repeated connector pin rule must match its source evidence")
        if self.evidence != projection.evidence:
            raise ValueError("Repeated connector pin evidence must match its source projection")


ConnectorPeerPinAssignmentSource: TypeAlias = (
    ConnectorPeerPinAssignmentOutlier | ConnectorPeerPinAssignmentDivergence
)


def project_connector_peer_pin_assignment_evidence(
    source: ConnectorPeerPinAssignmentSource,
) -> CandidateEvidenceProjection:
    """Project a typed outlier or divergence record without losing peer identity."""
    evidence = dict(source.assignments)
    if isinstance(source, ConnectorPeerPinAssignmentOutlier):
        rule_id = "connector.peer_pin_assignment_outlier"
        evidence["symbol"] = (
            source.peer_symbols if source.peer_identity_basis == "part_id" else (source.symbol,)
        )
        evidence["pin_number"] = (source.pin_number,)
        evidence["outlier_pins"] = source.outlier_pins
    else:
        rule_id = "connector.peer_pin_assignment_divergence"
        evidence["symbol"] = (
            source.peer_symbols if source.peer_identity_basis == "part_id" else (source.symbol,)
        )
        evidence["pin_number"] = (source.pin_number,)
        evidence["missing_pin_function_pins"] = source.missing_function_pins

    if source.peer_identity_basis == "part_id":
        evidence["peer_identity_basis"] = ("part_id",)
        evidence["peer_identity"] = (source.peer_identity,)
        evidence["peer_symbols"] = source.peer_symbols
    if source.peer_assignment_group is not None:
        evidence["peer_assignment_group"] = (source.peer_assignment_group,)
        evidence["peer_assignment_basis"] = source.peer_assignment_basis
    return CandidateEvidenceProjection(rule_id=rule_id, evidence=evidence)


@dataclass(frozen=True, slots=True)
class ConnectorPeerPinAssignmentCandidate(Candidate):
    """Internal generic connector peer finding retaining its typed scan record."""

    source_evidence: ConnectorPeerPinAssignmentSource

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: ConnectorPeerPinAssignmentSource,
        *,
        subject: str,
        message: str,
    ) -> ConnectorPeerPinAssignmentCandidate:
        projection = project_connector_peer_pin_assignment_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_connector_peer_pin_assignment_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id:
            raise ValueError("Connector peer pin rule must match its source evidence")
        if self.evidence != projection.evidence:
            raise ValueError("Connector peer pin evidence must match its source projection")
