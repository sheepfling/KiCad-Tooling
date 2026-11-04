"""Typed source projections for one-sided open I3C signal candidates."""

from __future__ import annotations

from dataclasses import dataclass

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection
from .i3c_unconnected_pins import UnconnectedI3cSignalPin


@dataclass(frozen=True, slots=True)
class I3cUnconnectedFindingEvidence:
    """One unconnected signal pin paired with its assigned channel peer."""

    source: UnconnectedI3cSignalPin


_I3C_UNCONNECTED_PIN: DesignLintRuleId = "bus.i3c_unconnected_pin"


def project_i3c_unconnected_evidence(
    source: I3cUnconnectedFindingEvidence,
) -> CandidateEvidenceProjection:
    """Project the exact open-pin scan record into the stable finding fields."""
    pin = source.source
    return CandidateEvidenceProjection(
        rule_id=_I3C_UNCONNECTED_PIN,
        evidence={
            pin.pin: (),
            "function": (pin.function,),
            "i3c_role": (pin.role,),
            "i3c_channel": (pin.channel or "unindexed",),
            "paired_pin": (pin.paired_pin,),
            "paired_function": (pin.paired_function,),
            "paired_net": (pin.paired_net,),
        },
    )


@dataclass(frozen=True, slots=True)
class I3cUnconnectedCandidate(Candidate):
    """Review candidate retaining its exact unconnected-pin source record."""

    source_evidence: I3cUnconnectedFindingEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: I3cUnconnectedFindingEvidence,
        *,
        subject: str,
        message: str,
    ) -> I3cUnconnectedCandidate:
        projection = project_i3c_unconnected_evidence(source_evidence)
        return cls(
            rule_id=projection.rule_id,
            subject=subject,
            message=message,
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_i3c_unconnected_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError("I3C unconnected fields must match their typed source projection")
