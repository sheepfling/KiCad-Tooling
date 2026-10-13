"""Compare source-bound design-lint reports without suppressing findings."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from typing import Literal

from .design_lint_connectivity_snapshot import compare_connectivity_snapshots
from .design_lint_connectivity_snapshot_models import DesignLintConnectivitySnapshot
from .design_lint_finding_models import DesignLintFinding
from .design_lint_reconciliation_models import (
    DesignLintFindingTransition,
    DesignLintReconciliationReport,
)
from .design_lint_report_models import DesignLintReport


def _report_sha256(report: DesignLintReport) -> str:
    payload = json.dumps(report.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _connectivity_sha256(snapshot: DesignLintConnectivitySnapshot | None) -> str | None:
    if snapshot is None:
        return None
    payload = json.dumps(snapshot.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _finding_transitions(
    baseline: DesignLintReport,
    current: DesignLintReport,
) -> tuple[DesignLintFindingTransition, ...]:
    before = {item.fingerprint: item for item in baseline.findings}
    after = {item.fingerprint: item for item in current.findings}
    rows: list[DesignLintFindingTransition] = []
    for key in sorted(before.keys() | after.keys()):
        old = before.get(key)
        new = after.get(key)
        if old is None:
            kind: Literal["PERSISTING", "NEW", "NO_LONGER_REPORTED", "RECLASSIFIED"] = "NEW"
        elif new is None:
            kind = "NO_LONGER_REPORTED"
        elif old == new:
            kind = "PERSISTING"
        else:
            kind = "RECLASSIFIED"
        rows.append(
            DesignLintFindingTransition(
                fingerprint=key,
                kind=kind,
                baseline=old,
                current=new,
            )
        )
    return tuple(rows)


def _ordered_findings(report: DesignLintReport) -> tuple[DesignLintFinding, ...]:
    """Retain raw report findings even when duplicate keys prevent safe matching."""
    return tuple(
        sorted(
            report.findings,
            key=lambda item: (
                item.fingerprint,
                item.rule_id,
                item.subject,
                item.disposition,
                item.reason or "",
                json.dumps(item.model_dump(mode="json"), sort_keys=True, separators=(",", ":")),
            ),
        )
    )


def _input_issue(report: DesignLintReport, label: str) -> str | None:
    if report.status == "BLOCKED":
        return f"{label} design-lint report is BLOCKED"
    if not report.source_hashes:
        return f"{label} report has no source hashes"
    if report.netlist_sha256 is None:
        return f"{label} report has no native netlist hash"
    if report.rule_catalog is None:
        return f"{label} report has no rule catalog digest"
    duplicates = [
        key
        for key, count in Counter(item.fingerprint for item in report.findings).items()
        if count > 1
    ]
    if duplicates:
        return f"{label} report repeats finding fingerprints: {', '.join(sorted(duplicates))}"
    return None


def reconcile_design_lint_reports(
    baseline: DesignLintReport,
    current: DesignLintReport,
) -> DesignLintReconciliationReport:
    """Classify finding changes while retaining every old and current finding.

    ``NO_LONGER_REPORTED`` records are change evidence, not accepted dismissals.
    Ignored and rule-off findings remain present in both reports and transitions.
    """
    transitions = (
        _finding_transitions(baseline, current)
        if baseline.project_id == current.project_id
        and len({item.fingerprint for item in baseline.findings}) == len(baseline.findings)
        and len({item.fingerprint for item in current.findings}) == len(current.findings)
        else ()
    )
    baseline_snapshot = baseline.connectivity_snapshot
    current_snapshot = current.connectivity_snapshot
    connectivity_comparison: Literal["COMPLETE", "PARTIAL", "UNAVAILABLE", "INCOMPATIBLE"]
    connectivity_changes = ()
    connectivity_issue: str | None = None
    if baseline_snapshot is None or current_snapshot is None:
        connectivity_comparison = "UNAVAILABLE"
    elif (baseline_snapshot.kicad_version, baseline_snapshot.toolchain_image) != (
        current_snapshot.kicad_version,
        current_snapshot.toolchain_image,
    ):
        connectivity_comparison = "INCOMPATIBLE"
        connectivity_issue = (
            "Baseline and current connectivity snapshots use different exact KiCad versions "
            "or toolchain images"
        )
    else:
        connectivity_comparison = (
            "COMPLETE"
            if baseline_snapshot.coverage == current_snapshot.coverage == "COMPLETE"
            else "PARTIAL"
        )
        connectivity_changes = compare_connectivity_snapshots(
            baseline_snapshot,
            current_snapshot,
        )
    issues = tuple(
        issue
        for issue in (
            _input_issue(baseline, "Baseline"),
            _input_issue(current, "Current"),
            connectivity_issue,
        )
        if issue is not None
    )
    if baseline.project_id != current.project_id:
        issues += ("Baseline and current reports belong to different project IDs",)

    context_changes: list[str] = []
    if baseline.status != current.status:
        context_changes.append(f"Report status changed: {baseline.status} -> {current.status}")
    if current.status != "PASS":
        context_changes.append(
            f"Current lint report is {current.status}; reconciliation does not accept its findings"
        )
    open_count = sum(item.disposition == "OPEN" for item in current.findings)
    if open_count:
        context_changes.append(
            f"Current report retains {open_count} open finding(s); baseline equality does not accept them"
        )
    old_catalog = baseline.rule_catalog.sha256 if baseline.rule_catalog is not None else None
    new_catalog = current.rule_catalog.sha256 if current.rule_catalog is not None else None
    if old_catalog != new_catalog:
        context_changes.append("Rule catalog digest changed")
    if (baseline.policy_path, baseline.policy_sha256) != (
        current.policy_path,
        current.policy_sha256,
    ):
        context_changes.append("Project lint-policy digest changed")
    if baseline.project_manifest_sha256 != current.project_manifest_sha256:
        context_changes.append("Project manifest digest changed")
    if (baseline.native_status, baseline.native_summary) != (
        current.native_status,
        current.native_summary,
    ):
        context_changes.append("Native validation evidence changed")
    if baseline.rule_overrides != current.rule_overrides:
        context_changes.append("Project rule overrides changed")
    if baseline.stale_ignores != current.stale_ignores:
        context_changes.append("Stale exact-ignore records changed")
    if baseline.issues != current.issues:
        context_changes.append("Report issues changed")
    if connectivity_comparison == "UNAVAILABLE":
        missing = []
        if baseline_snapshot is None:
            missing.append("baseline")
        if current_snapshot is None:
            missing.append("current")
        context_changes.append(
            f"Pin-connectivity comparison unavailable: {', '.join(missing)} report "
            "lacks a native connectivity snapshot"
        )
    elif connectivity_comparison == "PARTIAL":
        context_changes.append(
            "Pin-connectivity comparison is partial; inspect snapshot coverage before "
            "relying on the listed changes"
        )
    elif connectivity_changes:
        context_changes.append(
            f"Native pin connectivity changed for {len(connectivity_changes)} pin(s)"
        )

    before_sources = baseline.source_hashes
    after_sources = current.source_hashes
    changed_source_paths = tuple(
        sorted(
            path
            for path in before_sources.keys() | after_sources.keys()
            if before_sources.get(path) != after_sources.get(path)
        )
    )
    changed = (
        any(item.kind != "PERSISTING" for item in transitions)
        or bool(context_changes)
        or bool(connectivity_changes)
    )
    status: Literal["UNCHANGED", "REVIEW", "BLOCKED"] = (
        "BLOCKED" if issues else "REVIEW" if changed else "UNCHANGED"
    )
    issue = "; ".join(issues) if issues else None
    return DesignLintReconciliationReport(
        status=status,
        baseline_project_id=baseline.project_id,
        current_project_id=current.project_id,
        baseline_report_sha256=_report_sha256(baseline),
        current_report_sha256=_report_sha256(current),
        baseline_status=baseline.status,
        current_status=current.status,
        baseline_native_status=baseline.native_status,
        current_native_status=current.native_status,
        baseline_native_summary=baseline.native_summary,
        current_native_summary=current.native_summary,
        baseline_project_manifest_sha256=baseline.project_manifest_sha256,
        current_project_manifest_sha256=current.project_manifest_sha256,
        baseline_policy_path=baseline.policy_path,
        current_policy_path=current.policy_path,
        baseline_policy_sha256=baseline.policy_sha256,
        current_policy_sha256=current.policy_sha256,
        baseline_source_hashes=dict(sorted(before_sources.items())),
        current_source_hashes=dict(sorted(after_sources.items())),
        changed_source_paths=changed_source_paths,
        baseline_netlist_sha256=baseline.netlist_sha256,
        current_netlist_sha256=current.netlist_sha256,
        baseline_connectivity_sha256=_connectivity_sha256(baseline_snapshot),
        current_connectivity_sha256=_connectivity_sha256(current_snapshot),
        connectivity_comparison=connectivity_comparison,
        connectivity_changes=connectivity_changes,
        baseline_catalog_sha256=old_catalog,
        current_catalog_sha256=new_catalog,
        baseline_rule_overrides=tuple(
            sorted(baseline.rule_overrides, key=lambda item: item.rule_id)
        ),
        current_rule_overrides=tuple(sorted(current.rule_overrides, key=lambda item: item.rule_id)),
        baseline_stale_ignores=tuple(
            sorted(baseline.stale_ignores, key=lambda item: (item.rule_id, item.fingerprint))
        ),
        current_stale_ignores=tuple(
            sorted(current.stale_ignores, key=lambda item: (item.rule_id, item.fingerprint))
        ),
        baseline_findings=_ordered_findings(baseline),
        current_findings=_ordered_findings(current),
        baseline_issues=baseline.issues,
        current_issues=current.issues,
        context_changes=tuple(context_changes),
        transitions=transitions,
        issue=issue,
    )
