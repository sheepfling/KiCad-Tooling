"""Typed, source-bound evidence for same-domain connector return splits."""

from __future__ import annotations

from dataclasses import dataclass

from .connector_coverage import source_matched_connector_pin_evidence
from .connector_coverage_models import ConnectorCoverageReport, ConnectorMappedPinEvidence
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .netlist_contract_models import NetlistContract

_RULE_ID: DesignLintRuleId = "connector.mapped_same_domain_return_split_nets"


@dataclass(frozen=True, slots=True)
class MappedReturnDomainSplitAssignment:
    """One current return contact assigned to one native net in a mapped domain."""

    component_pin: str
    native_net: str
    voltage_domain: str
    mapped_pin: ConnectorMappedPinEvidence

    def __post_init__(self) -> None:
        if not self.component_pin or not self.native_net or not self.voltage_domain:
            raise ValueError("Return-domain split assignments require pin, net, and domain")
        if self.mapped_pin.component_pin != self.component_pin:
            raise ValueError("Return-domain assignment must match its mapped component pin")
        if self.mapped_pin.role != "return":
            raise ValueError("Return-domain split evidence must carry the return role")
        if self.mapped_pin.voltage_domain != self.voltage_domain:
            raise ValueError("Return-domain assignment must match its mapped voltage domain")
        if self.mapped_pin.nets != (self.native_net,) or self.mapped_pin.unconnected_reason:
            raise ValueError("Return-domain split assignment must have one current native net")


@dataclass(frozen=True, slots=True)
class MappedReturnDomainSplit:
    """Same-connector return assignments in one authored domain across split nets."""

    component_reference: str
    voltage_domain: str
    assignments: tuple[MappedReturnDomainSplitAssignment, ...]

    def __post_init__(self) -> None:
        expected = tuple(sorted(self.assignments, key=lambda item: item.component_pin))
        references = {item.component_pin.rpartition(".")[0] for item in self.assignments}
        domains = {item.voltage_domain for item in self.assignments}
        nets = {item.native_net for item in self.assignments}
        pins = tuple(item.component_pin for item in self.assignments)
        if not self.component_reference or not self.voltage_domain:
            raise ValueError("Return-domain split groups require a connector and domain")
        if len(self.assignments) < 2 or len(nets) < 2:
            raise ValueError("A return-domain split needs pins assigned across distinct nets")
        if self.assignments != expected or len(pins) != len(set(pins)):
            raise ValueError("Return-domain split assignments must be uniquely and stably ordered")
        if references != {self.component_reference} or domains != {self.voltage_domain}:
            raise ValueError("Return-domain split assignments must match one connector and domain")


@dataclass(frozen=True, slots=True)
class MappedReturnDomainSplitFindingEvidence:
    """A same-domain return split bound to current connector and netlist evidence."""

    observed: NetlistContract
    coverage: ConnectorCoverageReport
    split: MappedReturnDomainSplit

    def __post_init__(self) -> None:
        if self.coverage.status != "COMPLETE" or not self.coverage.interface_catalog_sha256:
            raise ValueError("Return-domain split evidence requires complete catalog coverage")
        current = source_matched_connector_pin_evidence(self.observed, self.coverage)
        dnp_references = {reference.casefold() for reference in self.observed.dnp_components}
        for assignment in self.split.assignments:
            reference, separator, _pin_number = assignment.component_pin.rpartition(".")
            if not separator or reference != self.split.component_reference:
                raise ValueError("Return-domain assignment must match its connector group")
            if reference.casefold() in dnp_references:
                raise ValueError("Unpopulated connectors cannot support return-domain evidence")
            if current.get(assignment.component_pin) != assignment.mapped_pin:
                raise ValueError("Return-domain assignment must match current connector evidence")


def project_mapped_return_domain_split_evidence(
    source: MappedReturnDomainSplitFindingEvidence,
) -> CandidateEvidenceProjection:
    """Project exact pin/net pairs and map identity into stable finding fields."""
    assignments = source.split.assignments
    evidence: dict[str, tuple[str, ...]] = {
        "component_reference": (source.split.component_reference,),
        "interface_role": ("return",),
        "voltage_domain": (source.split.voltage_domain,),
        "split_native_nets": tuple(
            sorted(
                {item.native_net for item in assignments}, key=lambda item: (item.casefold(), item)
            )
        ),
        "mapped_return_assignments": tuple(
            f"{item.component_pin}={item.native_net}; voltage_domain={item.voltage_domain}"
            for item in assignments
        ),
        "interface_catalog_sha256": (str(source.coverage.interface_catalog_sha256),),
    }
    if source.coverage.interface_catalog_path is not None:
        evidence["interface_catalog_path"] = (str(source.coverage.interface_catalog_path),)
    evidence.update({item.component_pin: (item.native_net,) for item in assignments})
    return CandidateEvidenceProjection(rule_id=_RULE_ID, evidence=evidence)


@dataclass(frozen=True, slots=True)
class MappedReturnDomainSplitCandidate(Candidate):
    """Finding candidate whose public fields derive from source-bound evidence."""

    source_evidence: MappedReturnDomainSplitFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: MappedReturnDomainSplitFindingEvidence,
        *,
        subject: str,
        message: str,
    ) -> MappedReturnDomainSplitCandidate:
        projection = project_mapped_return_domain_split_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_mapped_return_domain_split_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("Return-domain split fields must match current source evidence")
