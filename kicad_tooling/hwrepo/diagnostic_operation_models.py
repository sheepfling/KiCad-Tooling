"""Typed requests for project diagnosis, import diagnosis, and local rescue."""

from __future__ import annotations

from pathlib import Path
from typing import Self

from pydantic import StrictStr, model_validator

from .model_primitives import StrictModel
from .project_static_pipeline_models import ProjectStaticPipelineReport


class ProjectDiagnosticRequest(StrictModel):
    """Selected project plus optional native and portable evidence for coaching."""

    project_id: StrictStr
    native_report: Path | None = None
    bom: Path | None = None
    portable_report: ProjectStaticPipelineReport | None = None

    @model_validator(mode="after")
    def validate_evidence_scope(self) -> Self:
        if self.bom is not None and self.native_report is None:
            raise ValueError("BOM diagnosis requires the selected project's native_report")
        if self.portable_report is not None and self.portable_report.projects != (self.project_id,):
            raise ValueError("Captured portable report does not match the diagnosed project")
        return self


class ImportDiagnosticRequest(StrictModel):
    """Source path and reviewed project/toolchain selection for import coaching."""

    source: Path
    project_id: StrictStr
    toolchain_id: StrictStr


class ProjectRescueRequest(StrictModel):
    """Selected project island for explicitly partial local inspection."""

    project_id: StrictStr
