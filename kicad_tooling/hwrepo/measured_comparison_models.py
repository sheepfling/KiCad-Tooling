"""Typed evidence for a selected pair of measured time-series receipts."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from pydantic import Field

from .model_primitives import Digest, Identifier, NonEmptyText, RepositoryPath, StrictModel


class MeasuredRunIdentity(StrictModel):
    receipt: RepositoryPath
    receipt_sha256: Digest
    source: RepositoryPath
    source_sha256: Digest
    source_state: Literal["CURRENT", "CHANGED", "MISSING", "UNAVAILABLE"]
    observed_source_sha256: Digest | None = None
    channel: NonEmptyText
    unit: NonEmptyText
    samples: int
    first_time_seconds: str
    last_time_seconds: str


class MeasuredComparisonReport(StrictModel):
    schema_version: Literal["1"] = "1"
    lane: Literal["MEASURED_SERIES_COMPARISON"] = "MEASURED_SERIES_COMPARISON"
    project_id: Identifier
    alignment: Literal["absolute", "elapsed"]
    channel: NonEmptyText
    unit: NonEmptyText
    baseline: MeasuredRunIdentity
    candidate: MeasuredRunIdentity
    source_status: Literal["CURRENT", "HISTORICAL"]
    overlap: Literal["OVERLAP", "DISJOINT"]
    display_points_baseline: int
    display_points_candidate: int
    output_directory: str
    artifacts_sha256: Mapping[RepositoryPath, Digest] = Field(default_factory=dict)
