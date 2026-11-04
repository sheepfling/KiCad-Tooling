"""Typed report for the repository-wide static policy pipeline."""

from __future__ import annotations

from typing import Literal

from pydantic import model_validator

from .command_evidence_models import CommandEvidence
from .documentation_models import DocumentationPolicyReport
from .governance_lint_models import GovernanceLintReport
from .model_primitives import NonEmptyText, StrictModel
from .product_models import ProductPolicyReport
from .project_static_pipeline_models import GenerationReport, ProjectTestsReport
from .repository_policy_models import RepositoryPolicyReport
from .source_state_models import SourceState


class StaticPipelineReport(StrictModel):
    status: Literal["PASS", "FAIL"]
    source: SourceState | None = None
    scope: Literal["static_only", "repository_static"] = "static_only"
    tooling_version: NonEmptyText | None = None
    build_authorized: Literal[False] = False
    registry: GovernanceLintReport
    repository: RepositoryPolicyReport
    documentation: DocumentationPolicyReport
    rumdl: CommandEvidence
    mdrepo: CommandEvidence
    product: ProductPolicyReport
    generation: GenerationReport
    ruff: CommandEvidence | None = None
    pyright: CommandEvidence | None = None
    unit_tests: CommandEvidence | None = None
    project_tests: ProjectTestsReport

    @model_validator(mode="after")
    def explicit_tooling_boundary(self) -> StaticPipelineReport:
        if self.scope == "static_only" and any(
            command is None for command in (self.ruff, self.pyright, self.unit_tests)
        ):
            raise ValueError("Legacy full reports require all tooling quality commands")
        if self.scope == "repository_static" and self.tooling_version is None:
            raise ValueError(
                "Project repository reports must identify the installed tooling version"
            )
        return self
