"""Typed inputs for shared electrical-analysis operations."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from .model_primitives import Identifier, NonEmptyText, StrictModel


class ElectricalAnalysisRequest(StrictModel):
    """Select project evidence, receipt location, and fixed tool-runner choices."""

    project_id: Identifier
    output: Path | None = None
    native_summary: Path | None = None
    cli: NonEmptyText = "kicad-cli"
    ngspice: NonEmptyText = "ngspice"
    runner_mode: Literal["auto", "local", "container"] = "auto"
