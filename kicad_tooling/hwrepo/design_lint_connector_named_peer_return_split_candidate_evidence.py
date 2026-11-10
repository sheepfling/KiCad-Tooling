"""Typed source-bound evidence for named mapped peer-return splits."""

from __future__ import annotations

from dataclasses import dataclass

from .connector_comparison_scope_types import ConnectorComparisonScopes
from .connector_coverage import (
    source_matched_connector_pin_evidence,
    source_matched_connector_return_comparison_groups,
)
from .connector_coverage_models import (
    ConnectorCoverageReport,
    ConnectorMappedPinEvidenceByComponentPin,
)
from .connector_identity import (
    is_return_function,
    pin_function_is_generic,
    similar_connector_pin_groups,
)
from .design_lint_return_domain_split_candidate_evidence import (
    MappedReturnDomainSplitAssignment,
)
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .netlist_contract_models import NetlistContract

_RULE_ID: DesignLintRuleId = "connector.mapped_named_peer_return_split_nets"


def source_matched_legacy_return_peer_group_pins(
    observed: NetlistContract,
    coverage: ConnectorCoverageReport,
    mapped_pins: ConnectorMappedPinEvidenceByComponentPin,
    return_scopes: ConnectorComparisonScopes,
) -> frozenset[str]:
    """Return pins already covered by the existing repeated-return prompt."""
    groups = similar_connector_pin_groups(
        observed,
        tuple(entry.reference for entry in coverage.entries),
        mapped_pins,
        return_comparison_groups=return_scopes,
    )
    return frozenset(
        pin for group in groups if group.function == "ground/return" for pin in group.pins
    )


@dataclass(frozen=True, slots=True)
class MappedNamedPeerReturnSplit:
    """Named return contacts in one reviewed peer scope and domain across split nets."""

    return_comparison_group: str
    voltage_domain: str
    assignments: tuple[MappedReturnDomainSplitAssignment, ...]

    def __post_init__(self) -> None:
        expected = tuple(sorted(self.assignments, key=lambda item: item.component_pin))
        references = {item.component_pin.rpartition(".")[0] for item in self.assignments}
        pins = tuple(item.component_pin for item in self.assignments)
        native_functions = tuple(item.mapped_pin.symbol_function for item in self.assignments)
        if not self.return_comparison_group or not self.voltage_domain:
            raise ValueError("Named peer return splits require a group and voltage domain")
        if len(references) < 2 or len({item.native_net for item in self.assignments}) < 2:
            raise ValueError("A named peer return split needs two references on separate nets")
        if self.assignments != expected or len(pins) != len(set(pins)):
            raise ValueError("Named peer return assignments must be uniquely and stably ordered")
        if any(item.voltage_domain != self.voltage_domain for item in self.assignments):
            raise ValueError("Named peer return assignments must use one exact voltage domain")
        if any(
            function is None or pin_function_is_generic(function) or is_return_function(function)
            for function in native_functions
        ):
            raise ValueError("Named peer return assignments require meaningful non-return labels")


@dataclass(frozen=True, slots=True)
class MappedNamedPeerReturnSplitFindingEvidence:
    """A mapped peer-return split bound to current connector and native-net evidence."""

    observed: NetlistContract
    coverage: ConnectorCoverageReport
    split: MappedNamedPeerReturnSplit

    def __post_init__(self) -> None:
        if self.coverage.status != "COMPLETE" or not self.coverage.interface_catalog_sha256:
            raise ValueError("Named peer return evidence requires complete catalog coverage")
        current = source_matched_connector_pin_evidence(self.observed, self.coverage)
        scopes = source_matched_connector_return_comparison_groups(self.observed, self.coverage)
        dnp_references = {reference.casefold() for reference in self.observed.dnp_components}
        participants = {
            component_pin.rpartition(".")[0]
            for component_pin, mapped in current.items()
            if mapped.role == "return"
            and mapped.voltage_domain == self.split.voltage_domain
            and component_pin.rpartition(".")[0].casefold() not in dnp_references
        }
        if any(reference not in scopes for reference in participants):
            raise ValueError(
                "Every mapped return peer in this voltage domain needs a current scope"
            )
        legacy_pins = source_matched_legacy_return_peer_group_pins(
            self.observed,
            self.coverage,
            current,
            scopes,
        )
        for assignment in self.split.assignments:
            reference, separator, _pin_number = assignment.component_pin.rpartition(".")
            if not separator or reference.casefold() in dnp_references:
                raise ValueError("Named peer return evidence requires fitted connector pins")
            if current.get(assignment.component_pin) != assignment.mapped_pin:
                raise ValueError("Named peer return assignment must match current source evidence")
            if assignment.component_pin in legacy_pins:
                raise ValueError("Existing return-peer evidence already covers this assignment")
            scope = scopes.get(reference)
            if scope is None or scope.group != self.split.return_comparison_group:
                raise ValueError("Named peer return assignment must match its current review scope")
            function = assignment.mapped_pin.symbol_function
            if (
                function is None
                or pin_function_is_generic(function)
                or is_return_function(function)
            ):
                raise ValueError("Named peer return evidence needs meaningful non-return labels")


def project_mapped_named_peer_return_split_evidence(
    source: MappedNamedPeerReturnSplitFindingEvidence,
) -> CandidateEvidenceProjection:
    """Project the exact peer scope, domain, assignments, and catalog identity."""
    assignments = source.split.assignments
    references = tuple(
        sorted(
            {item.component_pin.rpartition(".")[0] for item in assignments},
            key=lambda item: (item.casefold(), item),
        )
    )
    scopes = source_matched_connector_return_comparison_groups(source.observed, source.coverage)
    bases = tuple(
        sorted(
            {scopes[reference].basis for reference in references if reference in scopes},
            key=lambda item: (item.casefold(), item),
        )
    )
    evidence: dict[str, tuple[str, ...]] = {
        "return_comparison_group": (source.split.return_comparison_group,),
        "return_comparison_basis": bases,
        "voltage_domain": (source.split.voltage_domain,),
        "connector_references": references,
        "split_native_nets": tuple(
            sorted(
                {item.native_net for item in assignments},
                key=lambda item: (item.casefold(), item),
            )
        ),
        "mapped_return_assignments": tuple(
            f"{item.component_pin}={item.native_net}; voltage_domain={item.voltage_domain}; "
            f"native_function={item.mapped_pin.symbol_function}"
            for item in assignments
        ),
        "interface_catalog_sha256": (str(source.coverage.interface_catalog_sha256),),
    }
    if source.coverage.interface_catalog_path is not None:
        evidence["interface_catalog_path"] = (str(source.coverage.interface_catalog_path),)
    evidence.update({item.component_pin: (item.native_net,) for item in assignments})
    return CandidateEvidenceProjection(rule_id=_RULE_ID, evidence=evidence)


@dataclass(frozen=True, slots=True)
class MappedNamedPeerReturnSplitCandidate(Candidate):
    """Finding candidate whose report fields derive from current source evidence."""

    source_evidence: MappedNamedPeerReturnSplitFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: MappedNamedPeerReturnSplitFindingEvidence,
        *,
        subject: str,
        message: str,
    ) -> MappedNamedPeerReturnSplitCandidate:
        projection = project_mapped_named_peer_return_split_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_mapped_named_peer_return_split_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("Named peer return candidate fields must match source evidence")
