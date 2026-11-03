"""Comparison of two explicitly saved product BOM source revisions."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from pydantic import Field

from .bom_compare_models import Change
from .model_primitives import Digest, Identifier, RepositoryPath, StrictModel
from .product_variant_bom_models import VariantBomInstanceState, VariantBomPartDifference


class ProductRevisionSnapshot(StrictModel):
    view: RepositoryPath
    view_sha256: Digest
    product_path: RepositoryPath
    product_sha256: Digest
    parts_catalog_path: RepositoryPath | None = None
    parts_catalog_sha256: Digest | None = None
    product_revision: Identifier
    variant_id: Identifier
    variant_revision: Identifier
    source_relation: Literal["CURRENT", "HISTORICAL", "UNAVAILABLE"]
    view_status: Literal["CURRENT", "REVIEW"]
    issues: tuple[str, ...] = ()


class ProductRevisionInstanceDifference(StrictModel):
    path: str
    change: Change
    before: VariantBomInstanceState | None = None
    after: VariantBomInstanceState | None = None


class ProductRevisionBomReport(StrictModel):
    schema_version: Literal["1"] = "1"
    lane: Literal["PRODUCT_REVISION_BOM_COMPARISON"] = "PRODUCT_REVISION_BOM_COMPARISON"
    build_authorized: Literal[False] = False
    purchase_authorized: Literal[False] = False
    product_id: Identifier
    baseline: ProductRevisionSnapshot
    candidate: ProductRevisionSnapshot
    variant_relation: Literal["SAME", "DIFFERENT"]
    product_path_relation: Literal["SAME", "DIFFERENT"]
    status: Literal["COMPARED", "REVIEW"]
    bom_projection: bool
    instances: tuple[ProductRevisionInstanceDifference, ...]
    parts: tuple[VariantBomPartDifference, ...]
    issues: tuple[str, ...] = ()
    output_directory: str
    artifacts_sha256: Mapping[RepositoryPath, Digest] = Field(default_factory=dict)
