"""Typed review of one authored return net against retained native observations."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from pydantic import Field

from .model_primitives import (
    Digest,
    Identifier,
    NetName,
    NonEmptyText,
    Reference,
    RepositoryPath,
    StrictModel,
)


class GroundingPinView(StrictModel):
    pin: Reference
    expected_net: NetName | None = None
    observed_nets: tuple[NetName, ...] = ()
    status: Literal[
        "MATCH", "DIFFERENT", "MISSING", "UNCONNECTED", "AMBIGUOUS", "UNDECLARED", "UNREVIEWED"
    ]


class GroundingViewReport(StrictModel):
    schema_version: Literal["1"] = "1"
    lane: Literal["GROUNDING_VIEW"] = "GROUNDING_VIEW"
    build_authorized: Literal[False] = False
    project_id: Identifier
    net: NetName
    basis: NonEmptyText
    source_receipt: RepositoryPath
    source_report_sha256: Digest
    requirements_sha256: Digest
    observed_sha256: Digest | None = None
    observation_status: Literal["RETAINED", "UNREVIEWED"]
    source_status: Literal["CURRENT", "STALE", "UNKNOWN", "UNAVAILABLE"] = "UNKNOWN"
    pins: tuple[GroundingPinView, ...]
    output_directory: str
    artifacts_sha256: Mapping[RepositoryPath, Digest] = Field(default_factory=dict)
