"""Typed source-bound evidence for named mapped peer-signal splits."""

from __future__ import annotations

from dataclasses import dataclass

from .connector_comparison_scope_types import ConnectorComparisonScopes
from .connector_coverage import (
    source_matched_connector_peer_assignment_groups,
    source_matched_connector_pin_evidence,
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

_RULE_ID: DesignLintRuleId = "connector.mapped_named_peer_signal_split_nets"


def source_matched_legacy_named_peer_signal_pins(
    observed: NetlistContract,
    coverage: ConnectorCoverageReport,
    mapped_pins: ConnectorMappedPinEvidenceByComponentPin,
    peer_scopes: ConnectorComparisonScopes,
) -> frozenset[str]:
    """Return pins whose same-symbol/native-function comparison already reviews them."""
    groups = similar_connector_pin_groups(
        observed,
        tuple(entry.reference for entry in coverage.entries),
        mapped_pins,
        peer_assignment_groups=peer_scopes,
    )
    return frozenset(pin for group in groups for pin in group.pins)


@dataclass(frozen=True, slots=True)
class MappedNamedPeerSignalSplitAssignment:
    """One current mapped signal contact assigned to one native net."""

    component_pin: str
    native_net: str
    interface_signal: str
    voltage_domain: str
    mapped_pin: ConnectorMappedPinEvidence

    def __post_init__(self) -> None:
        if not self.component_pin or not self.native_net:
            raise ValueError("Named peer signal assignments need a pin and native net")
        if not self.interface_signal or not self.voltage_domain:
            raise ValueError("Named peer signal assignments need signal and domain labels")
        if self.mapped_pin.component_pin != self.component_pin:
            raise ValueError("Named peer signal assignment must match its mapped component pin")
        if self.mapped_pin.role != "signal":
            raise ValueError("Named peer signal assignment must carry the signal role")
        if self.mapped_pin.interface_signal.strip() != self.interface_signal.strip():
            raise ValueError("Named peer signal assignment must match its mapped signal")
        if (self.mapped_pin.voltage_domain or "").strip() != self.voltage_domain.strip():
            raise ValueError("Named peer signal assignment must match its mapped voltage domain")
        if self.mapped_pin.nets != (self.native_net,) or self.mapped_pin.unconnected_reason:
            raise ValueError("Named peer signal assignment must have one current native net")
        function = self.mapped_pin.symbol_function
        if (
            function is None
            or pin_function_is_generic(function)
            or connector_power_function_key(function) is not None
            or is_return_function(function)
        ):
            raise ValueError("Named peer signal assignment needs a meaningful signal label")


@dataclass(frozen=True, slots=True)
class MappedNamedPeerSignalSplit:
    """Named mapped peer signals in one reviewed group and voltage domain."""

    peer_assignment_group: str
    interface_signal: str
    voltage_domain: str
    assignments: tuple[MappedNamedPeerSignalSplitAssignment, ...]

    def __post_init__(self) -> None:
        ordered = tuple(
            sorted(
                self.assignments,
                key=lambda item: (item.component_pin.casefold(), item.component_pin),
            )
        )
        pins = tuple(item.component_pin for item in self.assignments)
        references = {item.component_pin.rpartition(".")[0].casefold() for item in self.assignments}
        assignments_by_reference: dict[str, int] = {}
        for item in self.assignments:
            reference = item.component_pin.rpartition(".")[0].casefold()
            assignments_by_reference[reference] = assignments_by_reference.get(reference, 0) + 1
        if not self.peer_assignment_group or not self.interface_signal or not self.voltage_domain:
            raise ValueError("Named peer signal splits need group, signal, and domain labels")
        if (
            len(references) < 2
            or any(count != 1 for count in assignments_by_reference.values())
            or len({item.native_net for item in self.assignments}) < 2
        ):
            raise ValueError("A named peer signal split needs two references on separate nets")
        if self.assignments != ordered or len(pins) != len(set(pins)):
            raise ValueError("Named peer signal assignments must be uniquely and stably ordered")
        if any(
            item.interface_signal.strip() != self.interface_signal.strip()
            or item.voltage_domain.strip() != self.voltage_domain.strip()
            for item in self.assignments
        ):
            raise ValueError("Named peer signal assignments must use one signal and domain")


@dataclass(frozen=True, slots=True)
class MappedNamedPeerSignalSplitFindingEvidence:
    """A peer-signal split bound to current connector maps and native nets."""

    observed: NetlistContract
    coverage: ConnectorCoverageReport
    split: MappedNamedPeerSignalSplit

    def __post_init__(self) -> None:
        if self.coverage.status != "COMPLETE" or not self.coverage.interface_catalog_sha256:
            raise ValueError("Named peer signal evidence requires complete catalog coverage")
        current = source_matched_connector_pin_evidence(self.observed, self.coverage)
        scopes = source_matched_connector_peer_assignment_groups(self.observed, self.coverage)
        dnp_references = {reference.casefold() for reference in self.observed.dnp_components}
        signal_key = self.split.interface_signal.strip()
        domain_key = self.split.voltage_domain.strip()
        participants: set[str] = set()
        expected_pins: set[str] = set()
        for component_pin, mapped in current.items():
            reference, separator, _pin_number = component_pin.rpartition(".")
            if (
                not separator
                or reference.casefold() in dnp_references
                or mapped.role != "signal"
                or mapped.interface_signal.strip() != signal_key
                or (mapped.voltage_domain or "").strip() != domain_key
            ):
                continue
            participants.add(reference)
            scope = scopes.get(reference)
            if scope is None:
                raise ValueError("Every mapped peer signal in this domain needs a current scope")
            if scope.group == self.split.peer_assignment_group:
                expected_pins.add(component_pin)

        assignments_by_pin = {item.component_pin: item for item in self.split.assignments}
        if expected_pins != set(assignments_by_pin):
            raise ValueError(
                "Named peer signal assignments must cover the complete current peer set"
            )
        if len(participants) < 2:
            raise ValueError("Named peer signal evidence requires multiple mapped references")

        legacy_pins = source_matched_legacy_named_peer_signal_pins(
            self.observed,
            self.coverage,
            current,
            scopes,
        )
        symbols_by_pin: dict[str, str] = {}
        nets_by_symbol: dict[str, set[str]] = {}
        for assignment in self.split.assignments:
            reference, separator, _pin_number = assignment.component_pin.rpartition(".")
            if not separator or reference.casefold() in dnp_references:
                raise ValueError("Named peer signal evidence requires fitted connector pins")
            if current.get(assignment.component_pin) != assignment.mapped_pin:
                raise ValueError("Named peer signal assignment must match current source evidence")
            scope = scopes.get(reference)
            if scope is None or scope.group != self.split.peer_assignment_group:
                raise ValueError("Named peer signal assignment must match its current review scope")
            if assignment.component_pin in legacy_pins:
                raise ValueError("Existing connector peer evidence already covers this assignment")
            function = assignment.mapped_pin.symbol_function
            if (
                function is None
                or pin_function_is_generic(function)
                or connector_power_function_key(function) is not None
                or is_return_function(function)
            ):
                raise ValueError("Named peer signal evidence needs a meaningful signal label")
            symbol = self.observed.component_symbols.get(reference, "").strip()
            if not symbol:
                raise ValueError("Named peer signal evidence requires native connector symbols")
            symbols_by_pin[assignment.component_pin] = symbol.casefold()
            nets_by_symbol.setdefault(symbol.casefold(), set()).add(assignment.native_net)

        if len(set(symbols_by_pin.values())) < 2:
            raise ValueError("Named peer signal evidence requires unlike native symbols")
        if any(len(nets) > 1 for nets in nets_by_symbol.values()):
            raise ValueError("Same-symbol peer splits remain with existing connector checks")


def project_mapped_named_peer_signal_split_evidence(
    source: MappedNamedPeerSignalSplitFindingEvidence,
) -> CandidateEvidenceProjection:
    """Project the exact peer group, signal, assignments, and catalog digest."""
    assignments = source.split.assignments
    references = tuple(
        sorted(
            {item.component_pin.rpartition(".")[0] for item in assignments},
            key=lambda item: (item.casefold(), item),
        )
    )
    scopes = source_matched_connector_peer_assignment_groups(source.observed, source.coverage)
    bases = tuple(
        sorted(
            {scopes[reference].basis for reference in references if reference in scopes},
            key=lambda item: (item.casefold(), item),
        )
    )
    evidence: dict[str, tuple[str, ...]] = {
        "peer_assignment_group": (source.split.peer_assignment_group,),
        "peer_assignment_basis": bases,
        "interface_signal": (source.split.interface_signal,),
        "voltage_domain": (source.split.voltage_domain,),
        "connector_references": references,
        "component_pin": tuple(item.component_pin for item in assignments),
        "split_native_nets": tuple(
            sorted(
                {item.native_net for item in assignments},
                key=lambda item: (item.casefold(), item),
            )
        ),
        "mapped_signal_assignments": tuple(
            f"{item.component_pin}={item.native_net}; interface_signal={item.interface_signal}; "
            f"voltage_domain={item.voltage_domain}; native_function={item.mapped_pin.symbol_function}"
            for item in assignments
        ),
        "interface_catalog_sha256": (str(source.coverage.interface_catalog_sha256),),
    }
    if source.coverage.interface_catalog_path is not None:
        evidence["interface_catalog_path"] = (str(source.coverage.interface_catalog_path),)
    evidence.update({item.component_pin: (item.native_net,) for item in assignments})
    return CandidateEvidenceProjection(rule_id=_RULE_ID, evidence=evidence)


@dataclass(frozen=True, slots=True)
class MappedNamedPeerSignalSplitCandidate(Candidate):
    """Candidate whose report fields are projected from source-matched evidence."""

    source_evidence: MappedNamedPeerSignalSplitFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: MappedNamedPeerSignalSplitFindingEvidence,
        *,
        subject: str,
        message: str,
    ) -> MappedNamedPeerSignalSplitCandidate:
        projection = project_mapped_named_peer_signal_split_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_mapped_named_peer_signal_split_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("Named peer signal candidate fields must match source evidence")
