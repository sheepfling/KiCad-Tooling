"""Typed order-review records and DigiKey payload contracts."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from pydantic import Field

from .contract_coach_models import ContractCoachReport
from .model_primitives import (
    Digest,
    Identifier,
    NonEmptyText,
    NonNegativeCount,
    PositiveCount,
    RepositoryPath,
    StrictModel,
)
from .purchasing_preference_models import PurchasingPreferences, PurchasingSchemaModel


class PurchasingComponent(StrictModel):
    reference: Identifier
    value: str
    footprint: str
    part_id: str | None = None
    dnp: bool = False
    exclude_from_bom: bool = False


class PurchasingLine(StrictModel):
    part_id: Identifier
    revision: Identifier
    manufacturer: NonEmptyText
    mpn: NonEmptyText
    footprint: NonEmptyText
    references: tuple[Identifier, ...]
    per_board: PositiveCount
    required: PositiveCount
    spares: NonNegativeCount
    quantity: PositiveCount
    order_number: NonEmptyText
    order_number_kind: Literal["MPN", "DigiKey"]
    search_url: NonEmptyText


class PurchasingFinding(StrictModel):
    code: Identifier
    references: tuple[Identifier, ...] = ()
    message: NonEmptyText
    action: NonEmptyText


class PurchasingPlan(PurchasingSchemaModel):
    """Metadata readiness for human ordering review, never electrical approval."""

    schema_version: Literal["1"] = "1"
    status: Literal["NEEDS_PARTS", "READY_FOR_ORDER_REVIEW"]
    preferences: PurchasingPreferences
    components: tuple[PurchasingComponent, ...]
    lines: tuple[PurchasingLine, ...]
    findings: tuple[PurchasingFinding, ...]
    excluded_references: tuple[Identifier, ...] = ()
    purchase_authorized: Literal[False] = False
    build_authorized: Literal[False] = False


class PurchasingReport(PurchasingSchemaModel):
    """Source-bound local parts assistant receipt."""

    schema_version: Literal["1"] = "1"
    lane: Literal["PARTS_TO_ORDER"] = "PARTS_TO_ORDER"
    project_id: Identifier
    status: Literal["BLOCKED", "NEEDS_PARTS", "READY_FOR_ORDER_REVIEW"]
    purchase_authorized: Literal[False] = False
    build_authorized: Literal[False] = False
    plan: PurchasingPlan | None = None
    source_hashes: Mapping[RepositoryPath, Digest] = Field(default_factory=dict)
    input_hashes: Mapping[RepositoryPath, Digest] = Field(default_factory=dict)
    netlist_sha256: Digest | None = None
    native_status: Literal["PASS", "FAIL"] | None = None
    selected_runner: Literal["local", "container"] | None = None
    issues: tuple[NonEmptyText, ...] = ()
    next_actions: tuple[NonEmptyText, ...] = ()
    receipt_dir: str
    artifacts: tuple[str, ...] = ()
    evidence: ContractCoachReport | None = None
