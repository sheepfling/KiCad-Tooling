"""Typed source-bound comparison of two authored product variant BOMs."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from pydantic import Field

from .bom_compare_models import Change
from .model_primitives import Digest, Identifier, RepositoryPath, StrictModel
from .product_models import BomRow


class VariantBomInstanceState(StrictModel):
    item: str
    part_id: str | None = None
    revision: str | None = None
    quantity: int
    population: Literal["INCLUDED", "OMITTED", "UNRESOLVED"]


class VariantBomInstanceDifference(StrictModel):
    path: str
    change: Change
    before: VariantBomInstanceState
    after: VariantBomInstanceState


class VariantBomPartDifference(StrictModel):
    part_id: Identifier
    revision: Identifier
    change: Change
    before: BomRow | None = None
    after: BomRow | None = None


class ProductVariantBomReport(StrictModel):
    schema_version: Literal["1"] = "1"
    lane: Literal["PRODUCT_VARIANT_BOM_COMPARISON"] = "PRODUCT_VARIANT_BOM_COMPARISON"
    build_authorized: Literal[False] = False
    purchase_authorized: Literal[False] = False
    product_id: Identifier
    product_revision: Identifier
    before_variant: Identifier
    before_variant_revision: Identifier
    after_variant: Identifier
    after_variant_revision: Identifier
    product_path: RepositoryPath
    product_sha256: Digest
    source_hashes: Mapping[RepositoryPath, Digest]
    before_view_sha256: Digest
    after_view_sha256: Digest
    status: Literal["CURRENT", "REVIEW"]
    bom_projection: bool
    issues: tuple[str, ...] = ()
    instances: tuple[VariantBomInstanceDifference, ...]
    parts: tuple[VariantBomPartDifference, ...]
    output_directory: str
    artifacts_sha256: Mapping[RepositoryPath, Digest] = Field(default_factory=dict)
