"""Source-bound candidate projections for diode and polarized-capacitor polarity."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from .component_diode_symbols import diode_terminal_numbers
from .component_named_rail_terminal import (
    NamedRailTerminalEvidence,
    validate_named_rail_terminal,
)
from .component_polarized_capacitor_symbols import polarized_capacitor_terminal_numbers
from .component_rail_potentials import potential_is_lower
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .netlist_contract_models import NetlistContract

DIODE_RAIL_ORIENTATION_RULE_ID: DesignLintRuleId = (
    "component.diode_anode_below_cathode_on_named_rails"
)
POLARIZED_CAPACITOR_RAIL_ORIENTATION_RULE_ID: DesignLintRuleId = (
    "component.polarized_capacitor_reversed_on_named_rails"
)


@dataclass(frozen=True, slots=True)
class DiodeRailOrientationEvidence:
    """Current fitted diode identity and source-bound anode/cathode rail evidence."""

    observed: NetlistContract
    reference: str
    symbol: str
    anode: NamedRailTerminalEvidence
    cathode: NamedRailTerminalEvidence

    def __post_init__(self) -> None:
        inventory = _current_component_inventory(
            self.observed,
            reference=self.reference,
            symbol=self.symbol,
        )
        roles = diode_terminal_numbers(
            self.reference,
            self.symbol,
            inventory,
            self.observed.pin_functions,
        )
        if roles is None:
            raise ValueError(
                "Diode evidence requires a supported symbol and unique native A/K roles"
            )
        validate_named_rail_terminal(
            self.observed,
            self.anode,
            expected_pin=f"{self.reference}.{roles.anode}",
        )
        validate_named_rail_terminal(
            self.observed,
            self.cathode,
            expected_pin=f"{self.reference}.{roles.cathode}",
        )
        if not potential_is_lower(self.anode.potential, self.cathode.potential):
            raise ValueError("Diode evidence must retain an anode below its cathode")


@dataclass(frozen=True, slots=True)
class PolarizedCapacitorRailOrientationEvidence:
    """Current fitted polarized-capacitor identity and source-bound terminal rails."""

    observed: NetlistContract
    reference: str
    symbol: str
    positive: NamedRailTerminalEvidence
    negative: NamedRailTerminalEvidence

    def __post_init__(self) -> None:
        inventory = _current_component_inventory(
            self.observed,
            reference=self.reference,
            symbol=self.symbol,
        )
        roles = polarized_capacitor_terminal_numbers(self.symbol, inventory)
        if roles is None:
            raise ValueError(
                "Polarized-capacitor evidence requires the complete native 1/2 inventory"
            )
        validate_named_rail_terminal(
            self.observed,
            self.positive,
            expected_pin=f"{self.reference}.{roles.positive}",
        )
        validate_named_rail_terminal(
            self.observed,
            self.negative,
            expected_pin=f"{self.reference}.{roles.negative}",
        )
        if not potential_is_lower(self.positive.potential, self.negative.potential):
            raise ValueError("Polarized-capacitor evidence must retain positive pin 1 below pin 2")


ComponentPolarityEvidence: TypeAlias = (
    DiodeRailOrientationEvidence | PolarizedCapacitorRailOrientationEvidence
)


def project_component_polarity_evidence(
    source: ComponentPolarityEvidence,
) -> CandidateEvidenceProjection:
    """Project polarity sources to their existing rule-specific report fields."""
    if isinstance(source, DiodeRailOrientationEvidence):
        evidence: dict[str, tuple[str, ...]] = {
            "component": (source.reference,),
            "symbol": (source.symbol,),
            "anode_pin": (source.anode.pin,),
            "anode_net": (source.anode.net,),
            "cathode_pin": (source.cathode.pin,),
            "cathode_net": (source.cathode.net,),
            "anode_potential_basis": source.anode.potential.evidence,
            "cathode_potential_basis": source.cathode.potential.evidence,
        }
        if source.anode.potential.value is not None:
            evidence["anode_ordering_value_volts"] = (str(source.anode.potential.value),)
        if source.cathode.potential.value is not None:
            evidence["cathode_ordering_value_volts"] = (str(source.cathode.potential.value),)
        return CandidateEvidenceProjection(
            rule_id=DIODE_RAIL_ORIENTATION_RULE_ID, evidence=evidence
        )

    return CandidateEvidenceProjection(
        rule_id=POLARIZED_CAPACITOR_RAIL_ORIENTATION_RULE_ID,
        evidence={
            "component": (source.reference,),
            "symbol": (source.symbol,),
            "positive_terminal_pin": (source.positive.pin,),
            "negative_terminal_pin": (source.negative.pin,),
            "positive_terminal_net": (source.positive.net,),
            "negative_terminal_net": (source.negative.net,),
            "positive_terminal_potential_evidence": source.positive.potential.evidence,
            "negative_terminal_potential_evidence": source.negative.potential.evidence,
        },
    )


@dataclass(frozen=True, slots=True)
class ComponentPolarityCandidate(Candidate):
    """Finding bound to a current diode or polarized-capacitor source record."""

    source_evidence: ComponentPolarityEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: ComponentPolarityEvidence,
        *,
        subject: str,
        message: str,
    ) -> ComponentPolarityCandidate:
        projection = project_component_polarity_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_component_polarity_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id:
            raise ValueError("Component polarity rule must match its typed source evidence")
        if self.evidence != projection.evidence:
            raise ValueError("Component polarity report evidence must match its typed projection")


def _current_component_inventory(
    observed: NetlistContract,
    *,
    reference: str,
    symbol: str,
) -> tuple[str, ...]:
    reference_key = reference.casefold()
    fitted = {candidate.casefold() for candidate in observed.components}
    dnp = {candidate.casefold() for candidate in observed.dnp_components}
    inventory_by_reference = {
        candidate.casefold(): tuple(numbers)
        for candidate, numbers in observed.component_pin_numbers.items()
    }
    if (
        reference_key not in fitted
        or reference_key in dnp
        or observed.component_symbols.get(reference) != symbol
    ):
        raise ValueError("Component polarity evidence requires the current fitted native symbol")
    inventory = inventory_by_reference.get(reference_key)
    if inventory is None:
        raise ValueError("Component polarity evidence requires the native pin inventory")
    return inventory
