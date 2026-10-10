"""Apply project rule modes and exact-fingerprint ignores to lint findings."""

from __future__ import annotations

from typing import Literal

from .design_lint_candidate_aggregation import fingerprint
from .design_lint_evaluation_types import (
    DesignLintEvaluationCandidates,
    DesignLintEvaluationPreparation,
    DesignLintFindingDisposition,
)
from .models import DesignLintFinding


def resolve_finding_dispositions(
    prepared: DesignLintEvaluationPreparation,
    candidate_results: DesignLintEvaluationCandidates,
) -> DesignLintFindingDisposition:
    """Apply reviewed modes and ignores without changing candidate evidence."""
    findings: list[DesignLintFinding] = []
    seen: set[str] = set()
    for item in candidate_results.items:
        key = fingerprint(item)
        seen.add(key)
        override = prepared.overrides.get(item.rule_id)
        mode: Literal["review", "block", "off"] = (
            prepared.default_modes[item.rule_id] if override is None else override.mode
        )
        ignored = prepared.ignores.get(key)
        if ignored is not None and ignored.rule_id != item.rule_id:
            return DesignLintFindingDisposition(
                seen=frozenset(seen),
                findings=tuple(findings),
                issue=f"Ignore {key} names the wrong rule",
            )
        disposition: Literal["OPEN", "IGNORED", "RULE_OFF"] = (
            "RULE_OFF" if mode == "off" else "IGNORED" if ignored is not None else "OPEN"
        )
        findings.append(
            DesignLintFinding(
                rule_id=item.rule_id,
                fingerprint=key,
                subject=item.subject,
                message=item.message,
                evidence=item.evidence,
                mode=mode,
                disposition=disposition,
                reason=(
                    override.reason
                    if disposition == "RULE_OFF" and override is not None
                    else ignored.reason
                    if ignored is not None
                    else None
                ),
            )
        )
    return DesignLintFindingDisposition(seen=frozenset(seen), findings=tuple(findings))
