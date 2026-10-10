"""Reviewable heuristic findings from source-bound native netlist evidence."""

from __future__ import annotations

from pathlib import Path

from .design_lint_candidate_aggregation import candidates, fingerprint
from .design_lint_catalog import rule_catalog
from .design_lint_evaluator import evaluate
from .design_lint_project_inspection import inspect_design_lint_summary
from .design_lint_text_report import text_report
from .models import DesignLintReport

__all__ = [
    "candidates",
    "evaluate",
    "fingerprint",
    "inspect_summary",
    "rule_catalog",
    "text_report",
]


def inspect_summary(root: Path, project_id: str, native_summary: Path) -> DesignLintReport:
    """Inspect current project inputs and evaluate the authored design-lint policy."""
    return inspect_design_lint_summary(root, project_id, native_summary, evaluate)
