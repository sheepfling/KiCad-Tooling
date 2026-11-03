"""Saved, source-bound result of one read-only release readiness check."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Literal

from pydantic import Field

from .model_primitives import Digest, GitCommit, RepositoryPath, StrictModel
from .release_report_models import ReleaseReadinessReport


class ReleaseReadinessViewReport(StrictModel):
    schema_version: Literal["1"] = "1"
    lane: Literal["RELEASE_READINESS_VIEW"] = "RELEASE_READINESS_VIEW"
    build_authorized: Literal[False] = False
    manifest: RepositoryPath
    manifest_sha256: Digest
    source_commit: GitCommit
    source_stable: bool
    dependency_inventory_complete: bool
    checked_on: date
    source_hashes: Mapping[RepositoryPath, Digest]
    declared_files_sha256: Mapping[RepositoryPath, Digest | None]
    readiness: ReleaseReadinessReport
    output_directory: str
    artifacts_sha256: Mapping[RepositoryPath, Digest] = Field(default_factory=dict)
