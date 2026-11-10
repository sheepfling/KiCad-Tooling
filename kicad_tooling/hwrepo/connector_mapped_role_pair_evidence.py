"""Typed evidence for source-mapped connector role pairs sharing one net."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from .connector_coverage import source_matched_connector_pin_evidence
from .connector_coverage_models import ConnectorCoverageReport, ConnectorMappedPinEvidence
from .connector_peer_pin_models import ConnectorPinRole
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .netlist_contract_models import NetlistContract

MappedConnectorRolePair: TypeAlias = tuple[ConnectorPinRole, ConnectorPinRole]


@dataclass(frozen=True, slots=True)
class MappedConnectorRolePairAtNet:
    """Current source-matched contacts for two roles on one connector and net."""

    component_reference: str
    net_name: str
    primary_role: ConnectorPinRole
    primary_contacts: tuple[ConnectorMappedPinEvidence, ...]
    secondary_role: ConnectorPinRole
    secondary_contacts: tuple[ConnectorMappedPinEvidence, ...]

    def __post_init__(self) -> None:
        if not self.component_reference or not self.net_name:
            raise ValueError("Mapped connector role pairs require a reference and native net")
        if self.primary_role == self.secondary_role:
            raise ValueError("Mapped connector role-pair roles must be distinct")
        for contacts in (self.primary_contacts, self.secondary_contacts):
            if not contacts or contacts != tuple(
                sorted(contacts, key=lambda item: item.component_pin)
            ):
                raise ValueError("Mapped connector role-pair contacts must be non-empty and sorted")


def mapped_connector_role_pair_groups(
    observed: NetlistContract,
    coverage: ConnectorCoverageReport | None,
    *,
    primary_role: ConnectorPinRole,
    secondary_role: ConnectorPinRole,
) -> tuple[MappedConnectorRolePairAtNet, ...]:
    """Group exact one-net role pairs per fitted connector under complete coverage."""
    if primary_role == secondary_role:
        raise ValueError("Mapped connector role-pair roles must be distinct")
    if coverage is None or coverage.status != "COMPLETE" or not coverage.interface_catalog_sha256:
        return ()

    dnp_references = {reference.casefold() for reference in observed.dnp_components}
    grouped: dict[tuple[str, str], dict[ConnectorPinRole, list[ConnectorMappedPinEvidence]]] = {}
    for mapped in source_matched_connector_pin_evidence(observed, coverage).values():
        if (
            mapped.role not in {primary_role, secondary_role}
            or mapped.unconnected_reason is not None
            or len(mapped.nets) != 1
        ):
            continue
        reference, separator, _pin_number = mapped.component_pin.rpartition(".")
        if not separator or reference.casefold() in dnp_references:
            continue
        roles = grouped.setdefault(
            (reference, mapped.nets[0]),
            {primary_role: [], secondary_role: []},
        )
        roles[mapped.role].append(mapped)

    result: list[MappedConnectorRolePairAtNet] = []
    for (reference, net_name), roles in sorted(
        grouped.items(),
        key=lambda item: (
            item[0][0].casefold(),
            item[0][1].casefold(),
            item[0][0],
            item[0][1],
        ),
    ):
        primary = tuple(sorted(roles[primary_role], key=lambda item: item.component_pin))
        secondary = tuple(sorted(roles[secondary_role], key=lambda item: item.component_pin))
        if primary and secondary:
            result.append(
                MappedConnectorRolePairAtNet(
                    component_reference=reference,
                    net_name=net_name,
                    primary_role=primary_role,
                    primary_contacts=primary,
                    secondary_role=secondary_role,
                    secondary_contacts=secondary,
                )
            )
    return tuple(result)


@dataclass(frozen=True, slots=True)
class MappedConnectorRolePairFindingEvidence:
    """A role pair bound to the current netlist and complete interface catalog."""

    observed: NetlistContract
    coverage: ConnectorCoverageReport
    contacts: MappedConnectorRolePairAtNet

    def __post_init__(self) -> None:
        if self.coverage.status != "COMPLETE" or not self.coverage.interface_catalog_sha256:
            raise ValueError("Mapped connector role pairs require complete catalog evidence")
        current = source_matched_connector_pin_evidence(self.observed, self.coverage)
        dnp_references = {reference.casefold() for reference in self.observed.dnp_components}
        for role, contacts in (
            (self.contacts.primary_role, self.contacts.primary_contacts),
            (self.contacts.secondary_role, self.contacts.secondary_contacts),
        ):
            for mapped in contacts:
                if current.get(mapped.component_pin) != mapped:
                    raise ValueError("Mapped connector contacts must match current coverage")
                reference, separator, _pin_number = mapped.component_pin.rpartition(".")
                if not separator or reference != self.contacts.component_reference:
                    raise ValueError("Mapped connector contacts must match their component group")
                if reference.casefold() in dnp_references:
                    raise ValueError("Unpopulated connectors cannot support role-pair findings")
                if mapped.role != role:
                    raise ValueError(
                        "Mapped connector contact role differs from its role-pair group"
                    )
                if mapped.unconnected_reason is not None or mapped.nets != (
                    self.contacts.net_name,
                ):
                    raise ValueError("Mapped connector role-pair contacts must share one exact net")


def project_mapped_connector_role_pair_evidence(
    source: MappedConnectorRolePairFindingEvidence,
    *,
    rule_id: DesignLintRuleId,
) -> CandidateEvidenceProjection:
    """Project role-specific pins, signals, net, and catalog digest deterministically."""
    contacts = source.contacts
    evidence: dict[str, tuple[str, ...]] = {
        "component_reference": (contacts.component_reference,),
        "interface_role": (contacts.primary_role, contacts.secondary_role),
        "assigned_net": (contacts.net_name,),
        "interface_catalog_sha256": (str(source.coverage.interface_catalog_sha256),),
    }
    for role, pins in (
        (contacts.primary_role, contacts.primary_contacts),
        (contacts.secondary_role, contacts.secondary_contacts),
    ):
        evidence[f"{role}_component_pin"] = tuple(item.component_pin for item in pins)
        evidence[f"{role}_interface_signal"] = tuple(
            sorted(
                {item.interface_signal for item in pins}, key=lambda item: (item.casefold(), item)
            )
        )
    return CandidateEvidenceProjection(rule_id=rule_id, evidence=evidence)


@dataclass(frozen=True, slots=True)
class MappedConnectorRolePairCandidate(Candidate):
    """Rule candidate whose report fields are projected from current source records."""

    source_evidence: MappedConnectorRolePairFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: MappedConnectorRolePairFindingEvidence,
        *,
        rule_id: DesignLintRuleId,
        subject: str,
        message: str,
    ) -> MappedConnectorRolePairCandidate:
        projection = project_mapped_connector_role_pair_evidence(
            source_evidence,
            rule_id=rule_id,
        )
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_mapped_connector_role_pair_evidence(
            self.source_evidence,
            rule_id=self.rule_id,
        )
        if self.evidence != projection.evidence:
            raise ValueError("Mapped connector role-pair fields must match current source evidence")
