"""Reviewable heuristic findings from source-bound native netlist evidence."""

from __future__ import annotations

from pathlib import Path

from .design_lint_candidate_aggregation import candidates, fingerprint
from .design_lint_catalog import rule_catalog
from .design_lint_evaluator import evaluate
from .design_lint_inspection_models import DesignLintInspectionRequest
from .design_lint_project_inspection import inspect_design_lint_request
from .design_lint_reconciliation import reconcile_design_lint_reports
from .design_lint_reconciliation_text import reconciliation_text
from .design_lint_report_models import DesignLintReport
from .design_lint_text_report import text_report

__all__ = [
    "candidates",
    "evaluate",
    "fingerprint",
    "inspect_request",
    "inspect_summary",
    "reconcile_design_lint_reports",
    "reconciliation_text",
    "rule_catalog",
    "text_report",
]


def inspect_summary(root: Path, project_id: str, native_summary: Path) -> DesignLintReport:
    """Inspect current project inputs and evaluate the authored design-lint policy."""
    return inspect_request(
        root,
        DesignLintInspectionRequest(project_id=project_id, native_summary=native_summary),
    )


def inspect_request(root: Path, request: DesignLintInspectionRequest) -> DesignLintReport:
    """Inspect source-bound project inputs through the typed shared operation."""
    return inspect_design_lint_request(root, request)
