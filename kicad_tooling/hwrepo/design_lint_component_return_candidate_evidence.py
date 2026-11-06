"""Typed source evidence and report projection for component return-pin findings."""

from __future__ import annotations

from dataclasses import dataclass

from .connector_identity import connector_candidate_references, is_return_function
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .netlist_contract_models import NetlistContract
from .netlist_pin_assignments import netlist_pin_net_index

_RULE_ID: DesignLintRuleId = "component.repeated_return_pin_function"
_MESSAGE = (
    "Multiple recognized ground or return pins on this fitted component use different "
    "schematic nets. Review whether the split is intentional, such as separate analog and "
    "digital domains, or whether a common or bonded return relationship is missing. This "
    "prompt does not require those nets to be joined."
)


@dataclass(frozen=True, slots=True)
class ComponentReturnPinObservation:
    """One recognized native return pin and its exact net assignments."""

    pin: str
    function: str
    assignments: tuple[str, ...]

    def __post_init__(self) -> None:
        if "." not in self.pin or not self.function:
            raise ValueError("Component return-pin observations need a pin and function")


@dataclass(frozen=True, slots=True)
class ComponentReturnPinFindingEvidence:
    """Native source and connector scope supporting one component return finding."""

    observed: NetlistContract
    declared_connector_references: tuple[str, ...]
    reference: str
    symbol: str
    pins: tuple[ComponentReturnPinObservation, ...]

    def __post_init__(self) -> None:
        reference_key = self.reference.casefold()
        components = {reference.casefold() for reference in self.observed.components}
        unpopulated = {reference.casefold() for reference in self.observed.dnp_components}
        symbols = {
            reference.casefold(): symbol
            for reference, symbol in self.observed.component_symbols.items()
        }
        functions = {
            pin.casefold(): function for pin, function in self.observed.pin_functions.items()
        }
        assignments_by_pin = netlist_pin_net_index(self.observed)

        if reference_key not in components or reference_key in unpopulated:
            raise ValueError("Component return evidence requires a current fitted component")
        if symbols.get(reference_key) != self.symbol:
            raise ValueError("Component return evidence must match the current symbol")
        connector_references = {
            reference.casefold()
            for reference in connector_candidate_references(
                self.observed, self.declared_connector_references
            )
        }
        if reference_key in connector_references:
            raise ValueError("Component return evidence cannot target a connector")
        if len(self.pins) < 2:
            raise ValueError("Component return evidence requires at least two pins")
        if self.pins != tuple(sorted(self.pins, key=lambda item: (item.pin.casefold(), item.pin))):
            raise ValueError("Component return evidence pins must be deterministically ordered")
        if len({pin.pin.casefold() for pin in self.pins}) != len(self.pins):
            raise ValueError("Component return evidence cannot duplicate pins")

        for pin in self.pins:
            if pin.pin.rpartition(".")[0].casefold() != reference_key:
                raise ValueError("Component return evidence pins must belong to its component")
            if functions.get(pin.pin.casefold()) != pin.function or not is_return_function(
                pin.function
            ):
                raise ValueError("Component return-pin function must match the native source")
            current_assignments = tuple(
                sorted(assignments_by_pin.get(pin.pin.casefold(), ()), key=str.casefold)
            )
            if pin.assignments != current_assignments:
                raise ValueError("Component return-pin nets must match the native source")
            if len(pin.assignments) != 1:
                raise ValueError("Component return evidence requires unambiguous pin assignments")

        if len({pin.assignments[0].casefold() for pin in self.pins}) < 2:
            raise ValueError("Component return evidence requires distinct native nets")

    @property
    def subject(self) -> str:
        return f"{self.reference} ({self.symbol}): return pins use distinct nets"


def project_component_return_pin_evidence(
    source: ComponentReturnPinFindingEvidence,
) -> CandidateEvidenceProjection:
    """Project validated native return pins into the stable finding fields."""
    evidence = {pin.pin: pin.assignments for pin in source.pins}
    evidence["component_symbol"] = (source.symbol,)
    evidence["pin_functions"] = tuple(f"{pin.pin}={pin.function}" for pin in source.pins)
    return CandidateEvidenceProjection(rule_id=_RULE_ID, evidence=evidence)


@dataclass(frozen=True, slots=True)
class ComponentReturnPinCandidate(Candidate):
    """Candidate whose stable report mapping is derived from native source."""

    source_evidence: ComponentReturnPinFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: ComponentReturnPinFindingEvidence,
    ) -> ComponentReturnPinCandidate:
        projection = project_component_return_pin_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=source_evidence.subject,
            message=_MESSAGE,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_component_return_pin_evidence(self.source_evidence)
        if (
            self.rule_id != projection.rule_id
            or self.subject != self.source_evidence.subject
            or self.message != _MESSAGE
            or self.evidence != projection.evidence
        ):
            raise ValueError("Component return candidate must match its retained source projection")


def component_return_pin_candidate(
    source: ComponentReturnPinFindingEvidence,
) -> ComponentReturnPinCandidate:
    """Build one policy-neutral candidate from validated component return evidence."""
    return ComponentReturnPinCandidate.from_source_evidence(source)
