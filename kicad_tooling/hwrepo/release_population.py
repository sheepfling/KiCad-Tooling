"""Resolve source-bound product populations and compare native fitted BOMs."""

from __future__ import annotations

import csv
from collections.abc import Iterable, Mapping
from pathlib import Path

from .product_models import ProductRecord
from .product_occurrences import (
    ProductOccurrenceIndex,
    excluded,
    occurrences,
    occurrences_for,
    product_occurrence_index,
)
from .product_source_inputs import ProductSourceIdentity
from .release_contract_models import ReleaseVariant


def expected_board_population(
    product: ProductRecord,
    variant_id: str,
    project_id: str,
    *,
    occurrence_index: ProductOccurrenceIndex | None = None,
) -> dict[str, str] | None:
    """Resolve the fitted reference/part identities for every included board occurrence."""
    variant = next((item for item in product.variants if item.id == variant_id), None)
    if variant is None:
        raise ValueError(f"Unknown product variant {product.id}:{variant_id}")
    board_assemblies = {
        assembly.id: assembly
        for assembly in product.assemblies
        if assembly.project_id == project_id
    }
    populations: list[dict[str, str]] = []
    instance_index = (
        occurrences(product)
        if occurrence_index is None
        else occurrences_for(product, occurrence_index)
    )
    for path, occurrence in instance_index.items():
        assembly = board_assemblies.get(occurrence.item)
        if assembly is None or excluded(path, variant):
            continue
        population: dict[str, str] = {}
        for member in assembly.members:
            if not excluded(f"{path}.{member.ref}", variant):
                population[member.ref] = member.item
        populations.append(population)
    if not populations:
        return None
    if any(population != populations[0] for population in populations[1:]):
        raise ValueError(
            f"Product {product.id}:{variant_id} uses different populations of "
            f"board {project_id}; prepare separate board variants"
        )
    return populations[0]


def verify_board_population(
    products: Iterable[ProductRecord],
    selections: tuple[ReleaseVariant, ...],
    project_id: str,
    bom_path: Path,
    *,
    product_sources: Mapping[str, ProductSourceIdentity] | None = None,
) -> None:
    """Require a native fitted BOM to agree with selected product part identities."""
    selected = {product.id: product for product in products}
    expectations: list[tuple[str, dict[str, str]]] = []
    occurrence_indexes: dict[str, ProductOccurrenceIndex] = {}
    for choice in selections:
        product = selected.get(choice.product)
        if product is None:
            continue
        occurrence_index = None
        if product_sources is not None:
            occurrence_index = occurrence_indexes.get(product.id)
            if occurrence_index is None:
                source = product_sources.get(product.id)
                if source is None:
                    raise ValueError(f"Selected product has no source identity: {product.id}")
                occurrence_index = product_occurrence_index(source)
                occurrence_indexes[product.id] = occurrence_index
        expected = expected_board_population(
            product,
            choice.variant,
            project_id,
            occurrence_index=occurrence_index,
        )
        if expected is not None:
            expectations.append((f"{choice.product}:{choice.variant}", expected))
    if not expectations:
        return
    with bom_path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != ["Reference", "Value", "Footprint", "PartID", "DNP"]:
            raise ValueError(f"{bom_path}: unexpected native BOM columns")
        actual: dict[str, str] = {}
        for row in reader:
            reference, part_id = row["Reference"], row["PartID"]
            if not reference or not part_id or reference in actual:
                raise ValueError(f"{bom_path}: duplicate or incomplete BOM reference {reference!r}")
            actual[reference] = part_id
    for label, expected in expectations:
        if actual != expected:
            missing = sorted(expected.keys() - actual.keys())
            extra = sorted(actual.keys() - expected.keys())
            changed = sorted(
                ref for ref in actual.keys() & expected.keys() if actual[ref] != expected[ref]
            )
            raise ValueError(
                f"{project_id} native KiCad BOM differs from {label} product population: "
                f"missing={missing}, extra={extra}, changed_part_ids={changed}. "
                "Review product exclusions, KiCad DNP/variant overrides and PART_ID fields"
            )
