"""Diagnostic receipt context management for MCP workflow services."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from .contracts import repo_path
from .diagnostic_journal import DiagnosticJournal


@contextmanager
def journal(root: Path, project_id: str) -> Generator[DiagnosticJournal, None, None]:
    """Validate receipt containment before creating a journal and retain failures."""
    repo_path(root, "build/diagnostics")
    receipt = DiagnosticJournal(root, project_id)
    try:
        yield receipt
    except (Exception, KeyboardInterrupt) as exc:
        receipt.fail(exc)
        raise
