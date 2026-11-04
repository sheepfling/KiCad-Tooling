"""Typed evidence and stable projection for BJT and MOSFET terminal ties."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeAlias

from .design_lint_types import Candidate, CandidateEvidenceProjection

ComponentTerminalSameNetRuleId: TypeAlias = Literal[
    "component.bjt_collector_emitter_same_net",
    "component.bjt_base_emitter_same_net",
    "component.bjt_base_collector_same_net",
    "component.mosfet_drain_source_same_net",
    "component.mosfet_gate_source_same_net",
    "component.mosfet_gate_drain_same_net",
]
ComponentKind: TypeAlias = Literal["bjt", "mosfet"]
TerminalRole: TypeAlias = Literal["base", "collector", "emitter", "drain", "gate", "source"]


def _terminal_roles(
    rule_id: ComponentTerminalSameNetRuleId,
) -> tuple[ComponentKind, TerminalRole, TerminalRole]:
    match rule_id:
        case "component.bjt_collector_emitter_same_net":
            return "bjt", "collector", "emitter"
        case "component.bjt_base_emitter_same_net":
            return "bjt", "base", "emitter"
        case "component.bjt_base_collector_same_net":
            return "bjt", "base", "collector"
        case "component.mosfet_drain_source_same_net":
            return "mosfet", "drain", "source"
        case "component.mosfet_gate_source_same_net":
            return "mosfet", "gate", "source"
        case "component.mosfet_gate_drain_same_net":
            return "mosfet", "gate", "drain"


@dataclass(frozen=True, slots=True)
class ComponentTerminalSameNetEvidence:
    """One supported fitted device and its uniquely assigned native terminal pair."""

    rule_id: ComponentTerminalSameNetRuleId
    component_kind: ComponentKind
    reference: str
    symbol: str
    device_type: str
    first_pin: str
    first_net: str
    second_pin: str
    second_net: str

    def __post_init__(self) -> None:
        expected_kind, _, _ = _terminal_roles(self.rule_id)
        if self.component_kind != expected_kind:
            raise ValueError("Terminal evidence device kind must match its rule")
        if self.first_net.casefold() != self.second_net.casefold():
            raise ValueError("Same-net terminal evidence must retain matching native nets")
        if not all(
            (
                self.reference,
                self.symbol,
                self.device_type,
                self.first_pin,
                self.first_net,
                self.second_pin,
                self.second_net,
            )
        ):
            raise ValueError("Terminal evidence requires complete component and pin observations")


def project_component_terminal_evidence(
    source: ComponentTerminalSameNetEvidence,
) -> CandidateEvidenceProjection:
    """Map a typed terminal observation to the existing public finding fields."""
    component_kind, first_role, second_role = _terminal_roles(source.rule_id)
    if source.component_kind != component_kind:
        raise ValueError("Terminal evidence device kind must match its rule")
    device_type_field = "transistor_family" if component_kind == "bjt" else "channel_type"
    return CandidateEvidenceProjection(
        rule_id=source.rule_id,
        evidence={
            "component": (source.reference,),
            "symbol": (source.symbol,),
            device_type_field: (source.device_type,),
            f"{first_role}_pin": (source.first_pin,),
            f"{first_role}_net": (source.first_net,),
            f"{second_role}_pin": (source.second_pin,),
            f"{second_role}_net": (source.second_net,),
        },
    )


@dataclass(frozen=True, slots=True)
class ComponentTerminalCandidate(Candidate):
    """Finding retaining the source observation behind its report projection."""

    source_evidence: ComponentTerminalSameNetEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: ComponentTerminalSameNetEvidence,
        *,
        subject: str,
        message: str,
    ) -> ComponentTerminalCandidate:
        projection = project_component_terminal_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_component_terminal_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id:
            raise ValueError("Component terminal rule must match its source evidence")
        if self.evidence != projection.evidence:
            raise ValueError("Component terminal evidence must match its typed source projection")
