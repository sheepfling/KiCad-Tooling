"""Typed requests for source-bound design-lint project inspection."""

from __future__ import annotations

from pathlib import Path

from .model_primitives import Identifier, StrictModel


class DesignLintInspectionRequest(StrictModel):
    """Select one registered project and its retained native summary."""

    project_id: Identifier
    native_summary: Path
