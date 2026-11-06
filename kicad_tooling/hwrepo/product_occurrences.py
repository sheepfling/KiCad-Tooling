"""Expand authored product assemblies and bind paths to captured sources."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType

from .product_models import (
    AssemblyKind,
    Occurrence,
    ProductInstancePath,
    ProductOccurrenceMap,
    ProductRecord,
    Variant,
)
from .product_source_inputs import ProductSourceIdentity


@dataclass(frozen=True, slots=True)
class ProductOccurrenceIndex:
    """Read-only expanded hierarchy bound to one exact product source record."""

    source: ProductSourceIdentity
    root_assembly: str
    by_path: ProductOccurrenceMap


def _expand_occurrences(product: ProductRecord) -> dict[ProductInstancePath, Occurrence]:
    """Expand a product tree without silently treating built and purchased alike."""
    assemblies = {assembly.id: assembly for assembly in product.assemblies}
    result: dict[ProductInstancePath, Occurrence] = {}

    def visit(
        item: str, path: ProductInstancePath, quantity: int, ancestry: tuple[str, ...]
    ) -> None:
        if item in ancestry or len(ancestry) > 64:
            raise ValueError("Assembly cycle or excessive nesting")
        if len(result) >= 10_000:
            raise ValueError("Assembly exceeds the v1 limit of 10000 expanded instances")
        result[path] = Occurrence(item=item, quantity=quantity)
        assembly = assemblies.get(item)
        if assembly is not None and assembly.kind is not AssemblyKind.PURCHASED:
            for member in assembly.members:
                child = ProductInstancePath(f"{path}.{member.ref}" if path else member.ref)
                if child in result:
                    raise ValueError(f"Duplicate instance: {child}")
                visit(
                    member.item,
                    child,
                    quantity * member.quantity,
                    (*ancestry, item),
                )

    visit(product.root_assembly, ProductInstancePath(""), 1, ())
    return result


def occurrences(product: ProductRecord) -> ProductOccurrenceMap:
    """Compatibility projection of the expanded product hierarchy."""
    return _expand_occurrences(product)


def product_occurrence_index(source: ProductSourceIdentity) -> ProductOccurrenceIndex:
    """Expand the immutable product record and retain its exact path and digest."""
    by_path = MappingProxyType(_expand_occurrences(source.record))
    return ProductOccurrenceIndex(
        source=source,
        root_assembly=source.record.root_assembly,
        by_path=by_path,
    )


def occurrences_for(product: ProductRecord, index: ProductOccurrenceIndex) -> ProductOccurrenceMap:
    """Require the consumer's record to equal the source record behind its index."""
    if product != index.source.record or product.root_assembly != index.root_assembly:
        raise ValueError("Product occurrence index source identity differs from the product record")
    return index.by_path


def excluded(path: str, variant: Variant) -> bool:
    """Whether an authored variant excludes an instance path or its descendants."""
    return any(path == item or path.startswith(item + ".") for item in variant.exclude)
