"""Resolve explicit release product variants against current repository sources."""

from __future__ import annotations

from pathlib import Path

from .layout import read_repository_layout, require_repository_layout_current
from .product_source_inputs import (
    ProductRecordInput,
    capture_product_record,
    product_record_freshness_issues,
    read_product_index_document,
    require_product_index_document_current,
)
from .release_contract_models import ReleaseVariant


def resolve_variants(root: Path, values: tuple[str, ...]) -> tuple[ReleaseVariant, ...]:
    """Resolve explicit PRODUCT:VARIANT choices to current typed revision identities."""
    if not values:
        return ()
    root = root.resolve()
    layout_document = read_repository_layout(root)
    index_document = read_product_index_document(root, layout_document.value.layout.products)
    index = index_document.value
    indexed = {entry.id: entry for entry in index.products}
    if len(indexed) != len(index.products):
        raise ValueError(f"{layout_document.value.layout.products} has duplicate product IDs")
    selections: list[ReleaseVariant] = []
    product_inputs: dict[str, ProductRecordInput] = {}
    for value in values:
        product_id, separator, variant_id = value.partition(":")
        if not separator:
            raise ValueError("Variant selection uses PRODUCT:VARIANT")
        entry = indexed.get(product_id)
        if entry is None:
            raise ValueError(
                f"Unknown release product {product_id!r} in {layout_document.value.layout.products}"
            )
        product_input = product_inputs.get(product_id)
        if product_input is None:
            product_input = capture_product_record(root, entry)
            product_inputs[product_id] = product_input
        product = product_input.record
        if product_input.state != "EVALUATED" or product is None:
            raise ValueError(
                f"{entry.path}: {product_input.issue or 'product record is unavailable'}"
            )
        if product.id != product_id:
            raise ValueError(
                f"{entry.path}: product ID differs from {layout_document.value.layout.products}"
            )
        variant = next((item for item in product.variants if item.id == variant_id), None)
        if variant is None:
            raise ValueError(f"Unknown variant {variant_id!r} for product {product_id!r}")
        selections.append(
            ReleaseVariant(
                product=product.id,
                product_revision=product.revision,
                variant=variant.id,
                variant_revision=variant.revision,
            )
        )
    require_product_index_document_current(root, index_document)
    freshness_issues = product_record_freshness_issues(root, tuple(product_inputs.values()))
    if freshness_issues:
        raise ValueError("; ".join(freshness_issues))
    require_repository_layout_current(root, layout_document)
    return tuple(selections)
