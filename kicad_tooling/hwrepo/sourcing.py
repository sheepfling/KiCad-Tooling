"""Provider-neutral validation for manually captured, time-bound supplier offers."""
from __future__ import annotations

from pathlib import Path

from .contracts import read_model, repo_path
from .discovery import load_registry
from .models import (
    PartsCatalog,
    PolicyIssue,
    SourcingSnapshot,
    SourcingSnapshotReport,
)


def finding(code: str, location: str, message: str) -> PolicyIssue:
    """Build a concise, typed sourcing finding without contacting a supplier."""
    return PolicyIssue(code=code, location=location, message=message)


def check(root: Path, snapshot: SourcingSnapshot) -> SourcingSnapshotReport:
    """Validate offer identity and part references; prices never approve a component."""
    resolved_root = root.resolve()
    issues: list[PolicyIssue] = []
    try:
        registry = load_registry(resolved_root)
        parts = {
            part.id
            for part in read_model(
                repo_path(resolved_root, registry.catalogs.parts), PartsCatalog
            ).parts
        }
    except (OSError, ValueError) as exc:
        return SourcingSnapshotReport(
            snapshot_id=snapshot.snapshot_id,
            offers=len(snapshot.offers),
            status="FAIL",
            issues=(finding("SOURCING_LOAD", "catalog/parts.json", str(exc)),),
        )

    offer_ids: set[str] = set()
    offer_keys: set[tuple[str, str, str, int]] = set()
    for offer in snapshot.offers:
        if offer.id in offer_ids:
            issues.append(finding("SOURCING_OFFER_ID", offer.id, "Duplicate offer identity"))
        offer_ids.add(offer.id)
        key = (offer.part_id, offer.supplier, offer.supplier_sku, offer.quantity_break)
        if key in offer_keys:
            issues.append(
                finding("SOURCING_OFFER", offer.id, "Duplicate supplier, SKU and quantity break")
            )
        offer_keys.add(key)
        if offer.part_id not in parts:
            issues.append(finding("SOURCING_PART", offer.id, "Offer references an unknown part"))
    return SourcingSnapshotReport(
        snapshot_id=snapshot.snapshot_id,
        offers=len(snapshot.offers),
        status="FAIL" if issues else "PASS",
        issues=tuple(issues),
    )
