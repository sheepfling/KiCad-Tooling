"""Shared internal value types for design-lint evaluation."""

from __future__ import annotations

from dataclasses import dataclass

from .models import DesignLintRuleId


@dataclass(frozen=True)
class Candidate:
    rule_id: DesignLintRuleId
    subject: str
    message: str
    evidence: dict[str, tuple[str, ...]]
