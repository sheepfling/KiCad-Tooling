"""Typed requests for BOM and drawing navigation operations."""

from __future__ import annotations

from pathlib import Path

from .model_primitives import Identifier, StrictModel


class CrossProbeBuildRequest(StrictModel):
    """Select the project receipts, optional variant, and output for one cross-probe."""

    project_id: Identifier
    parts_report: Path
    findings_view: Path
    output: Path | None = None
    assembly_variant: str | None = None
