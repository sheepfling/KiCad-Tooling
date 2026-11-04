"""Typed requests and response summaries for native project checks."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from .governance_lint_models import GovernanceLintReport
from .model_primitives import Identifier, RepositoryPath, StrictModel
from .product_models import ProductPolicyReport
from .repository_policy_models import RepositoryPolicyReport


class NativeProjectCheckRequest(StrictModel):
    """Output scope, selected project set and exact KiCad command."""

    output: Path
    cli: str = "kicad-cli"
    project_ids: tuple[Identifier, ...] | None = None


class ProjectCheckSummary(StrictModel):
    id: Identifier
    status: Literal["PASS", "FAIL"]
    summary: RepositoryPath


class CheckAllSummary(StrictModel):
    schema_version: Literal["1"] = "1"
    lane: Literal["KICAD_CLI_ALL_PROJECTS"] = "KICAD_CLI_ALL_PROJECTS"
    governance: GovernanceLintReport
    repository: RepositoryPolicyReport
    product_policy: ProductPolicyReport
    projects: tuple[ProjectCheckSummary, ...]
    status: Literal["PASS", "FAIL"]
