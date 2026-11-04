"""Shared internal value types for design-lint evaluation."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from .design_lint_rule_types import DesignLintRuleId


def _freeze_evidence(
    evidence: Mapping[str, tuple[str, ...]],
) -> Mapping[str, tuple[str, ...]]:
    frozen = {key: tuple(values) for key, values in evidence.items()}
    return MappingProxyType(frozen)


@dataclass(frozen=True, slots=True)
class CandidateEvidenceProjection:
    """A rule-owned projection into the stable candidate report fields."""

    rule_id: DesignLintRuleId
    evidence: Mapping[str, tuple[str, ...]]

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence", _freeze_evidence(self.evidence))


@dataclass(frozen=True, slots=True)
class Candidate:
    rule_id: DesignLintRuleId
    subject: str
    message: str
    evidence: Mapping[str, tuple[str, ...]]

    def __post_init__(self) -> None:
        """Copy and freeze the report evidence at the candidate boundary."""
        object.__setattr__(self, "evidence", _freeze_evidence(self.evidence))
