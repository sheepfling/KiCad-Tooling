"""Typed request contract for one selected project verification run."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import model_validator

from .model_primitives import Identifier, StrictModel

VerificationDepth = Literal["portable", "native", "electrical"]
VerificationRunner = Literal["auto", "local", "container"]
VerificationDetail = Literal["brief", "full"]


class ProjectVerificationRequest(StrictModel):
    """Inputs shared by the CLI and MCP project-verification surfaces."""

    project_id: Identifier
    depth: VerificationDepth = "portable"
    runner: VerificationRunner = "auto"
    cli: str = "kicad-cli"
    output: Path | None = None
    detail: VerificationDetail = "brief"
    ngspice: str = "ngspice"

    @model_validator(mode="after")
    def validate_runner_depth(self) -> ProjectVerificationRequest:
        if self.depth == "portable" and self.runner != "auto":
            raise ValueError("A local or container runner requires native depth")
        return self
