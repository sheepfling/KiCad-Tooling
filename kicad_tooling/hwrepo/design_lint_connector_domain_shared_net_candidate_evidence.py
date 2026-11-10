"""Typed source projections for mapped connector domains sharing a net."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .connector_coverage import source_matched_connector_pin_evidence
from .connector_coverage_models import ConnectorCoverageReport, ConnectorMappedPinEvidence
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .netlist_contract_models import NetlistContract

ConnectorDomainRole = Literal["supply", "return"]
_RULE_BY_ROLE: dict[ConnectorDomainRole, DesignLintRuleId] = {
    "supply": "connector.mapped_supply_domains_share_net",
    "return": "connector.mapped_return_domains_share_net",
}


@dataclass(frozen=True, slots=True)
class MappedConnectorDomainAssignment:
    """One source-matched connector contact assigned to a native net."""

    pin: str
    native_net: str
    voltage_domain: str
    mapped_pin: ConnectorMappedPinEvidence
    interface_role: ConnectorDomainRole = "supply"

    def __post_init__(self) -> None:
        if not self.pin or not self.native_net or not self.voltage_domain:
            raise ValueError("Mapped connector domain assignments need pin, net, and domain")
        if self.mapped_pin.component_pin != self.pin:
            raise ValueError("Mapped connector pin must match its coverage record")
        if self.mapped_pin.role != self.interface_role:
            raise ValueError("Mapped connector role must match its coverage record")
        if self.mapped_pin.voltage_domain != self.voltage_domain:
            raise ValueError("Mapped connector voltage domain must match its coverage record")
        if self.mapped_pin.nets != (self.native_net,) or self.mapped_pin.unconnected_reason:
            raise ValueError("Mapped connector net must match one assigned source record")


@dataclass(frozen=True, slots=True)
class MappedConnectorDomainsSharedNet:
    """One native net assigned to distinct source-mapped connector domains."""

    native_net: str
    voltage_domains: tuple[str, ...]
    assignments: tuple[MappedConnectorDomainAssignment, ...]
    interface_role: ConnectorDomainRole = "supply"

    def __post_init__(self) -> None:
        expected_domains = tuple(sorted({item.voltage_domain for item in self.assignments}))
        expected_assignments = tuple(
            sorted(self.assignments, key=lambda item: (item.voltage_domain, item.pin))
        )
        if (
            not self.native_net
            or len(expected_domains) < 2
            or self.voltage_domains != expected_domains
        ):
            raise ValueError("A shared connector net needs at least two exact authored domains")
        if self.assignments != expected_assignments:
            raise ValueError("Shared connector assignments must retain deterministic order")
        if any(
            item.native_net != self.native_net or item.interface_role != self.interface_role
            for item in self.assignments
        ):
            raise ValueError("Shared connector assignments must match net and role")


@dataclass(frozen=True, slots=True)
class MappedConnectorDomainsFindingEvidence:
    """A shared-domain observation bound to its netlist and connector coverage."""

    observed: NetlistContract
    coverage: ConnectorCoverageReport
    shared_net: MappedConnectorDomainsSharedNet

    def __post_init__(self) -> None:
        if self.coverage.interface_catalog_sha256 is None:
            raise ValueError("Mapped connector-domain evidence needs its interface catalog digest")
        source_pins = source_matched_connector_pin_evidence(self.observed, self.coverage)
        unpopulated = {reference.casefold() for reference in self.observed.dnp_components}
        for assignment in self.shared_net.assignments:
            reference = assignment.pin.rsplit(".", maxsplit=1)[0]
            if reference.casefold() in unpopulated:
                raise ValueError("Unpopulated connector pins cannot support domain evidence")
            if source_pins.get(assignment.pin) != assignment.mapped_pin:
                raise ValueError(
                    "Mapped connector assignment must match current source netlist and coverage"
                )


def project_mapped_connector_domains_shared_net_evidence(
    source: MappedConnectorDomainsFindingEvidence,
) -> CandidateEvidenceProjection:
    """Project exact role, domain, pin, net, and catalog source evidence."""
    shared_net = source.shared_net
    role = shared_net.interface_role
    assignments_key = f"mapped_{role}_assignments"
    evidence: dict[str, tuple[str, ...]] = {
        "native_shared_net": (shared_net.native_net,),
        "reviewed_voltage_domains": shared_net.voltage_domains,
        assignments_key: tuple(
            f"{item.pin}={item.native_net}; voltage_domain={item.voltage_domain}"
            for item in shared_net.assignments
        ),
        "role_classification_sources": tuple(
            (
                f"{item.pin}: source-matched project interface role={role}; "
                f"voltage_domain={item.voltage_domain}; "
                f"signal={item.mapped_pin.interface_signal}; "
                f"native function={item.mapped_pin.symbol_function or '<unnamed>'}"
            )
            for item in shared_net.assignments
        ),
        "interface_catalog_sha256": (str(source.coverage.interface_catalog_sha256),),
    }
    if role == "return":
        evidence["interface_role"] = (role,)
    if source.coverage.interface_catalog_path is not None:
        evidence["interface_catalog_path"] = (str(source.coverage.interface_catalog_path),)
    evidence.update({item.pin: (item.native_net,) for item in shared_net.assignments})
    return CandidateEvidenceProjection(rule_id=_RULE_BY_ROLE[role], evidence=evidence)


@dataclass(frozen=True, slots=True)
class MappedConnectorDomainsCandidate(Candidate):
    """Finding candidate whose public fields derive from typed source evidence."""

    source_evidence: MappedConnectorDomainsFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: MappedConnectorDomainsFindingEvidence,
        *,
        subject: str,
        message: str,
    ) -> MappedConnectorDomainsCandidate:
        projection = project_mapped_connector_domains_shared_net_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_mapped_connector_domains_shared_net_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("Connector-domain fields must match their typed source projection")
