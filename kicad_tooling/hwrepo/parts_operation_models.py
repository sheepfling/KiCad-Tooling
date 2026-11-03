"""Typed inputs for source-bound purchasing and parts-review operations."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field

from .model_primitives import Identifier, NonEmptyText, NonNegativeCount, PositiveCount, StrictModel


class PartsPreparationRequest(StrictModel):
    """Bind project evidence, reviewed preferences, quantities, and native runner choice."""

    project_id: Identifier
    output: Path
    native_summary: Path | None = None
    requested_preferences: Path | None = None
    boards: PositiveCount | None = None
    spare_percent: Annotated[int, Field(ge=0, le=100)] | None = None
    spare_minimum: NonNegativeCount | None = None
    cli: NonEmptyText = "kicad-cli"
    runner_mode: Literal["auto", "local", "container"] = "auto"
