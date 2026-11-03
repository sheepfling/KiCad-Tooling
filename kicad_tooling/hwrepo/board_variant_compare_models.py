"""Typed comparison of two retained native board-variant populations."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from pydantic import Field

from .bom_compare_models import Change
from .model_primitives import Digest, Identifier, NonEmptyText, RepositoryPath, StrictModel


class BoardVariantState(StrictModel):
    schematic: Literal["FITTED", "DNP", "ABSENT"]
    board: Literal["FITTED", "DNP", "ABSENT"]
    part_id: str | None = None
    value: str | None = None
    footprint: str | None = None


class BoardVariantReferenceChange(StrictModel):
    reference: NonEmptyText
    change: Change
    before: BoardVariantState | None = None
    after: BoardVariantState | None = None


class BoardVariantQuantityChange(StrictModel):
    part_id: Identifier
    value: str
    footprint: str
    change: Change
    before: int
    after: int
    before_references: tuple[NonEmptyText, ...] = ()
    after_references: tuple[NonEmptyText, ...] = ()


class BoardVariantSide(StrictModel):
    name: str
    evidence_sha256: Mapping[RepositoryPath, Digest]
    unresolved_fitted: tuple[NonEmptyText, ...] = ()


class BoardVariantComparisonReport(StrictModel):
    """One source snapshot and two explicit named KiCad variant observations."""

    schema_version: Literal["1"] = "1"
    lane: Literal["BOARD_VARIANT_COMPARISON"] = "BOARD_VARIANT_COMPARISON"
    build_authorized: Literal[False] = False
    purchase_authorized: Literal[False] = False
    project_id: Identifier
    findings_view: RepositoryPath
    findings_view_sha256: Digest
    lint_report: RepositoryPath
    lint_report_sha256: Digest
    source_hashes: Mapping[RepositoryPath, Digest]
    before: BoardVariantSide
    after: BoardVariantSide
    references: tuple[BoardVariantReferenceChange, ...]
    quantities: tuple[BoardVariantQuantityChange, ...]
    issues: tuple[str, ...] = ()
    output_directory: str
    artifacts_sha256: Mapping[str, Digest] = Field(default_factory=dict)
