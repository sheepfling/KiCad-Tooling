"""Typed source and check records returned by native project validation."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Literal

from pydantic import Field

from .model_primitives import (
    Digest,
    Identifier,
    NonEmptyText,
    RepositoryPath,
    StrictModel,
)
from .project_models import ProjectKind
from .source_state_models import SourceState


class NativeProjectValidationRequest(StrictModel):
    """Select the native validation receipt, KiCad CLI, and optional config."""

    output: Path
    cli: NonEmptyText
    config_path: Path | None = None


class CheckEvidence(StrictModel):
    status: Literal["PASS", "FAIL", "NOT_RUN"]
    returncode: int | None = None
    error: NonEmptyText | None = None
    findings: int | None = None
    expected_ignored_checks: tuple[Identifier, ...] = ()
    files: tuple[RepositoryPath, ...] = ()
    source_hashes: Mapping[RepositoryPath, Digest] = Field(default_factory=dict)
    identity_status: Literal["PASS", "NOT_APPLICABLE"] | None = None
    observed_version: NonEmptyText | None = None
    image: NonEmptyText | None = None


class ValidationSummary(StrictModel):
    schema_version: Literal["1"] = "1"
    lane: Literal["KICAD_CLI"] = "KICAD_CLI"
    timestamp_utc: NonEmptyText
    checked_commit: NonEmptyText
    source: SourceState | None = None
    project_id: Identifier | None = None
    pr_head_commit: str | None = None
    assurance_profile: Literal["training", "development", "production"] | None = None
    not_for_manufacture: bool | None = None
    project_kind: ProjectKind | None = None
    checks: Mapping[Identifier, CheckEvidence]
    status: Literal["PASS", "FAIL"]
    artifacts_sha256: Mapping[RepositoryPath, Digest]
