"""Typed inventory for an explicitly selected project review overview."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from pydantic import Field

from .model_primitives import Digest, Identifier, NonEmptyText, RepositoryPath, StrictModel

OverviewKind = Literal["native", "findings", "parts", "three_d", "simulation", "verification"]
Freshness = Literal["CURRENT", "STALE", "MISSING", "UNAVAILABLE", "UNKNOWN", "NOT_SELECTED"]


class OverviewLink(StrictModel):
    label: NonEmptyText
    path: RepositoryPath
    sha256: Digest
    receipt_bound: bool


class OverviewItem(StrictModel):
    kind: OverviewKind
    selected_path: RepositoryPath | None = None
    status: NonEmptyText = "NOT_SELECTED"
    freshness: Freshness = "NOT_SELECTED"
    report_sha256: Digest | None = None
    source_commit: str | None = None
    source_hashes: Mapping[RepositoryPath, Digest] = Field(default_factory=dict)
    links: tuple[OverviewLink, ...] = ()
    issues: tuple[NonEmptyText, ...] = ()


class ReviewOverviewReport(StrictModel):
    """A navigation snapshot; statuses remain those of their original receipts."""

    schema_version: Literal["1"] = "1"
    lane: Literal["PROJECT_REVIEW_OVERVIEW"] = "PROJECT_REVIEW_OVERVIEW"
    build_authorized: Literal[False] = False
    project_id: Identifier
    project_manifest: RepositoryPath
    project_manifest_sha256: Digest
    toolchain_id: Identifier
    kicad_version: NonEmptyText
    current_source_hashes: Mapping[RepositoryPath, Digest]
    items: tuple[OverviewItem, ...]
    output_directory: str
    artifacts_sha256: Mapping[RepositoryPath, Digest] = Field(default_factory=dict)
