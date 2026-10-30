"""Typed, non-authorizing supplier offer observations and reports."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import AwareDatetime, StringConstraints

from .model_primitives import (
    GitCommit,
    Identifier,
    NonEmptyText,
    NonNegativeCount,
    PositiveCount,
    StrictModel,
)
from .policy_issue_models import PolicyIssue


class SupplierOffer(StrictModel):
    """One manually captured supplier offer; it does not approve a part."""

    id: Identifier
    part_id: Identifier
    supplier: NonEmptyText
    supplier_sku: NonEmptyText
    source_url: NonEmptyText
    region: NonEmptyText
    currency: Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]
    quantity_break: PositiveCount
    unit_price_minor: NonNegativeCount | None = None
    availability: NonEmptyText
    lead_time_days: NonNegativeCount | None = None
    minimum_order_quantity: PositiveCount | None = None
    package_multiple: PositiveCount | None = None


class SourcingSnapshot(StrictModel):
    """Versioned supplier observations captured at a source commit and time."""

    schema_version: Literal["1"] = "1"
    snapshot_id: Identifier
    source_commit: GitCommit
    observed_at: AwareDatetime
    offers: tuple[SupplierOffer, ...]


class SourcingSnapshotReport(StrictModel):
    """Local catalog-reference validation; never authorizes purchasing or builds."""

    schema_version: Literal["1"] = "1"
    lane: Literal["SOURCING_SNAPSHOT"] = "SOURCING_SNAPSHOT"
    build_authorized: Literal[False] = False
    snapshot_id: Identifier
    offers: NonNegativeCount
    status: Literal["PASS", "FAIL"]
    issues: tuple[PolicyIssue, ...]
