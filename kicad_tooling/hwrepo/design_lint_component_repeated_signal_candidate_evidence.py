"""Source records and report projection for repeated component signal pins."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeAlias

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .netlist_contract_models import NetlistContract
from .netlist_pin_assignments import netlist_pin_net_index

RepeatedSignalFindingKind: TypeAlias = Literal["divergent", "unassigned"]


@dataclass(frozen=True, slots=True)
class RepeatedSignalPin:
    """One native pin with its explicit function and exact net assignments."""

    pin: str
    function: str
    assignments: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RepeatedSignalPinGroup:
    """Current pins sharing one explicit native function and electrical type."""

    reference: str
    symbol: str
    function: str
    electrical_type: str
    pins: tuple[RepeatedSignalPin, ...]

    def __post_init__(self) -> None:
        if not self.reference or not self.symbol or not self.function:
            raise ValueError("Repeated signal groups require component identity and pin function")
        if len(self.pins) < 2:
            raise ValueError("Repeated signal groups require at least two pins")
        if self.pins != tuple(sorted(self.pins, key=lambda item: (item.pin.casefold(), item.pin))):
            raise ValueError("Repeated signal pins must be ordered by component pin")
        if len({pin.pin.casefold() for pin in self.pins}) != len(self.pins):
            raise ValueError("Repeated signal groups cannot duplicate native pins")
        normalized_function = " ".join(self.function.casefold().split())
        if any(
            " ".join(pin.function.casefold().split()) != normalized_function for pin in self.pins
        ):
            raise ValueError("Repeated signal pins must share one normalized native function")


@dataclass(frozen=True, slots=True)
class RepeatedSignalPinFindingEvidence:
    """Typed native source for either repeated-pin review finding."""

    observed: NetlistContract
    group: RepeatedSignalPinGroup
    finding_kind: RepeatedSignalFindingKind
    assigned_signal_pins: tuple[str, ...] = ()
    unassigned_signal_pins: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        reference_key = self.group.reference.casefold()
        components = {reference.casefold() for reference in self.observed.components}
        symbols = {
            reference.casefold(): symbol
            for reference, symbol in self.observed.component_symbols.items()
        }
        dnp_references = {reference.casefold() for reference in self.observed.dnp_components}
        functions = {
            pin.casefold(): function for pin, function in self.observed.pin_functions.items()
        }
        electrical_types = {
            pin.casefold(): value.strip().casefold().replace("-", "_")
            for pin, value in self.observed.pin_electrical_types.items()
        }
        nets_by_pin = netlist_pin_net_index(self.observed)

        if reference_key not in components or reference_key in dnp_references:
            raise ValueError("Repeated signal evidence requires a current fitted component")
        if symbols.get(reference_key) != self.group.symbol:
            raise ValueError("Repeated signal evidence must match the current component symbol")
        for pin in self.group.pins:
            pin_key = pin.pin.casefold()
            if pin.pin.rpartition(".")[0].casefold() != reference_key:
                raise ValueError("Repeated signal pins must belong to the retained component")
            if functions.get(pin_key) != pin.function:
                raise ValueError("Repeated signal pin function must match the current netlist")
            if electrical_types.get(pin_key) != self.group.electrical_type:
                raise ValueError("Repeated signal pin type must match the current netlist")
            current_assignments = tuple(
                sorted(nets_by_pin.get(pin_key, ()), key=lambda item: (item.casefold(), item))
            )
            if pin.assignments != current_assignments:
                raise ValueError("Repeated signal pin nets must match the current netlist")

        assigned = tuple(pin.pin for pin in self.group.pins if pin.assignments)
        unassigned = tuple(pin.pin for pin in self.group.pins if not pin.assignments)
        if self.finding_kind == "divergent":
            nets = tuple(pin.assignments for pin in self.group.pins)
            if (
                any(len(assignments) != 1 for assignments in nets)
                or len({assignments[0].casefold() for assignments in nets}) < 2
                or self.assigned_signal_pins
                or self.unassigned_signal_pins
            ):
                raise ValueError(
                    "Divergent findings require uniquely assigned pins on distinct nets"
                )
        elif (
            any(len(pin.assignments) > 1 for pin in self.group.pins)
            or not assigned
            or not unassigned
            or self.assigned_signal_pins != assigned
            or self.unassigned_signal_pins != unassigned
        ):
            raise ValueError("Unassigned findings require exact assigned and open pin lists")


def project_repeated_signal_pin_evidence(
    source: RepeatedSignalPinFindingEvidence,
) -> CandidateEvidenceProjection:
    """Project the retained pin group into the established report fields."""
    evidence = {pin.pin: pin.assignments for pin in source.group.pins}
    evidence["component_symbol"] = (source.group.symbol,)
    evidence["pin_function"] = (source.group.function,)
    evidence["electrical_type"] = (source.group.electrical_type,)
    if source.finding_kind == "unassigned":
        evidence["assigned_signal_pins"] = source.assigned_signal_pins
        evidence["unassigned_signal_pins"] = source.unassigned_signal_pins
        rule_id: DesignLintRuleId = "component.repeated_signal_pin_unassigned"
    else:
        rule_id = "component.repeated_signal_pin_assignment_divergence"
    return CandidateEvidenceProjection(rule_id=rule_id, evidence=evidence)


@dataclass(frozen=True, slots=True)
class RepeatedSignalPinCandidate(Candidate):
    """Candidate whose evidence is projected from current repeated-pin source."""

    source_evidence: RepeatedSignalPinFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: RepeatedSignalPinFindingEvidence,
        *,
        subject: str,
        message: str,
    ) -> RepeatedSignalPinCandidate:
        projection = project_repeated_signal_pin_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_repeated_signal_pin_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("Repeated signal candidate must match its typed source projection")
