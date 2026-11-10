"""Typed source-bound evidence for named mapped peer-supply splits."""

from __future__ import annotations

from dataclasses import dataclass

from .connector_comparison_scope_types import ConnectorComparisonScopes
from .connector_coverage import (
    source_matched_connector_pin_evidence,
    source_matched_connector_supply_comparison_groups,
)
from .connector_coverage_models import (
    ConnectorCoverageReport,
    ConnectorMappedPinEvidence,
    ConnectorMappedPinEvidenceByComponentPin,
)
from .connector_identity import (
    connector_power_function_key,
    is_return_function,
    pin_function_is_generic,
    similar_connector_pin_groups,
)
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .netlist_contract_models import NetlistContract

_RULE_ID: DesignLintRuleId = "connector.mapped_named_peer_supply_split_nets"


def source_matched_legacy_supply_peer_group_pins(
    observed: NetlistContract,
    coverage: ConnectorCoverageReport,
    mapped_pins: ConnectorMappedPinEvidenceByComponentPin,
    supply_scopes: ConnectorComparisonScopes,
) -> frozenset[str]:
    """Return pins whose divergent assignments already enter peer-pin review."""
    groups = similar_connector_pin_groups(
        observed,
        tuple(entry.reference for entry in coverage.entries),
        mapped_pins,
        supply_comparison_groups=supply_scopes,
    )
    return frozenset(pin for group in groups for pin in group.pins)


@dataclass(frozen=True, slots=True)
class MappedNamedPeerSupplySplitAssignment:
    """One current mapped supply contact assigned to one native net."""

    component_pin: str
    native_net: str
    voltage_domain: str
    mapped_pin: ConnectorMappedPinEvidence

    def __post_init__(self) -> None:
        if not self.component_pin or not self.native_net or not self.voltage_domain:
            raise ValueError("Named peer supply assignments need pin, net, and voltage domain")
        if self.mapped_pin.component_pin != self.component_pin:
            raise ValueError("Named peer supply assignment must match its mapped component pin")
        if self.mapped_pin.role != "supply":
            raise ValueError("Named peer supply assignment must carry the supply role")
        if self.mapped_pin.voltage_domain != self.voltage_domain:
            raise ValueError("Named peer supply assignment must match its mapped voltage domain")
        if self.mapped_pin.nets != (self.native_net,) or self.mapped_pin.unconnected_reason:
            raise ValueError("Named peer supply assignment must have one current native net")


@dataclass(frozen=True, slots=True)
class MappedNamedPeerSupplySplit:
    """Named mapped supplies in one reviewed comparison group and voltage domain."""

    supply_comparison_group: str
    voltage_domain: str
    assignments: tuple[MappedNamedPeerSupplySplitAssignment, ...]

    def __post_init__(self) -> None:
        ordered = tuple(sorted(self.assignments, key=lambda item: item.component_pin))
        references = {item.component_pin.rpartition(".")[0] for item in self.assignments}
        pins = tuple(item.component_pin for item in self.assignments)
        functions = tuple(item.mapped_pin.symbol_function for item in self.assignments)
        if not self.supply_comparison_group or not self.voltage_domain:
            raise ValueError("Named peer supply splits require a group and voltage domain")
        if len(references) < 2 or len({item.native_net for item in self.assignments}) < 2:
            raise ValueError("A named peer supply split needs two references on separate nets")
        if self.assignments != ordered or len(pins) != len(set(pins)):
            raise ValueError("Named peer supply assignments must be uniquely and stably ordered")
        if any(item.voltage_domain != self.voltage_domain for item in self.assignments):
            raise ValueError("Named peer supply assignments must use one exact voltage domain")
        if any(
            function is None
            or pin_function_is_generic(function)
            or connector_power_function_key(function) is not None
            or is_return_function(function)
            for function in functions
        ):
            raise ValueError("Named peer supply assignments need meaningful uncategorized labels")


@dataclass(frozen=True, slots=True)
class MappedNamedPeerSupplySplitFindingEvidence:
    """A peer-supply split bound to current connector maps and native nets."""

    observed: NetlistContract
    coverage: ConnectorCoverageReport
    split: MappedNamedPeerSupplySplit

    def __post_init__(self) -> None:
        if self.coverage.status != "COMPLETE" or not self.coverage.interface_catalog_sha256:
            raise ValueError("Named peer supply evidence requires complete catalog coverage")
        current = source_matched_connector_pin_evidence(self.observed, self.coverage)
        scopes = source_matched_connector_supply_comparison_groups(self.observed, self.coverage)
        dnp_references = {reference.casefold() for reference in self.observed.dnp_components}
        participants = {
            component_pin.rpartition(".")[0]
            for component_pin, mapped in current.items()
            if mapped.role == "supply"
            and mapped.voltage_domain == self.split.voltage_domain
            and component_pin.rpartition(".")[0].casefold() not in dnp_references
        }
        if any(reference not in scopes for reference in participants):
            raise ValueError(
                "Every mapped supply peer in this voltage domain needs a current scope"
            )
        legacy_pins = source_matched_legacy_supply_peer_group_pins(
            self.observed,
            self.coverage,
            current,
            scopes,
        )
        for assignment in self.split.assignments:
            reference, separator, _pin_number = assignment.component_pin.rpartition(".")
            if not separator or reference.casefold() in dnp_references:
                raise ValueError("Named peer supply evidence requires fitted connector pins")
            if current.get(assignment.component_pin) != assignment.mapped_pin:
                raise ValueError("Named peer supply assignment must match current source evidence")
            if assignment.component_pin in legacy_pins:
                raise ValueError("Existing peer-pin evidence already covers this assignment")
            scope = scopes.get(reference)
            if scope is None or scope.group != self.split.supply_comparison_group:
                raise ValueError("Named peer supply assignment must match its current review scope")
            function = assignment.mapped_pin.symbol_function
            if (
                function is None
                or pin_function_is_generic(function)
                or connector_power_function_key(function) is not None
                or is_return_function(function)
            ):
                raise ValueError("Named peer supply evidence needs meaningful uncategorized labels")


def project_mapped_named_peer_supply_split_evidence(
    source: MappedNamedPeerSupplySplitFindingEvidence,
) -> CandidateEvidenceProjection:
    """Project the exact peer group, domain, assignments, and catalog digest."""
    assignments = source.split.assignments
    references = tuple(
        sorted(
            {item.component_pin.rpartition(".")[0] for item in assignments},
            key=lambda item: (item.casefold(), item),
        )
    )
    scopes = source_matched_connector_supply_comparison_groups(source.observed, source.coverage)
    bases = tuple(
        sorted(
            {scopes[reference].basis for reference in references if reference in scopes},
            key=lambda item: (item.casefold(), item),
        )
    )
    evidence: dict[str, tuple[str, ...]] = {
        "supply_comparison_group": (source.split.supply_comparison_group,),
        "supply_comparison_basis": bases,
        "voltage_domain": (source.split.voltage_domain,),
        "connector_references": references,
        "split_native_nets": tuple(
            sorted(
                {item.native_net for item in assignments},
                key=lambda item: (item.casefold(), item),
            )
        ),
        "mapped_supply_assignments": tuple(
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
class MappedNamedPeerSupplySplitCandidate(Candidate):
    """Candidate whose report fields are projected from source-matched evidence."""

    source_evidence: MappedNamedPeerSupplySplitFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: MappedNamedPeerSupplySplitFindingEvidence,
        *,
        subject: str,
        message: str,
    ) -> MappedNamedPeerSupplySplitCandidate:
        projection = project_mapped_named_peer_supply_split_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_mapped_named_peer_supply_split_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("Named peer supply candidate fields must match source evidence")
