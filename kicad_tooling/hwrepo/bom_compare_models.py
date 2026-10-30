"""Typed differences between two explicitly selected parts receipts."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from pydantic import Field

from .model_primitives import Digest, Identifier, RepositoryPath, StrictModel

Change = Literal["ADDED", "REMOVED", "CHANGED", "UNCHANGED"]
Population = Literal["FITTED", "DNP", "EXCLUDED", "UNRESOLVED"]


class BomReferenceState(StrictModel):
    part_id: str | None = None
    revision: str | None = None
    population: Population
    value: str
    footprint: str
    issue_codes: tuple[Identifier, ...] = ()


class BomReferenceDifference(StrictModel):
    reference: Identifier
    change: Change
    before: BomReferenceState | None = None
    after: BomReferenceState | None = None


class BomQuantityState(StrictModel):
    references: tuple[Identifier, ...]
    per_board: int
    required: int
    spares: int
    quantity: int


class BomQuantityDifference(StrictModel):
    part_id: Identifier
    revision: Identifier
    change: Change
    before: BomQuantityState | None = None
    after: BomQuantityState | None = None


class BomComparisonReport(StrictModel):
    schema_version: Literal["1"] = "1"
    lane: Literal["BOM_COMPARISON"] = "BOM_COMPARISON"
    build_authorized: Literal[False] = False
    purchase_authorized: Literal[False] = False
    project_id: Identifier
    before_receipt: RepositoryPath
    after_receipt: RepositoryPath
    before_report_sha256: Digest
    after_report_sha256: Digest
    before_source_hashes: Mapping[RepositoryPath, Digest]
    after_source_hashes: Mapping[RepositoryPath, Digest]
    source_scope: Literal["SAME_PATHS", "DIFFERENT_PATHS"]
    variant_scope: Literal["NOT_RECORDED"] = "NOT_RECORDED"
    before_status: str
    after_status: str
    references: tuple[BomReferenceDifference, ...]
    quantities: tuple[BomQuantityDifference, ...]
    output_directory: str
    artifacts_sha256: Mapping[RepositoryPath, Digest] = Field(default_factory=dict)
