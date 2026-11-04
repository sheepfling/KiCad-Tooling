"""Typed source identity observed from a repository checkout."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TypeAlias

from pydantic import Field

from .model_primitives import Digest, GitCommit, RepositoryPath, StrictModel

SourceHashInventory: TypeAlias = Mapping[RepositoryPath, Digest]


class SourceState(StrictModel):
    """Observed Git identity and source bytes, never a caller-supplied assertion."""

    commit: GitCommit | None = None
    clean: bool = False
    files_sha256: SourceHashInventory = Field(default_factory=dict)
