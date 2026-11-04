"""Typed component power-pin sources and their stable finding projection."""

from __future__ import annotations

from dataclasses import dataclass

from .component_pin_patterns import (
    UnconnectedGenericPowerInputComponentPin,
    UnconnectedGenericPowerOutputComponentPin,
    UnconnectedNamedComponentPin,
)
from .design_lint_types import Candidate, CandidateEvidenceProjection

UnconnectedComponentPinEvidence = (
    UnconnectedGenericPowerInputComponentPin
    | UnconnectedGenericPowerOutputComponentPin
    | UnconnectedNamedComponentPin
)


def project_unconnected_component_pin_evidence(
    source: UnconnectedComponentPinEvidence,
) -> CandidateEvidenceProjection:
    """Project one unconnected component power pin to its existing wire fields."""
    if isinstance(source, UnconnectedNamedComponentPin):
        if source.category == "supply":
            rule_id = "component.unconnected_supply_pin"
        elif source.category == "return":
            rule_id = "component.unconnected_return_pin"
        else:
            raise ValueError(
                f"Unsupported unconnected named component pin category: {source.category}"
            )
        evidence = {source.pin: ()}
    elif isinstance(source, UnconnectedGenericPowerInputComponentPin):
        if source.electrical_type != "power_in":
            raise ValueError("Generic power-input evidence requires the native power_in role")
        rule_id = "component.unconnected_power_input"
        evidence = _generic_power_evidence(source)
    else:
        if source.electrical_type != "power_out":
            raise ValueError("Generic power-output evidence requires the native power_out role")
        rule_id = "component.unconnected_power_output"
        evidence = _generic_power_evidence(source)
    return CandidateEvidenceProjection(rule_id=rule_id, evidence=evidence)


@dataclass(frozen=True, slots=True)
class UnconnectedComponentPinCandidate(Candidate):
    """Internal finding retaining its exact unconnected component-pin observation."""

    source_evidence: UnconnectedComponentPinEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: UnconnectedComponentPinEvidence,
        *,
        subject: str,
        message: str,
    ) -> UnconnectedComponentPinCandidate:
        projection = project_unconnected_component_pin_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_unconnected_component_pin_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id:
            raise ValueError("Unconnected component pin rule must match its source evidence")
        if self.evidence != projection.evidence:
            raise ValueError("Unconnected component pin evidence must match its typed projection")


def _generic_power_evidence(
    source: UnconnectedGenericPowerInputComponentPin | UnconnectedGenericPowerOutputComponentPin,
) -> dict[str, tuple[str, ...]]:
    evidence = {
        "symbol": (source.symbol,),
        "pin_electrical_type": (source.electrical_type,),
        source.pin: (),
    }
    if source.function is not None:
        evidence["native_pin_function"] = (source.function,)
    return evidence
