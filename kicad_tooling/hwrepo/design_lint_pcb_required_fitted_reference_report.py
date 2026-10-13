"""Typed report checks and text lines for required fitted PCB references."""

from __future__ import annotations

from collections.abc import Sequence

from .design_lint_finding_models import DesignLintFinding
from .pcb_component_inventory_models import PcbComponentInventoryCoverageReport


def validate_required_fitted_reference_findings(
    inventory: PcbComponentInventoryCoverageReport,
    findings: Sequence[DesignLintFinding],
) -> None:
    """Require findings to account for every required-reference result or evidence gap."""
    coverage = inventory.required_fitted_reference_coverage
    if coverage.status == "DISABLED":
        expected = 0
    elif coverage.status == "BLOCKED":
        expected = 1
    else:
        expected = len(coverage.mismatches)
    actual = sum(item.rule_id == "pcb.required_fitted_reference" for item in findings)
    if actual != expected:
        raise ValueError("Required fitted-reference findings must match coverage rows")


def required_fitted_reference_report_lines(
    inventory: PcbComponentInventoryCoverageReport,
) -> list[str]:
    """Render the explicit requirement coverage and its source mismatches."""
    coverage = inventory.required_fitted_reference_coverage
    if coverage.status == "DISABLED":
        return []
    lines = [
        (
            "PCB required fitted-reference check: "
            f"{coverage.status} (mode: {coverage.mode}; requirements: {coverage.requirement_count})"
        )
    ]
    for item in coverage.mismatches:
        lines.append(
            f"  {item.reference}: "
            + ", ".join(item.violations)
            + f" (expected {item.expected_footprint})"
        )
    if coverage.issue is not None:
        lines.append(f"  Coverage issue: {coverage.issue}")
    return lines
