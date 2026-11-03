"""Typed readiness and package reports shared by release operations and surfaces."""

from __future__ import annotations

from typing import Literal

from .model_primitives import Digest, GitCommit, Identifier, RepositoryPath, StrictModel
from .policy_issue_models import PolicyIssue
from .release_model_types import ReleaseClass


class ReleaseReadinessReport(StrictModel):
    schema_version: Literal["1"] = "1"
    lane: Literal["RELEASE_READINESS"] = "RELEASE_READINESS"
    build_authorized: Literal[False] = False
    release_id: Identifier
    release_class: ReleaseClass
    status: Literal["PASS", "FAIL"]
    issues: tuple[PolicyIssue, ...]


class ReleasePackageReport(StrictModel):
    status: Literal["PASS", "FAIL"]
    source_commit: GitCommit
    package: str
    package_sha256: Digest
    manifest: RepositoryPath
    build_authorized: Literal[False] = False
