"""Typed, currency-separated comparison of dated saved supplier offers."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Literal

from pydantic import AwareDatetime, Field

from .model_primitives import (
    Digest,
    GitCommit,
    Identifier,
    NonEmptyText,
    RepositoryPath,
    StrictModel,
)

OfferFreshness = Literal["CURRENT", "STALE", "FUTURE"]
OfferChange = Literal["ADDED", "REMOVED", "CHANGED", "UNCHANGED"]


class SupplierAnalysisSnapshot(StrictModel):
    snapshot_id: Identifier
    path: RepositoryPath
    sha256: Digest
    source_commit: GitCommit
    observed_at: AwareDatetime
    freshness: OfferFreshness
    validation_status: Literal["PASS", "FAIL"]
    validation_issues: tuple[NonEmptyText, ...] = ()


class SupplierOfferCost(StrictModel):
    offer_id: Identifier
    part_id: Identifier
    supplier: NonEmptyText
    supplier_sku: NonEmptyText
    region: NonEmptyText
    source_url: NonEmptyText
    currency: NonEmptyText
    quantity_break: int
    unit_price_minor: int | None = None
    availability: NonEmptyText
    lead_time_days: int | None = None
    minimum_order_quantity: int | None = None
    package_multiple: int | None = None
    requested_quantity: int | None = None
    order_quantity: int | None = None
    extended_minor: int | None = None
    status: Literal[
        "QUOTED",
        "MISSING_PRICE",
        "PACKAGING_UNKNOWN",
        "BREAK_NOT_MET",
        "NOT_IN_BOM",
        "REVISION_AMBIGUOUS",
    ]


class SupplierOfferDifference(StrictModel):
    part_id: Identifier
    supplier: NonEmptyText
    supplier_sku: NonEmptyText
    quantity_break: int
    change: OfferChange
    before: SupplierOfferCost | None = None
    after: SupplierOfferCost | None = None


class SupplierAnalysisReport(StrictModel):
    schema_version: Literal["1"] = "1"
    lane: Literal["SUPPLIER_ANALYSIS"] = "SUPPLIER_ANALYSIS"
    build_authorized: Literal[False] = False
    purchase_authorized: Literal[False] = False
    project_id: Identifier
    parts_receipt: RepositoryPath
    parts_receipt_sha256: Digest
    parts_source_hashes: Mapping[RepositoryPath, Digest]
    parts_input_hashes: Mapping[RepositoryPath, Digest]
    parts_source_current: bool
    as_of: date
    max_age_days: int = Field(ge=0)
    before: SupplierAnalysisSnapshot
    after: SupplierAnalysisSnapshot
    offers: tuple[SupplierOfferDifference, ...]
    unresolved_references: tuple[Identifier, ...]
    currencies: tuple[NonEmptyText, ...]
    issues: tuple[NonEmptyText, ...] = ()
    output_directory: str
    artifacts_sha256: Mapping[RepositoryPath, Digest] = Field(default_factory=dict)
