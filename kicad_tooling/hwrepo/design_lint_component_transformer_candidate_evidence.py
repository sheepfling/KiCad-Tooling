"""Typed source projections for transformer winding candidates."""

from __future__ import annotations

from dataclasses import dataclass

from .design_lint_component_transformer_models import (
    SupportedTransformerObservation,
    TransformerPinNetAssignment,
    TransformerWindingPinGroup,
)
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection

_TRANSFORMER_WINDING_SAME_NET: DesignLintRuleId = "component.transformer_winding_same_net"
_TRANSFORMER_WINDING_GROUPS_SHARE_NET: DesignLintRuleId = (
    "component.transformer_winding_groups_share_net"
)


@dataclass(frozen=True, slots=True)
class TransformerWindingSameNetEvidence:
    """One supported winding whose two exact terminals share a native net."""

    transformer: SupportedTransformerObservation
    winding: TransformerWindingPinGroup
    net: str

    def __post_init__(self) -> None:
        if not any(group is self.winding for group in self.transformer.winding_groups):
            raise ValueError("Transformer winding must belong to its source observation")
        assignments = {item.pin_number: item.net for item in self.transformer.pin_assignments}
        if any(assignments.get(number) != self.net for number in self.winding.pin_numbers):
            raise ValueError("Transformer same-net evidence must match both source terminals")


@dataclass(frozen=True, slots=True)
class TransformerWindingGroupsShareNetEvidence:
    """The exact terminals from both supported winding groups on one native net."""

    transformer: SupportedTransformerObservation
    net: str
    first_winding: TransformerWindingPinGroup
    second_winding: TransformerWindingPinGroup
    first_pin_assignments: tuple[TransformerPinNetAssignment, ...]
    second_pin_assignments: tuple[TransformerPinNetAssignment, ...]

    def __post_init__(self) -> None:
        groups = self.transformer.winding_groups
        if (
            len(groups) != 2
            or self.first_winding is not groups[0]
            or self.second_winding is not groups[1]
        ):
            raise ValueError("Transformer winding groups must match their source observation")
        by_number = {item.pin_number: item for item in self.transformer.pin_assignments}
        expected_first = tuple(
            by_number[number]
            for number in self.first_winding.pin_numbers
            if by_number[number].net == self.net
        )
        expected_second = tuple(
            by_number[number]
            for number in self.second_winding.pin_numbers
            if by_number[number].net == self.net
        )
        if not expected_first or not expected_second:
            raise ValueError("Shared-net evidence must touch both source winding groups")
        if (
            self.first_pin_assignments != expected_first
            or self.second_pin_assignments != expected_second
        ):
            raise ValueError("Transformer shared-net terminals must match their source assignments")


TransformerFindingEvidence = (
    TransformerWindingSameNetEvidence | TransformerWindingGroupsShareNetEvidence
)


def project_transformer_evidence(
    source: TransformerFindingEvidence,
) -> CandidateEvidenceProjection:
    """Project one typed transformer observation into the existing rule fields."""
    transformer = source.transformer
    if isinstance(source, TransformerWindingSameNetEvidence):
        return CandidateEvidenceProjection(
            rule_id=_TRANSFORMER_WINDING_SAME_NET,
            evidence={
                "symbol": (transformer.symbol,),
                "value": (transformer.value,),
                "winding": (source.winding.name,),
                "net": (source.net,),
                "pin_assignments": tuple(
                    f"{transformer.reference}.{number} -> {source.net}"
                    for number in source.winding.pin_numbers
                ),
            },
        )
    return CandidateEvidenceProjection(
        rule_id=_TRANSFORMER_WINDING_GROUPS_SHARE_NET,
        evidence={
            "symbol": (transformer.symbol,),
            "value": (transformer.value,),
            "shared_net": (source.net,),
            "first_winding_pins": tuple(
                f"{transformer.reference}.{item.pin_number}"
                for item in source.first_pin_assignments
            ),
            "second_winding_pins": tuple(
                f"{transformer.reference}.{item.pin_number}"
                for item in source.second_pin_assignments
            ),
        },
    )


@dataclass(frozen=True, slots=True)
class TransformerCandidate(Candidate):
    """Transformer finding retaining its exact normalized netlist observation."""

    source_evidence: TransformerFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: TransformerFindingEvidence,
        *,
        subject: str,
        message: str,
    ) -> TransformerCandidate:
        projection = project_transformer_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_transformer_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("Transformer fields must match their typed source projection")
