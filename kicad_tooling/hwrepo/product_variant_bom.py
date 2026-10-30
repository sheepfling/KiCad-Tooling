"""Compare two authored product variants using the canonical BOM projection."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from .bom_compare_models import Change
from .contract_coach import receipt_directory
from .contracts import read_model, repo_path, write_model
from .evidence import digest
from .generation import bom_rows
from .product import load_repository
from .product_models import AssemblyKind, BomRow, ProductRecord
from .product_variant_bom_html import render_product_variant_bom
from .product_variant_bom_models import (
    ProductVariantBomReport,
    VariantBomInstanceDifference,
    VariantBomInstanceState,
    VariantBomPartDifference,
)
from .product_visual import build_product_visual
from .product_visual_models import ProductVisualReport


def _change(before: object | None, after: object | None) -> Change:
    return (
        "ADDED"
        if before is None
        else "REMOVED"
        if after is None
        else "UNCHANGED"
        if before == after
        else "CHANGED"
    )


def _instances(
    view: ProductVisualReport,
    product: ProductRecord,
    revisions: dict[str, str],
) -> dict[str, VariantBomInstanceState]:
    assemblies = {item.id: item for item in product.assemblies}
    result: dict[str, VariantBomInstanceState] = {}
    for instance in view.instances:
        if instance.kind not in {"PART", "PURCHASED", "UNRESOLVED"}:
            continue
        assembly = assemblies.get(instance.item)
        identifier = (
            assembly.purchase_part
            if assembly is not None and assembly.kind is AssemblyKind.PURCHASED
            else instance.item
        )
        known = identifier is not None and identifier in revisions
        result[instance.path] = VariantBomInstanceState(
            item=instance.item,
            part_id=identifier if known else None,
            revision=revisions[identifier] if known and identifier is not None else None,
            quantity=instance.quantity,
            population=instance.population if known else "UNRESOLVED",
        )
    return result


def _part_differences(
    before: tuple[BomRow, ...], after: tuple[BomRow, ...]
) -> tuple[VariantBomPartDifference, ...]:
    old = {(item.part_id, item.revision): item for item in before}
    new = {(item.part_id, item.revision): item for item in after}
    if len(old) != len(before) or len(new) != len(after):
        raise ValueError("Canonical BOM repeats a part and revision")
    return tuple(
        VariantBomPartDifference(
            part_id=part_id,
            revision=revision,
            change=_change(old.get((part_id, revision)), new.get((part_id, revision))),
            before=old.get((part_id, revision)),
            after=new.get((part_id, revision)),
        )
        for part_id, revision in sorted(old.keys() | new.keys())
    )


def _verify_view(root: Path, view: ProductVisualReport) -> None:
    directory = Path(view.output_directory)
    for name, expected in view.artifacts_sha256.items():
        if digest(directory / name) != expected:
            raise ValueError(f"Variant view artifact changed: {name}")
    if any(digest(repo_path(root, name)) != sha for name, sha in view.source_hashes.items()):
        raise ValueError("Product source changed during variant comparison")


def compare_product_variants(
    root: Path,
    product_id: str,
    before_variant: str,
    after_variant: str,
    output: Path | None = None,
) -> ProductVariantBomReport:
    """Retain two explicit variant views and compare their authored BOM rows."""
    if before_variant == after_variant:
        raise ValueError("Select two distinct product variants")
    root = root.resolve()
    directory = receipt_directory(
        root,
        product_id,
        output or Path("build/product-variant-bom") / f"{product_id}-{uuid4().hex[:12]}",
    )
    before = build_product_visual(root, product_id, before_variant, directory / "before")
    after = build_product_visual(root, product_id, after_variant, directory / "after")
    if before.source_hashes != after.source_hashes or before.product_sha256 != after.product_sha256:
        raise ValueError("Selected variants must have the same product source revision")
    product = read_model(directory / "before/product.json", ProductRecord)
    if digest(directory / "before/product.json") != before.product_sha256:
        raise ValueError("Retained product record changed during comparison")
    variants = {item.id: item for item in product.variants}
    repository = load_repository(root, ())
    revisions = {name: part.revision for name, part in repository.parts.items()}
    old_instances = _instances(before, product, revisions)
    new_instances = _instances(after, product, revisions)
    if old_instances.keys() != new_instances.keys():
        raise ValueError("Variant instance scope changed during comparison")
    instances = tuple(
        VariantBomInstanceDifference(
            path=path,
            change=_change(old_instances[path], new_instances[path]),
            before=old_instances[path],
            after=new_instances[path],
        )
        for path in sorted(old_instances)
    )
    issues = list(dict.fromkeys((*before.issues, *after.issues)))
    issues.extend(f"{item.code} at {item.location}: {item.message}" for item in repository.issues)
    projected = before.status == after.status == "CURRENT" and not issues
    parts: tuple[VariantBomPartDifference, ...] = ()
    if projected:
        try:
            parts = _part_differences(
                bom_rows(product, repository.parts, variants[before_variant]),
                bom_rows(product, repository.parts, variants[after_variant]),
            )
        except (KeyError, ValueError) as exc:
            projected = False
            issues.append(f"Canonical BOM projection unavailable: {exc}")
    _verify_view(root, before)
    _verify_view(root, after)
    report = ProductVariantBomReport(
        product_id=product_id,
        product_revision=product.revision,
        before_variant=before_variant,
        before_variant_revision=variants[before_variant].revision,
        after_variant=after_variant,
        after_variant_revision=variants[after_variant].revision,
        product_path=before.product_path,
        product_sha256=before.product_sha256,
        source_hashes=before.source_hashes,
        before_view_sha256=digest(directory / "before/product-visual.json"),
        after_view_sha256=digest(directory / "after/product-visual.json"),
        status="CURRENT" if projected else "REVIEW",
        bom_projection=projected,
        issues=tuple(issues),
        instances=instances,
        parts=parts,
        output_directory=str(directory),
    )
    (directory / "index.html").write_text(render_product_variant_bom(report), encoding="utf-8")
    _verify_view(root, before)
    _verify_view(root, after)
    report = report.model_copy(
        update={
            "artifacts_sha256": {
                "index.html": digest(directory / "index.html"),
                "before/product-visual.json": report.before_view_sha256,
                "after/product-visual.json": report.after_view_sha256,
            }
        }
    )
    write_model(directory / "comparison.json", report)
    return report
