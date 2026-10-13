"""Typed source-bound design-lint reconciliation records."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from pydantic import Field, model_validator

from .design_lint_finding_models import (
    DesignLintFinding,
    DesignLintIgnore,
    DesignLintRuleOverride,
)
from .model_primitives import Digest, Identifier, NonEmptyText, RepositoryPath, StrictModel


class DesignLintFindingTransition(StrictModel):
    """One finding retained on both sides of a baseline comparison."""

    fingerprint: Digest
    kind: Literal["PERSISTING", "NEW", "NO_LONGER_REPORTED", "RECLASSIFIED"]
    baseline: DesignLintFinding | None = None
    current: DesignLintFinding | None = None

    @model_validator(mode="after")
    def transition_has_expected_sides(self) -> DesignLintFindingTransition:
        if self.kind == "NEW" and (self.baseline is not None or self.current is None):
            raise ValueError("A new finding must have only current evidence")
        if self.kind == "NO_LONGER_REPORTED" and (
            self.baseline is None or self.current is not None
        ):
            raise ValueError("A no-longer-reported finding must have only baseline evidence")
        if self.kind in {"PERSISTING", "RECLASSIFIED"} and (
            self.baseline is None or self.current is None
        ):
            raise ValueError("A continuing finding must retain baseline and current evidence")
        if any(
            item is not None and item.fingerprint != self.fingerprint
            for item in (self.baseline, self.current)
        ):
            raise ValueError("Transition fingerprint must match its retained finding evidence")
        if self.kind == "PERSISTING" and self.baseline != self.current:
            raise ValueError(
                "A persisting finding must have identical baseline and current records"
            )
        if self.kind == "RECLASSIFIED" and self.baseline == self.current:
            raise ValueError("A reclassified finding must record a changed finding record")
        return self


class DesignLintReconciliationReport(StrictModel):
    """Finding deltas with both source-bound reports' evidence preserved."""

    schema_version: Literal["1"] = "1"
    lane: Literal["DESIGN_LINT_RECONCILIATION"] = "DESIGN_LINT_RECONCILIATION"
    status: Literal["UNCHANGED", "REVIEW", "BLOCKED"]
    build_authorized: Literal[False] = False
    baseline_project_id: Identifier
    current_project_id: Identifier
    baseline_report_sha256: Digest
    current_report_sha256: Digest
    baseline_status: Literal["PASS", "REVIEW", "FAIL", "BLOCKED"]
    current_status: Literal["PASS", "REVIEW", "FAIL", "BLOCKED"]
    baseline_native_status: Literal["PASS", "FAIL"] | None = None
    current_native_status: Literal["PASS", "FAIL"] | None = None
    baseline_native_summary: str | None = None
    current_native_summary: str | None = None
    baseline_project_manifest_sha256: Digest | None = None
    current_project_manifest_sha256: Digest | None = None
    baseline_policy_path: RepositoryPath | None = None
    current_policy_path: RepositoryPath | None = None
    baseline_policy_sha256: Digest | None = None
    current_policy_sha256: Digest | None = None
    baseline_source_hashes: Mapping[RepositoryPath, Digest] = Field(default_factory=dict)
    current_source_hashes: Mapping[RepositoryPath, Digest] = Field(default_factory=dict)
    changed_source_paths: tuple[RepositoryPath, ...] = ()
    baseline_netlist_sha256: Digest | None = None
    current_netlist_sha256: Digest | None = None
    baseline_catalog_sha256: Digest | None = None
    current_catalog_sha256: Digest | None = None
    baseline_rule_overrides: tuple[DesignLintRuleOverride, ...] = ()
    current_rule_overrides: tuple[DesignLintRuleOverride, ...] = ()
    baseline_stale_ignores: tuple[DesignLintIgnore, ...] = ()
    current_stale_ignores: tuple[DesignLintIgnore, ...] = ()
    baseline_findings: tuple[DesignLintFinding, ...] = ()
    current_findings: tuple[DesignLintFinding, ...] = ()
    baseline_issues: tuple[NonEmptyText, ...] = ()
    current_issues: tuple[NonEmptyText, ...] = ()
    context_changes: tuple[NonEmptyText, ...] = ()
    transitions: tuple[DesignLintFindingTransition, ...] = ()
    issue: NonEmptyText | None = None

    @model_validator(mode="after")
    def status_matches_review_evidence(self) -> DesignLintReconciliationReport:
        if self.status == "BLOCKED" and self.issue is None:
            raise ValueError("Blocked reconciliation must explain its evidence gap")
        if self.status != "BLOCKED" and self.issue is not None:
            raise ValueError("Only blocked reconciliation may carry an issue")
        changed = any(item.kind != "PERSISTING" for item in self.transitions)
        changed = changed or bool(self.context_changes)
        if self.status == "UNCHANGED" and changed:
            raise ValueError("Unchanged reconciliation cannot contain finding or context changes")
        if self.status == "REVIEW" and not changed:
            raise ValueError("Review reconciliation must contain a finding or context change")
        return self
