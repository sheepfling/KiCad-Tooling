"""Readable output for source-bound design-lint reconciliation."""

from __future__ import annotations

from .design_lint_finding_models import DesignLintFinding
from .design_lint_reconciliation_models import (
    DesignLintFindingTransition,
    DesignLintReconciliationReport,
)


def _finding_lines(label: str, finding: DesignLintFinding) -> list[str]:
    lines = [
        (
            f"  {label}: {finding.disposition} [{finding.rule_id}] {finding.subject} "
            f"({finding.fingerprint})"
        ),
        f"    {finding.message}",
    ]
    lines.extend(
        f"    {name}: {', '.join(values) or '<unconnected>'}"
        for name, values in sorted(finding.evidence.items())
    )
    if finding.reason:
        lines.append(f"    Reason: {finding.reason}")
    return lines


def _transition_lines(item: DesignLintFindingTransition) -> list[str]:
    lines = [f"{item.kind} ({item.fingerprint})"]
    if item.baseline is not None:
        lines.extend(_finding_lines("baseline", item.baseline))
    if item.current is not None:
        lines.extend(_finding_lines("current", item.current))
    return lines


def reconciliation_text(report: DesignLintReconciliationReport) -> str:
    """Render each finding transition with its baseline/current evidence intact."""
    lines = [
        f"Design-lint reconciliation: {report.status}",
        f"Project IDs: {report.baseline_project_id} -> {report.current_project_id}",
        f"Report SHA-256: {report.baseline_report_sha256} -> {report.current_report_sha256}",
        f"Report status: {report.baseline_status} -> {report.current_status}",
        f"Native validation status: {report.baseline_native_status} -> {report.current_native_status}",
        f"Rule catalog SHA-256: {report.baseline_catalog_sha256} -> {report.current_catalog_sha256}",
        f"Source-bound paths changed: {len(report.changed_source_paths)}",
        f"Findings compared: {len(report.transitions)}",
    ]
    if report.changed_source_paths:
        lines.extend(f"  Source changed: {path}" for path in report.changed_source_paths)
    if report.baseline_netlist_sha256 != report.current_netlist_sha256:
        lines.append(
            "Native netlist SHA-256 changed: "
            f"{report.baseline_netlist_sha256 or 'unavailable'} -> "
            f"{report.current_netlist_sha256 or 'unavailable'}"
        )
    for change in report.context_changes:
        lines.append(f"Context change: {change}")
    if report.issue is not None:
        lines.append(f"Issue: {report.issue}")
    if not report.transitions:
        lines.append("No finding transitions.")
        if report.baseline_findings or report.current_findings:
            lines.append("Unmatched raw findings (comparison unavailable):")
            for item in report.baseline_findings:
                lines.extend(_finding_lines("baseline", item))
            for item in report.current_findings:
                lines.extend(_finding_lines("current", item))
    for item in report.transitions:
        lines.extend(_transition_lines(item))
    return "\n".join(lines)
