"""Typed inputs for the native project-check operation."""

from __future__ import annotations

from pathlib import Path

from .model_primitives import Identifier, StrictModel


class NativeProjectCheckRequest(StrictModel):
    """Output scope, selected project set and exact KiCad command."""

    output: Path
    cli: str = "kicad-cli"
    project_ids: tuple[Identifier, ...] | None = None
