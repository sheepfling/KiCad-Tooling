"""Typed result records for product repository composition."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from .models import InterfaceRecord
from .part_catalog_models import PartRecord
from .policy_issue_models import PolicyIssue
from .product_models import ProductRecord
from .product_source_inputs import (
    ProductIndexDocument,
    ProductRecordInput,
    ProductSourceIdentity,
)
from .project_models import ProjectRecord


@dataclass(frozen=True, slots=True)
class ProductRepository:
    """Validated records and read-only lookup snapshots bound to captured inputs."""

    products: tuple[ProductRecord, ...]
    product_project_ids: Mapping[str, tuple[str, ...]]
    parts: Mapping[str, PartRecord]
    interfaces: Mapping[str, InterfaceRecord]
    projects: Mapping[str, ProjectRecord]
    product_sources: Mapping[str, ProductSourceIdentity]
    issues: tuple[PolicyIssue, ...]
    record_inputs: tuple[ProductRecordInput, ...] = ()
    product_index_document: ProductIndexDocument | None = None

    def __post_init__(self) -> None:
        """Detach each lookup from its builder and prevent post-capture mutation."""
        object.__setattr__(
            self, "product_project_ids", MappingProxyType(dict(self.product_project_ids))
        )
        object.__setattr__(self, "parts", MappingProxyType(dict(self.parts)))
        object.__setattr__(self, "interfaces", MappingProxyType(dict(self.interfaces)))
        object.__setattr__(self, "projects", MappingProxyType(dict(self.projects)))
        object.__setattr__(self, "product_sources", MappingProxyType(dict(self.product_sources)))
