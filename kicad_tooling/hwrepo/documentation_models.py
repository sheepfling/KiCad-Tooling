"""Typed policy, exception, and issue records for repository documentation."""

from __future__ import annotations

from datetime import date
from typing import Literal

from .model_primitives import (
    Identifier,
    NonEmptyText,
    NonNegativeCount,
    PositiveCount,
    RepositoryPath,
    StrictModel,
)


class DocumentationException(StrictModel):
    """A reviewed, path-scoped and time-bounded documentation-policy waiver."""

    id: Identifier
    code: Identifier
    path: RepositoryPath
    reason: NonEmptyText
    expires: date


class DocumentationPolicy(StrictModel):
    """Repository-owned Markdown graph roots and narrow policy exceptions."""

    schema_version: Literal["1"] = "1"
    roots: tuple[RepositoryPath, ...]
    documentation_namespaces: tuple[RepositoryPath, ...] = ()
    exceptions: tuple[DocumentationException, ...] = ()


class DocumentationIssue(StrictModel):
    code: Identifier
    path: RepositoryPath
    line: PositiveCount
    message: NonEmptyText


class DocumentationPolicyReport(StrictModel):
    schema_version: Literal["1"] = "1"
    lane: Literal["MARKDOWN_REPOSITORY_POLICY"] = "MARKDOWN_REPOSITORY_POLICY"
    roots: tuple[RepositoryPath, ...]
    documents: NonNegativeCount
    issues: tuple[DocumentationIssue, ...]
    status: Literal["PASS", "FAIL"]
