"""Typed source projections for mapped connector supply-domain candidates."""

from __future__ import annotations

from dataclasses import dataclass

from .connector_coverage import source_matched_connector_pin_evidence
from .connector_coverage_models import ConnectorCoverageReport, ConnectorMappedPinEvidence
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .netlist_contract_models import NetlistContract

_SUPPLY_DOMAINS_SHARE_NET: DesignLintRuleId = "connector.mapped_supply_domains_share_net"


@dataclass(frozen=True, slots=True)
class MappedSupplyDomainAssignment:
    """One source-matched connector pin classified in a voltage domain."""

    pin: str
    native_net: str
    voltage_domain: str
    mapped_pin: ConnectorMappedPinEvidence

    def __post_init__(self) -> None:
        if self.mapped_pin.component_pin != self.pin:
            raise ValueError("Mapped supply pin must match its coverage record")
        if self.mapped_pin.role != "supply":
            raise ValueError("Mapped supply evidence must carry the supply role")
        if self.mapped_pin.voltage_domain != self.voltage_domain:
            raise ValueError("Mapped supply voltage domain must match its coverage record")
        if self.mapped_pin.nets != (self.native_net,):
            raise ValueError("Mapped supply net must match its source coverage record")


@dataclass(frozen=True, slots=True)
class MappedSupplyDomainsSharedNet:
    """One native net with complete source-matched supply domains and pin records."""

    native_net: str
    voltage_domains: tuple[str, ...]
    assignments: tuple[MappedSupplyDomainAssignment, ...]

    def __post_init__(self) -> None:
        expected_domains = tuple(sorted({item.voltage_domain for item in self.assignments}))
        expected_assignments = tuple(
            sorted(self.assignments, key=lambda item: (item.voltage_domain, item.pin))
        )
        if len(expected_domains) < 2 or self.voltage_domains != expected_domains:
            raise ValueError("A shared supply net needs its exact ordered voltage domains")
        if self.assignments != expected_assignments:
            raise ValueError("Shared supply assignments must retain deterministic order")
        if any(item.native_net != self.native_net for item in self.assignments):
            raise ValueError("Shared supply assignments must match the grouped native net")


@dataclass(frozen=True, slots=True)
class MappedSupplyDomainsFindingEvidence:
    """One shared-domain observation bound to its netlist and connector coverage."""

    observed: NetlistContract
    coverage: ConnectorCoverageReport
    shared_net: MappedSupplyDomainsSharedNet

    def __post_init__(self) -> None:
        if self.coverage.interface_catalog_sha256 is None:
            raise ValueError("Mapped supply-domain evidence needs its interface catalog digest")
        source_pins = source_matched_connector_pin_evidence(self.observed, self.coverage)
        unpopulated = {reference.casefold() for reference in self.observed.dnp_components}
        for assignment in self.shared_net.assignments:
            reference = assignment.pin.rsplit(".", maxsplit=1)[0]
            if reference.casefold() in unpopulated:
                raise ValueError("Unpopulated connector pins cannot support supply-domain evidence")
            if source_pins.get(assignment.pin) != assignment.mapped_pin:
                raise ValueError("Mapped supply assignment must match its current source netlist")


def project_mapped_supply_domains_evidence(
    source: MappedSupplyDomainsFindingEvidence,
) -> CandidateEvidenceProjection:
    """Project the source-matched shared domain record into existing report fields."""
    evidence = {
        "native_shared_net": (source.shared_net.native_net,),
        "reviewed_voltage_domains": source.shared_net.voltage_domains,
        "mapped_supply_assignments": tuple(
            f"{item.pin}={item.native_net}; voltage_domain={item.voltage_domain}"
            for item in source.shared_net.assignments
        ),
        "role_classification_sources": tuple(
            (
                f"{item.pin}: source-matched project interface role=supply; "
                f"voltage_domain={item.voltage_domain}; "
                f"signal={item.mapped_pin.interface_signal}; "
                f"native function={item.mapped_pin.symbol_function or '<unnamed>'}"
            )
            for item in source.shared_net.assignments
        ),
        "interface_catalog_sha256": (str(source.coverage.interface_catalog_sha256),),
    }
    if source.coverage.interface_catalog_path is not None:
        evidence["interface_catalog_path"] = (str(source.coverage.interface_catalog_path),)
    evidence.update({item.pin: (item.native_net,) for item in source.shared_net.assignments})
    return CandidateEvidenceProjection(
        rule_id=_SUPPLY_DOMAINS_SHARE_NET,
        evidence=evidence,
    )


@dataclass(frozen=True, slots=True)
class MappedSupplyDomainsCandidate(Candidate):
    """Connector supply-domain review retaining the exact source coverage records."""

    source_evidence: MappedSupplyDomainsFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: MappedSupplyDomainsFindingEvidence,
        *,
        subject: str,
        message: str,
    ) -> MappedSupplyDomainsCandidate:
        projection = project_mapped_supply_domains_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_mapped_supply_domains_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("Supply-domain fields must match their typed source projection")
