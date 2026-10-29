"""Typed bounded file reads and project-source edit results."""

from __future__ import annotations

from typing import Literal

from .model_primitives import (
    Digest,
    Identifier,
    NonEmptyText,
    NonNegativeCount,
    RepositoryPath,
    StrictModel,
)


class McpFileContent(StrictModel):
    """Bounded Unicode text or metadata; offsets count characters, never bytes."""

    schema_version: Literal["1"] = "1"
    build_authorized: Literal[False] = False
    path: RepositoryPath
    sha256: Digest
    size_bytes: NonNegativeCount
    content_kind: Literal["text", "binary", "metadata_only"]
    text: str | None = None
    offset: NonNegativeCount
    total_characters: NonNegativeCount | None = None
    truncated: bool = False
    next_offset: NonNegativeCount | None = None
    note: str | None = None


class McpEditPreview(StrictModel):
    """A proposed exact replacement, without a claim of engineering validation."""

    schema_version: Literal["1"] = "1"
    build_authorized: Literal[False] = False
    checks_required: Literal[True] = True
    project_id: Identifier
    path: RepositoryPath
    before_sha256: Digest
    after_sha256: Digest
    diff: str
    validation: Literal["JSON_MODEL", "TEXT_ONLY"]
    next_command: NonEmptyText


class McpEditResult(StrictModel):
    schema_version: Literal["1"] = "1"
    build_authorized: Literal[False] = False
    checks_required: Literal[True] = True
    status: Literal["APPLIED"] = "APPLIED"
    project_id: Identifier
    path: RepositoryPath
    before_sha256: Digest
    after_sha256: Digest
    readback_sha256: Digest
    next_command: NonEmptyText
