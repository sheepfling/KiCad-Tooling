"""Review source-mapped capacitor hold-up estimates against authored limits."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from types import MappingProxyType

from .capacitor_hold_up_checks import (
    CapacitorHoldUpAssessment,
    assess_capacitor_hold_up,
    capacitor_hold_up_map_sha256,
)
from .capacitor_hold_up_models import CapacitorHoldUpMap, CapacitorHoldUpRequirement
from .design_lint_types import Candidate
from .netlist_contract_models import NetlistContract

RULE_ID = "power.capacitor_hold_up_below_project_minimum"


@dataclass(frozen=True, slots=True)
class CapacitorHoldUpFindingEvidence:
    """A current assessment retained with its native input and authored map."""

    observed: NetlistContract
    requirements: CapacitorHoldUpMap
    requirement_id: str
    assessment: CapacitorHoldUpAssessment

    def __post_init__(self) -> None:
        requirement = self.requirement
        current = assess_capacitor_hold_up(self.observed, requirement)
        if self.assessment != current or not (
            current.issues
            or current.estimated_hold_up_ms is None
            or current.estimated_hold_up_ms < Decimal(str(requirement.minimum_hold_up_ms))
        ):
            raise ValueError("Hold-up evidence must retain one current actionable assessment")

    @property
    def requirement(self) -> CapacitorHoldUpRequirement:
        matches = tuple(
            item
            for item in self.requirements.requirements
            if item.id.casefold() == self.requirement_id.casefold()
        )
        if len(matches) != 1:
            raise ValueError("Hold-up evidence requires one authored requirement")
        return matches[0]

    @property
    def map_sha256(self) -> str:
        return capacitor_hold_up_map_sha256(self.requirements)

    @property
    def projected_evidence(self) -> Mapping[str, tuple[str, ...]]:
        requirement = self.requirement
        assessment = self.assessment
        return MappingProxyType(
            {
                "requirement_id": (requirement.id,),
                "capacitor": (requirement.capacitor_reference,),
                "part_id": (requirement.expected_part_id,),
                "capacitor_value": (requirement.expected_value,),
                "positive_endpoint": (f"{requirement.positive_pin}={requirement.positive_net}",),
                "return_endpoint": (f"{requirement.return_pin}={requirement.return_net}",),
                "nominal_capacitance_pf": (
                    ()
                    if assessment.capacitance_pf is None
                    else (format(assessment.capacitance_pf, "f"),)
                ),
                "estimated_hold_up_ms": (
                    ()
                    if assessment.estimated_hold_up_ms is None
                    else (format(assessment.estimated_hold_up_ms, "f"),)
                ),
                "minimum_hold_up_ms": (str(requirement.minimum_hold_up_ms),),
                "operating_window_v": (
                    f"{requirement.starting_voltage_v}->{requirement.minimum_load_voltage_v}",
                ),
                "maximum_load_current_ma": (str(requirement.maximum_load_current_ma),),
                "issues": assessment.issues,
                "basis": (requirement.basis,),
                "map_sha256": (self.map_sha256,),
            }
        )


@dataclass(frozen=True, slots=True)
class CapacitorHoldUpCandidate(Candidate):
    """Power candidate that validates its serialized evidence against its sources."""

    source_evidence: CapacitorHoldUpFindingEvidence

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        if self.rule_id != RULE_ID or self.evidence != self.source_evidence.projected_evidence:
            raise ValueError("Hold-up candidate fields must match the typed source evidence")


def capacitor_hold_up_candidates(
    observed: NetlistContract,
    requirements: CapacitorHoldUpMap | None,
) -> tuple[Candidate, ...]:
    """Review mapped capacitors whose nominal constant-current estimate misses its limit."""
    if requirements is None:
        return ()
    found: list[Candidate] = []
    for requirement in sorted(requirements.requirements, key=lambda item: item.id.casefold()):
        assessment = assess_capacitor_hold_up(observed, requirement)
        estimated_ms = assessment.estimated_hold_up_ms
        minimum_ms = Decimal(str(requirement.minimum_hold_up_ms))
        if not assessment.issues and (estimated_ms is None or estimated_ms >= minimum_ms):
            continue
        source = CapacitorHoldUpFindingEvidence(
            observed=observed,
            requirements=requirements,
            requirement_id=requirement.id,
            assessment=assessment,
        )
        if assessment.issues:
            reason = "; ".join(assessment.issues)
        else:
            reason = (
                f"nominal constant-current estimate is {estimated_ms} ms, "
                f"below the authored {minimum_ms} ms minimum"
            )
        found.append(
            CapacitorHoldUpCandidate(
                rule_id=RULE_ID,
                subject=f"{requirement.id}: {requirement.capacitor_reference} hold-up review",
                message=(
                    f"The exact mapped capacitor does not meet the project-authored "
                    f"hold-up screen: {reason}. Review the cited source and operating bounds. "
                    "The estimate uses nominal capacitance and a constant-current load; it does "
                    "not model tolerance, voltage-dependent capacitance, ESR, leakage, load "
                    "transients, or the wider power path."
                ),
                evidence=source.projected_evidence,
                source_evidence=source,
            )
        )
    return tuple(found)
