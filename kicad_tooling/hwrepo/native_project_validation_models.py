"""Typed requests for one project's exact native validation run."""

from __future__ import annotations

from pathlib import Path

from .model_primitives import NonEmptyText, StrictModel


class NativeProjectValidationRequest(StrictModel):
    """Select the fresh receipt, KiCad CLI, and optional project config path."""

    output: Path
    cli: NonEmptyText
    config_path: Path | None = None
