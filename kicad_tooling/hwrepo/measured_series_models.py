"""Typed evidence for one explicitly mapped local measurement CSV."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from pydantic import Field

from .model_primitives import Digest, Identifier, NonEmptyText, RepositoryPath, StrictModel


class MeasuredChannel(StrictModel):
    column: NonEmptyText
    unit: NonEmptyText


class MeasuredSeriesReport(StrictModel):
    schema_version: Literal["1"] = "1"
    lane: Literal["MEASURED_SERIES"] = "MEASURED_SERIES"
    status: Literal["PASS", "FAIL"]
    project_id: Identifier
    source: RepositoryPath
    source_sha256: Digest
    time_column: NonEmptyText
    time_unit: Literal["s", "ms", "us", "ns", "iso8601"]
    channels: tuple[MeasuredChannel, ...]
    samples: int = 0
    output_directory: str
    errors: tuple[str, ...] = ()
    artifacts_sha256: Mapping[RepositoryPath, Digest] = Field(default_factory=dict)
