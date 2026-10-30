"""Typed, read-only onboarding review before an explicit project import."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from pydantic import Field

from .model_primitives import Digest, Identifier, RepositoryPath, StrictModel
from .models import DiagnosticReport
from .project_models import ProjectImportReport, ProjectKind, ToolchainRecord


class ImportReviewFile(StrictModel):
    path: str
    role: Literal["PROJECT", "SCHEMATIC", "PCB", "LIBRARY", "OTHER", "UNSUPPORTED"]
    disposition: Literal["INCLUDED", "EXCLUDED", "MISSING", "UNSUPPORTED"]
    sha256: Digest | None = None
    reason: str = ""


class ImportReviewDependency(StrictModel):
    source_location: str
    kind: Literal["LIBRARY", "MODEL"]
    reference: str
    status: Literal[
        "PROJECT_LOCAL",
        "PINNED_LIBRARY",
        "EMBEDDED_DECLARED",
        "MISSING",
        "NONPORTABLE",
        "UNRESOLVED",
    ]
    issue: str = ""


class ImportReviewReport(StrictModel):
    schema_version: Literal["1"] = "1"
    lane: Literal["IMPORT_REVIEW"] = "IMPORT_REVIEW"
    build_authorized: Literal[False] = False
    copied: Literal[False] = False
    status: Literal["PREVIEW_CLEAR", "NEEDS_WORK", "UNSUPPORTED_FORMAT"]
    project_id: Identifier
    source_project: str
    source_project_sha256: Digest | None = None
    source_kind: ProjectKind | None = None
    toolchain_id: Identifier
    toolchain: ToolchainRecord | None = None
    repository_inputs_sha256: Mapping[RepositoryPath, Digest] = Field(default_factory=dict)
    preview: ProjectImportReport
    diagnosis: DiagnosticReport
    files: tuple[ImportReviewFile, ...] = ()
    dependencies: tuple[ImportReviewDependency, ...] = ()
    issues: tuple[str, ...] = ()
    output_directory: str
    artifacts_sha256: Mapping[RepositoryPath, Digest] = Field(default_factory=dict)
