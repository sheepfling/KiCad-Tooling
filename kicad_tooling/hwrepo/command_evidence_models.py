"""Typed records for captured subprocess execution."""

from __future__ import annotations

from .model_primitives import NonEmptyText, StrictModel


class CommandEvidence(StrictModel):
    """Exit result and captured streams for one recorded command invocation."""

    argv: tuple[NonEmptyText, ...]
    started_utc: NonEmptyText
    returncode: int
    stdout: str = ""
    stderr: str = ""
    error: str | None = None
