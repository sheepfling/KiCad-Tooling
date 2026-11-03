"""Typed finding and report contracts for project diagnostics and rescue."""

from __future__ import annotations

from typing import Literal

from .model_primitives import NonEmptyText, RepositoryPath, StrictModel


class DiagnosticFinding(StrictModel):
    """One observed failure or review task with a concrete repair path."""

    severity: Literal["BLOCKING", "REVIEW"]
    code: NonEmptyText
    location: NonEmptyText
    observed: NonEmptyText
    action: NonEmptyText
    guide: RepositoryPath


class DiagnosticReport(StrictModel):
    """A local coaching view; success never constitutes engineering approval."""

    schema_version: Literal["1"] = "1"
    lane: Literal["PROJECT_DIAGNOSTICS"] = "PROJECT_DIAGNOSTICS"
    build_authorized: Literal[False] = False
    project_id: NonEmptyText
    scope: Literal["import", "project"]
    status: Literal["PASS", "NEEDS_WORK"]
    findings: tuple[DiagnosticFinding, ...]
    next_command: NonEmptyText
    follow_up_command: NonEmptyText | None = None
    run_directory: str | None = None


class LocalRescueReport(StrictModel):
    """Partial, read-only island inspection that cannot satisfy repository gates."""

    schema_version: Literal["1"] = "1"
    lane: Literal["LOCAL_PROJECT_RESCUE"] = "LOCAL_PROJECT_RESCUE"
    status: Literal["UNVERIFIED_GLOBAL"] = "UNVERIFIED_GLOBAL"
    build_authorized: Literal[False] = False
    ci_eligible: Literal[False] = False
    release_eligible: Literal[False] = False
    project_id: NonEmptyText
    selected_manifest: RepositoryPath | None = None
    local_inspection: Literal["CLEAR", "NEEDS_REPAIR"]
    findings: tuple[DiagnosticFinding, ...] = ()
    omitted_checks: tuple[NonEmptyText, ...]
    next_command: NonEmptyText
    run_directory: NonEmptyText
