"""Project decisions and findings owned by deterministic design lint."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from .design_lint_rule_types import DesignLintRuleId
from .model_primitives import Digest, NonEmptyText, StrictModel


class DesignLintRuleOverride(StrictModel):
    """One project-owned mode decision for a catalogued lint rule."""

    rule_id: DesignLintRuleId
    mode: Literal["review", "block", "off"]
    reason: NonEmptyText


class DesignLintIgnore(StrictModel):
    """One reasoned decision for an exact observed finding fingerprint."""

    rule_id: DesignLintRuleId
    fingerprint: Digest
    reason: NonEmptyText


class DesignLintFinding(StrictModel):
    """A deterministic source-bound candidate and its visible policy disposition."""

    rule_id: DesignLintRuleId
    fingerprint: Digest
    subject: NonEmptyText
    message: NonEmptyText
    evidence: Mapping[str, tuple[str, ...]]
    mode: Literal["review", "block", "off"]
    disposition: Literal["OPEN", "IGNORED", "RULE_OFF"]
    reason: NonEmptyText | None = None
