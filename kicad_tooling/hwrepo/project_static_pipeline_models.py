"""Typed inputs for the selected-project portable policy lane."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Literal

from pydantic import Field

from .command_evidence_models import CommandEvidence
from .governance_lint_models import GovernanceLintReport
from .model_primitives import Identifier, NonEmptyText, StrictModel
from .product_models import ProductPolicyReport
from .repository_policy_models import RepositoryPolicyReport


class ProjectStaticPipelineRequest(StrictModel):
    """Selected project scope and bounded worker count for portable checks."""

    project_ids: tuple[Identifier, ...]
    workers: Annotated[int, Field(ge=1)] = 1


class GenerationReport(StrictModel):
    status: Literal["PASS", "FAIL"]
    issues: tuple[NonEmptyText, ...]


class ProjectTestsReport(StrictModel):
    status: Literal["PASS", "FAIL"]
    commands: Mapping[Identifier, CommandEvidence]


class ProjectStaticPipelineReport(StrictModel):
    """Fast local policy result for explicitly selected design projects."""

    status: Literal["PASS", "FAIL"]
    scope: Literal["project_static"] = "project_static"
    build_authorized: Literal[False] = False
    projects: tuple[Identifier, ...]
    registry: GovernanceLintReport
    repository: RepositoryPolicyReport
    product: ProductPolicyReport
    generation: GenerationReport
    project_tests: ProjectTestsReport
