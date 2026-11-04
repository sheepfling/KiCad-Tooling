"""Shared internal value types for design-lint evaluation."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from .design_lint_rule_types import DesignLintRuleId


@dataclass(frozen=True, slots=True)
class Candidate:
    rule_id: DesignLintRuleId
    subject: str
    message: str
    evidence: Mapping[str, tuple[str, ...]]

    def __post_init__(self) -> None:
        """Copy and freeze the legacy wire evidence at the candidate boundary."""
        frozen = {key: tuple(values) for key, values in self.evidence.items()}
        object.__setattr__(self, "evidence", MappingProxyType(frozen))
