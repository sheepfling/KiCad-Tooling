"""Saved, source-bound result of one read-only release readiness check."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from types import MappingProxyType
from typing import Annotated, Literal, TypeAlias

from pydantic import Field, PlainSerializer, model_validator

from .model_primitives import Digest, GitCommit, RepositoryPath, StrictModel
from .release_report_models import ReleaseReadinessReport
from .source_state_models import SerializedPathDigestInventory

DeclaredFileHashes: TypeAlias = Mapping[RepositoryPath, Digest | None]


def serialize_declared_file_hashes(
    value: DeclaredFileHashes,
) -> dict[RepositoryPath, Digest | None]:
    return dict(value)


SerializedDeclaredFileHashes: TypeAlias = Annotated[
    DeclaredFileHashes,
    PlainSerializer(
        serialize_declared_file_hashes,
        return_type=dict[RepositoryPath, Digest | None],
        when_used="always",
    ),
]


class ReleaseDependencyInventory(StrictModel):
    """Hash observations plus whether nested report artifacts were enumerable."""

    declared_files_sha256: SerializedDeclaredFileHashes
    artifact_enumeration_complete: bool

    @model_validator(mode="after")
    def freeze_hashes(self) -> ReleaseDependencyInventory:
        frozen = MappingProxyType(dict(self.declared_files_sha256))
        object.__setattr__(self, "declared_files_sha256", frozen)
        return self


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
    source_hashes: SerializedPathDigestInventory
    declared_files_sha256: SerializedDeclaredFileHashes
    readiness: ReleaseReadinessReport
    output_directory: str
    artifacts_sha256: SerializedPathDigestInventory = Field(default_factory=dict)

    @model_validator(mode="after")
    def freeze_hash_indexes(self) -> ReleaseReadinessViewReport:
        object.__setattr__(self, "source_hashes", MappingProxyType(dict(self.source_hashes)))
        object.__setattr__(
            self, "declared_files_sha256", MappingProxyType(dict(self.declared_files_sha256))
        )
        object.__setattr__(self, "artifacts_sha256", MappingProxyType(dict(self.artifacts_sha256)))
        return self
