"""Typed source identity observed from a repository checkout."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Annotated, Protocol, Self, TypeAlias, TypeVar, cast

from pydantic import Field, PlainSerializer, model_validator

from .model_primitives import Digest, GitCommit, RepositoryPath, StrictModel

PathDigestInventory: TypeAlias = Mapping[RepositoryPath, Digest]
SourceHashInventory: TypeAlias = PathDigestInventory
SourcePreconditionInventory: TypeAlias = Mapping[RepositoryPath, Digest | None]


class _SourceIndexFields(Protocol):
    preconditions: SourcePreconditionInventory
    after_hashes: PathDigestInventory


_SourceIndexFieldsT = TypeVar("_SourceIndexFieldsT", bound=_SourceIndexFields)


def freeze_source_index_mappings(value: _SourceIndexFieldsT) -> _SourceIndexFieldsT:
    """Copy source-index mappings into read-only views on plan models."""
    object.__setattr__(value, "preconditions", MappingProxyType(dict(value.preconditions)))
    object.__setattr__(value, "after_hashes", MappingProxyType(dict(value.after_hashes)))
    return value


class SourceIndexPlan(StrictModel):
    """Shared in-memory immutability contract for source-edit plan models."""

    @model_validator(mode="after")
    def freeze_source_index_maps(self) -> Self:
        return cast(
            Self,
            freeze_source_index_mappings(cast(_SourceIndexFields, self)),
        )


def serialize_path_digest_inventory(value: PathDigestInventory) -> dict[RepositoryPath, Digest]:
    return dict(value)


def serialize_source_precondition_inventory(
    value: SourcePreconditionInventory,
) -> dict[RepositoryPath, Digest | None]:
    return dict(value)


SerializedPathDigestInventory: TypeAlias = Annotated[
    PathDigestInventory,
    PlainSerializer(
        serialize_path_digest_inventory,
        return_type=dict[RepositoryPath, Digest],
        when_used="always",
    ),
]

SerializedSourcePreconditionInventory: TypeAlias = Annotated[
    SourcePreconditionInventory,
    PlainSerializer(
        serialize_source_precondition_inventory,
        return_type=dict[RepositoryPath, Digest | None],
        when_used="always",
    ),
]


class SourceState(StrictModel):
    """Observed Git identity and source bytes, never a caller-supplied assertion."""

    commit: GitCommit | None = None
    clean: bool = False
    files_sha256: SerializedPathDigestInventory = Field(default_factory=dict)

    @model_validator(mode="after")
    def freeze_file_hashes(self) -> SourceState:
        object.__setattr__(self, "files_sha256", MappingProxyType(dict(self.files_sha256)))
        return self
