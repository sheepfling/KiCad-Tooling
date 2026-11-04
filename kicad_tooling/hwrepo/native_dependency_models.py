"""Typed requests for preparing native container dependencies."""

from __future__ import annotations

from pathlib import Path

from .model_primitives import NonEmptyText, StrictModel


class NativeDependencyPreparationRequest(StrictModel):
    """Select a project checkout, digest-pinned image, and ignored output path."""

    root: Path
    image: NonEmptyText
    output: Path
