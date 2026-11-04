"""Typed LED topology sources and stable candidate evidence projections."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from .component_roles import component_role_binding_digest, component_role_binding_evidence
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .led_heuristics import DirectLedRailBridge, LedOutputWithoutVisibleSeriesResistor

LedCandidateEvidence: TypeAlias = DirectLedRailBridge | LedOutputWithoutVisibleSeriesResistor


def project_led_candidate_evidence(
    source: LedCandidateEvidence,
) -> CandidateEvidenceProjection:
    """Project one typed LED topology observation into its established report fields."""
    if isinstance(source, DirectLedRailBridge):
        if source.positive_net == source.return_net:
            raise ValueError("An LED rail bridge requires distinct positive and return nets")
        return CandidateEvidenceProjection(
            rule_id="component.led_directly_across_supply_and_return",
            evidence={
                "symbol": (source.symbol,),
                "led_pins": source.pins,
                "positive_net": (source.positive_net,),
                "return_net": (source.return_net,),
            },
        )

    if (
        len(set(source.led_pins)) != 2
        or not source.output_pins
        or len(source.output_pin_types) != len(source.output_pins)
        or source.driven_net == source.opposite_net
        or source.opposite_net_role not in {"positive", "return"}
    ):
        raise ValueError("Output-driven LED evidence must retain a complete rail-spanning path")
    role_evidence = _role_binding_evidence(source)
    return CandidateEvidenceProjection(
        rule_id="component.led_directly_driven_from_output",
        evidence={
            "symbol": (source.symbol,),
            "led_pins": source.led_pins,
            "output_pins": source.output_pins,
            "output_pin_types": source.output_pin_types,
            "driven_net": (source.driven_net,),
            "opposite_net": (source.opposite_net,),
            "opposite_net_role": (source.opposite_net_role,),
            **role_evidence,
        },
    )


@dataclass(frozen=True, slots=True)
class LedTopologyCandidate(Candidate):
    """Internal LED finding retaining its exact typed topology observation."""

    source_evidence: LedCandidateEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: LedCandidateEvidence,
        *,
        subject: str,
        message: str,
    ) -> LedTopologyCandidate:
        projection = project_led_candidate_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_led_candidate_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id:
            raise ValueError("LED rule must match its typed topology source")
        if self.evidence != projection.evidence:
            raise ValueError("LED evidence must match its typed source projection")


def _role_binding_evidence(
    source: LedOutputWithoutVisibleSeriesResistor,
) -> dict[str, tuple[str, ...]]:
    if source.role_binding is None:
        if source.role_binding_sha256 is not None:
            raise ValueError("An absent LED role binding cannot carry a role-map digest")
        return {}
    if (
        source.role_binding.role != "led"
        or source.role_binding.symbol != source.symbol
        or source.role_binding_sha256 is None
        or source.role_binding_sha256 != component_role_binding_digest(source.role_binding)
    ):
        raise ValueError("LED role evidence must retain its exact binding and digest")
    return component_role_binding_evidence(source.role_binding)
