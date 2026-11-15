"""Typed readiness and package reports shared by release operations and surfaces."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from .command_evidence_models import CommandEvidence
from .fabrication_connectivity_models import FabricationConnectivitySummary
from .model_primitives import (
    Digest,
    GitCommit,
    Identifier,
    NonEmptyText,
    RepositoryPath,
    StrictModel,
)
from .policy_issue_models import PolicyIssue
from .project_models import ReleaseExportSettings
from .release_model_types import ReleaseClass
from .source_state_models import SourceState


class ReleaseExportReport(StrictModel):
    schema_version: Literal["1"] = "1"
    project_id: Identifier
    source: SourceState
    toolchain_id: Identifier
    settings: ReleaseExportSettings
    assembly_variant: NonEmptyText | None = None
    commands: Mapping[Identifier, CommandEvidence]
    artifacts_sha256: Mapping[RepositoryPath, Digest]
    status: Literal["PASS", "FAIL"]
    issues: tuple[NonEmptyText, ...] = ()
    artifact_connectivity: FabricationConnectivitySummary | None = None


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
