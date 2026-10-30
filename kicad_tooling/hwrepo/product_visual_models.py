"""Typed source-bound product hierarchy and relation review records."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from pydantic import Field

from .model_primitives import Digest, Identifier, RepositoryPath, StrictModel
from .product_models import HarnessScheduleRow


class ProductVisualInstance(StrictModel):
    path: str
    parent: str | None = None
    item: str
    quantity: int
    kind: Literal["BUILT", "PHANTOM", "PURCHASED", "PART", "UNRESOLVED"]
    population: Literal["INCLUDED", "OMITTED"]
    project_id: Identifier | None = None


class ProductVisualEndpoint(StrictModel):
    terminal_id: Identifier
    instance: str | None = None
    pin: str | None = None
    interface_id: Identifier | None = None
    interface_pin: str | None = None
    status: Literal["RESOLVED", "MISSING", "OMITTED"]


class ProductVisualRelation(StrictModel):
    id: Identifier
    kind: Literal["electrical", "functional", "mechanical", "protocol"]
    from_endpoint: ProductVisualEndpoint
    to_endpoint: ProductVisualEndpoint
    harness: Identifier | None = None
    assurance: str
    evidence: tuple[Identifier, ...] = ()
    population: Literal["INCLUDED", "OMITTED", "UNRESOLVED"]
    origin: Literal["AUTHORED"] = "AUTHORED"


class ProductProjectIdentity(StrictModel):
    project_id: Identifier
    config_path: RepositoryPath | None = None
    config_sha256: Digest | None = None
    source_hashes: Mapping[RepositoryPath, Digest] = Field(default_factory=dict)
    status: Literal["CURRENT", "MISSING", "UNAVAILABLE"]
    issue: str | None = None


class ProductVisualReport(StrictModel):
    """Authored product relationships, never observed wiring or build approval."""

    schema_version: Literal["1"] = "1"
    lane: Literal["PRODUCT_VISUAL_REVIEW"] = "PRODUCT_VISUAL_REVIEW"
    build_authorized: Literal[False] = False
    observed_wiring: Literal[False] = False
    product_id: Identifier
    product_revision: Identifier
    variant_id: Identifier
    variant_revision: Identifier
    status: Literal["CURRENT", "REVIEW"]
    product_path: RepositoryPath
    product_sha256: Digest
    source_hashes: Mapping[RepositoryPath, Digest]
    projects: tuple[ProductProjectIdentity, ...]
    instances: tuple[ProductVisualInstance, ...]
    relations: tuple[ProductVisualRelation, ...]
    harnesses: tuple[HarnessScheduleRow, ...] = ()
    system_projection: bool
    harness_projection: bool
    open_items: tuple[str, ...] = ()
    issues: tuple[str, ...] = ()
    output_directory: str
    artifacts_sha256: Mapping[str, Digest] = Field(default_factory=dict)
