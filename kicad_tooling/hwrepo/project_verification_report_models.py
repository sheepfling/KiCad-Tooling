"""Typed result model for one selected-project verification run."""

from __future__ import annotations

from typing import Literal

from .command_evidence_models import CommandEvidence
from .design_lint_report_models import DesignLintReport
from .diagnostics_models import DiagnosticReport
from .doctor_models import TemplateDoctorReport
from .electrical_report_models import ElectricalAnalysisReport
from .model_primitives import Identifier, NonEmptyText, StrictModel
from .native_project_check_models import CheckAllSummary
from .project_static_pipeline_models import ProjectStaticPipelineReport


class ProjectVerificationReport(StrictModel):
    """One local project attempt with retained portable and optional native evidence."""

    schema_version: Literal["1"] = "1"
    lane: Literal["PROJECT_VERIFY"] = "PROJECT_VERIFY"
    build_authorized: Literal[False] = False
    project_id: Identifier
    depth: Literal["portable", "native", "electrical"]
    runner: Literal["none", "local", "container"] = "none"
    run_directory: NonEmptyText
    portable: ProjectStaticPipelineReport | None = None
    doctor: TemplateDoctorReport | None = None
    dependency_command: CommandEvidence | None = None
    native_command: CommandEvidence | None = None
    native: CheckAllSummary | None = None
    design_lint: DesignLintReport | None = None
    electrical: ElectricalAnalysisReport | None = None
    diagnosis: DiagnosticReport | None = None
    status: Literal["PASS", "FAIL", "ERROR"]
    next_actions: tuple[NonEmptyText, ...] = ()
    error: str | None = None
