"""Compare two retained product views without projecting an old BOM from live catalogs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from uuid import uuid4

from .bom_change import change_state
from .contract_coach import receipt_directory
from .contracts import read_model, repo_path, write_model
from .evidence import digest
from .generation import bom_rows
from .part_catalog_models import PartRecord, PartsCatalog
from .product_models import ProductRecord
from .product_revision_bom_html import render_product_revision_bom
from .product_revision_bom_models import (
    ProductRevisionBomReport,
    ProductRevisionInstanceDifference,
    ProductRevisionSnapshot,
)
from .product_variant_bom import instance_states, part_differences
from .product_visual import project_instances
from .product_visual_models import ProductVisualReport
from .review_overview_evidence import (
    checked_artifact_digest,
    read_receipt,
    recorded_directory,
    selected_receipt,
)


@dataclass(frozen=True, slots=True)
class SavedProductView:
    snapshot: ProductRevisionSnapshot
    view: ProductVisualReport
    product: ProductRecord
    parts: dict[str, PartRecord] | None


def _source_relation(
    root: Path, hashes: dict[str, str]
) -> Literal["CURRENT", "HISTORICAL", "UNAVAILABLE"]:
    try:
        return (
            "CURRENT"
            if all(digest(repo_path(root, name)) == expected for name, expected in hashes.items())
            else "HISTORICAL"
        )
    except FileNotFoundError:
        return "HISTORICAL"
    except (OSError, ValueError):
        return "UNAVAILABLE"


def _load_view(root: Path, requested: Path) -> SavedProductView:
    path = selected_receipt(root, requested, "product-visual.json")
    view, checksum = read_receipt(path, ProductVisualReport)
    if not recorded_directory(root, view.output_directory, path.parent):
        raise ValueError("Product view identifies another output directory")
    required = {"index.html", "product.json", "product-index.json"}
    if not required <= view.artifacts_sha256.keys():
        raise ValueError("Product view omits retained source or page hashes")
    for name, expected in view.artifacts_sha256.items():
        if checked_artifact_digest(root, repo_path(path.parent, name)) != expected:
            raise ValueError(f"Selected product view artifact changed or is missing: {name}")
    if (
        view.source_hashes.get(view.product_path) != view.product_sha256
        or view.artifacts_sha256["product.json"] != view.product_sha256
    ):
        raise ValueError("Retained product record does not bind the view source identity")
    product = read_model(path.parent / "product.json", ProductRecord)
    variant = next((item for item in product.variants if item.id == view.variant_id), None)
    if (
        product.id != view.product_id
        or product.revision != view.product_revision
        or variant is None
        or variant.revision != view.variant_revision
    ):
        raise ValueError("Retained product and variant identities differ from the selected view")
    parts: dict[str, PartRecord] | None = None
    if (view.parts_catalog_path is None) != (view.parts_catalog_sha256 is None):
        raise ValueError("Product view has an incomplete retained parts catalog identity")
    if view.parts_catalog_path is not None and view.parts_catalog_sha256 is not None:
        if (
            view.source_hashes.get(view.parts_catalog_path) != view.parts_catalog_sha256
            or view.artifacts_sha256.get("parts-catalog.json") != view.parts_catalog_sha256
        ):
            raise ValueError("Retained parts catalog does not bind the view source identity")
        catalog = read_model(path.parent / "parts-catalog.json", PartsCatalog)
        parts = {item.id: item for item in catalog.parts}
        if len(parts) != len(catalog.parts):
            raise ValueError("Retained parts catalog repeats an ID")
        try:
            expected_instances = project_instances(product, variant, set(parts))
        except ValueError as exc:
            if view.status == "CURRENT":
                raise ValueError("Current product view has an invalid retained hierarchy") from exc
        else:
            if view.instances != expected_instances:
                raise ValueError("Saved product instances differ from retained product and catalog")
    snapshot = ProductRevisionSnapshot(
        view=path.relative_to(root).as_posix(),
        view_sha256=checksum,
        product_path=view.product_path,
        product_sha256=view.product_sha256,
        parts_catalog_path=view.parts_catalog_path,
        parts_catalog_sha256=view.parts_catalog_sha256,
        product_revision=view.product_revision,
        variant_id=view.variant_id,
        variant_revision=view.variant_revision,
        source_relation=_source_relation(root, dict(view.source_hashes)),
        view_status=view.status,
        issues=view.issues,
    )
    return SavedProductView(snapshot=snapshot, view=view, product=product, parts=parts)


def compare_product_revisions(
    root: Path,
    baseline: Path,
    candidate: Path,
    output: Path | None = None,
) -> ProductRevisionBomReport:
    """Compare selected authored snapshots, retaining historical source identity."""
    root = root.resolve()
    old = _load_view(root, baseline)
    new = _load_view(root, candidate)
    if old.view.product_id != new.view.product_id:
        raise ValueError("Select two views of the same product ID")

    def revisions(saved: SavedProductView) -> dict[str, str]:
        return {name: part.revision for name, part in (saved.parts or {}).items()}

    before_instances = instance_states(old.view, old.product, revisions(old))
    after_instances = instance_states(new.view, new.product, revisions(new))
    instances = tuple(
        ProductRevisionInstanceDifference(
            path=path,
            change=change_state(before_instances.get(path), after_instances.get(path)),
            before=before_instances.get(path),
            after=after_instances.get(path),
        )
        for path in sorted(before_instances.keys() | after_instances.keys())
    )
    issues = list(dict.fromkeys((*old.view.issues, *new.view.issues)))
    if old.parts is None or new.parts is None:
        issues.append("One saved view predates retained parts catalogs; canonical BOM unavailable.")
    projected = old.view.status == new.view.status == "CURRENT" and not issues
    parts = ()
    if projected:
        try:
            assert old.parts is not None and new.parts is not None
            old_variant = next(
                item for item in old.product.variants if item.id == old.view.variant_id
            )
            new_variant = next(
                item for item in new.product.variants if item.id == new.view.variant_id
            )
            parts = part_differences(
                bom_rows(old.product, old.parts, old_variant),
                bom_rows(new.product, new.parts, new_variant),
            )
        except (KeyError, ValueError) as exc:
            projected = False
            issues.append(f"Canonical saved BOM projection unavailable: {exc}")
    target = (
        output or Path("build/product-revision-bom") / f"{old.view.product_id}-{uuid4().hex[:12]}"
    )
    directory = receipt_directory(root, old.view.product_id, target)
    report = ProductRevisionBomReport(
        product_id=old.view.product_id,
        baseline=old.snapshot,
        candidate=new.snapshot,
        variant_relation="SAME" if old.view.variant_id == new.view.variant_id else "DIFFERENT",
        product_path_relation="SAME"
        if old.view.product_path == new.view.product_path
        else "DIFFERENT",
        status="COMPARED" if projected else "REVIEW",
        bom_projection=projected,
        instances=instances,
        parts=parts,
        issues=tuple(issues),
        output_directory=str(directory),
    )
    (directory / "index.html").write_text(
        render_product_revision_bom(root, report), encoding="utf-8"
    )
    if _load_view(root, baseline) != old or _load_view(root, candidate) != new:
        raise ValueError("Selected product source or receipt changed during comparison")
    report = report.model_copy(
        update={"artifacts_sha256": {"index.html": digest(directory / "index.html")}}
    )
    write_model(directory / "comparison.json", report)
    return report
