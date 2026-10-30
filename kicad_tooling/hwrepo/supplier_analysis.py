"""Compare two manually captured supplier snapshots against one saved BOM."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, date
from pathlib import Path
from uuid import uuid4

from .artifact_access import artifact_path, read_regular_bytes
from .contract_coach import receipt_directory
from .contracts import write_model
from .discovery import load_config
from .evidence import digest
from .models import PurchasingPlan, PurchasingReport
from .parts_receipts import read_parts_receipt
from .review_overview_evidence import ReviewContext, read_receipt, source_mismatch
from .selection import resolve_project
from .sourcing import check as check_sourcing
from .sourcing_models import SourcingSnapshot, SupplierOffer
from .supplier_analysis_html import render_supplier_analysis
from .supplier_analysis_models import (
    OfferFreshness,
    SupplierAnalysisReport,
    SupplierAnalysisSnapshot,
    SupplierOfferCost,
    SupplierOfferDifference,
)
from .verification_history_evidence import current_source


@dataclass(frozen=True, slots=True)
class _Inputs:
    parts_path: Path
    parts: PurchasingReport
    parts_sha256: str
    before_path: Path
    before: SourcingSnapshot
    before_sha256: str
    after_path: Path
    after: SourcingSnapshot
    after_sha256: str
    source_issue: str | None


def _read_snapshot(root: Path, selected: Path) -> tuple[Path, SourcingSnapshot, str]:
    try:
        relative = selected.relative_to(root) if selected.is_absolute() else selected
    except ValueError as exc:
        raise ValueError("Select a sourcing snapshot under this checkout's build/") from exc
    path = artifact_path(root, relative.as_posix())
    report, checksum = read_receipt(path, SourcingSnapshot)
    return path, report, checksum


def _load_inputs(
    root: Path, project_id: str, parts_receipt: Path, before: Path, after: Path
) -> _Inputs:
    project = resolve_project(root, project_id)
    parts_path, parts, parts_sha = read_parts_receipt(root, parts_receipt, project_id)
    before_path, old, old_sha = _read_snapshot(root, before)
    after_path, new, new_sha = _read_snapshot(root, after)
    if before_path == after_path or old.snapshot_id == new.snapshot_id:
        raise ValueError("Select two different dated sourcing snapshots")
    config = load_config(root, project.config)
    current, _ = current_source(root, project_id)
    source_issue = source_mismatch(
        ReviewContext(root, project_id, config, current),
        {**parts.source_hashes, **parts.input_hashes},
        exact_scope=False,
    )
    return _Inputs(
        parts_path,
        parts,
        parts_sha,
        before_path,
        old,
        old_sha,
        after_path,
        new,
        new_sha,
        source_issue,
    )


def _freshness(snapshot: SourcingSnapshot, as_of: date, max_age_days: int) -> OfferFreshness:
    observed = snapshot.observed_at.astimezone(UTC).date()
    if observed > as_of:
        return "FUTURE"
    return "STALE" if (as_of - observed).days > max_age_days else "CURRENT"


def _snapshot_record(
    root: Path,
    path: Path,
    snapshot: SourcingSnapshot,
    checksum: str,
    as_of: date,
    max_age_days: int,
) -> SupplierAnalysisSnapshot:
    validation = check_sourcing(root, snapshot)
    return SupplierAnalysisSnapshot(
        snapshot_id=snapshot.snapshot_id,
        path=path.relative_to(root).as_posix(),
        sha256=checksum,
        source_commit=snapshot.source_commit,
        observed_at=snapshot.observed_at,
        freshness=_freshness(snapshot, as_of, max_age_days),
        validation_status=validation.status,
        validation_issues=tuple(f"{item.code}: {item.message}" for item in validation.issues),
    )


def _quantities(plan: PurchasingPlan) -> tuple[dict[str, int], set[str], tuple[str, ...]]:
    grouped: dict[str, list[tuple[str, int]]] = {}
    fitted: set[str] = set()
    for line in plan.lines:
        grouped.setdefault(line.part_id, []).append((line.revision, line.quantity))
        fitted.update(line.references)
    ambiguous = {part_id for part_id, entries in grouped.items() if len(entries) > 1}
    quantities = {
        part_id: entries[0][1] for part_id, entries in grouped.items() if len(entries) == 1
    }
    unresolved = tuple(
        sorted(
            component.reference
            for component in plan.components
            if not component.dnp
            and not component.exclude_from_bom
            and component.reference not in fitted
        )
    )
    return quantities, ambiguous, unresolved


def _cost(
    offer: SupplierOffer, quantities: dict[str, int], ambiguous: set[str]
) -> SupplierOfferCost:
    requested = quantities.get(offer.part_id)
    minimum, multiple = offer.minimum_order_quantity, offer.package_multiple
    order: int | None = None
    extended: int | None = None
    if offer.part_id in ambiguous:
        status = "REVISION_AMBIGUOUS"
    elif requested is None:
        status = "NOT_IN_BOM"
    else:
        if minimum is not None and multiple is not None:
            needed = max(requested, minimum)
            order = ((needed + multiple - 1) // multiple) * multiple
        if offer.unit_price_minor is None:
            status = "MISSING_PRICE"
        elif order is None:
            status = "PACKAGING_UNKNOWN"
        elif order < offer.quantity_break:
            status = "BREAK_NOT_MET"
        else:
            status = "QUOTED"
            extended = order * offer.unit_price_minor
    return SupplierOfferCost(
        offer_id=offer.id,
        part_id=offer.part_id,
        supplier=offer.supplier,
        supplier_sku=offer.supplier_sku,
        region=offer.region,
        source_url=offer.source_url,
        currency=offer.currency,
        quantity_break=offer.quantity_break,
        unit_price_minor=offer.unit_price_minor,
        availability=offer.availability,
        lead_time_days=offer.lead_time_days,
        minimum_order_quantity=minimum,
        package_multiple=multiple,
        requested_quantity=requested,
        order_quantity=order,
        extended_minor=extended,
        status=status,
    )


def _offers(
    before: SourcingSnapshot,
    after: SourcingSnapshot,
    quantities: dict[str, int],
    ambiguous: set[str],
) -> tuple[SupplierOfferDifference, ...]:
    def keyed(snapshot: SourcingSnapshot) -> dict[tuple[str, str, str, int], SupplierOfferCost]:
        result: dict[tuple[str, str, str, int], SupplierOfferCost] = {}
        for offer in snapshot.offers:
            key = (offer.part_id, offer.supplier, offer.supplier_sku, offer.quantity_break)
            if key in result:
                raise ValueError(f"Sourcing snapshot repeats supplier/SKU/break for {key}")
            result[key] = _cost(offer, quantities, ambiguous)
        return result

    old, new = keyed(before), keyed(after)
    result: list[SupplierOfferDifference] = []
    for key in sorted(old.keys() | new.keys()):
        left, right = old.get(key), new.get(key)
        change = (
            "ADDED"
            if left is None
            else "REMOVED"
            if right is None
            else "UNCHANGED"
            if left == right
            else "CHANGED"
        )
        result.append(
            SupplierOfferDifference(
                part_id=key[0],
                supplier=key[1],
                supplier_sku=key[2],
                quantity_break=key[3],
                change=change,
                before=left,
                after=right,
            )
        )
    return tuple(result)


def compare_supplier_snapshots(
    root: Path,
    project_id: str,
    parts_receipt: Path,
    before: Path,
    after: Path,
    as_of: date,
    max_age_days: int,
    output: Path | None = None,
) -> SupplierAnalysisReport:
    """Review dated offers with explicit packaging and without currency conversion."""
    root = root.resolve()
    if max_age_days < 0:
        raise ValueError("Maximum offer age must be non-negative")
    inputs = _load_inputs(root, project_id, parts_receipt, before, after)
    if inputs.parts.plan is None:
        raise ValueError("Selected parts receipt has no BOM plan")
    quantities, ambiguous, unresolved = _quantities(inputs.parts.plan)
    differences = _offers(inputs.before, inputs.after, quantities, ambiguous)
    old = _snapshot_record(
        root, inputs.before_path, inputs.before, inputs.before_sha256, as_of, max_age_days
    )
    new = _snapshot_record(
        root, inputs.after_path, inputs.after, inputs.after_sha256, as_of, max_age_days
    )
    currencies = tuple(
        sorted(
            {
                offer.currency
                for item in differences
                for offer in (item.before, item.after)
                if offer is not None
            }
        )
    )
    issues: list[str] = []
    if inputs.source_issue:
        issues.append(f"Parts source is stale: {inputs.source_issue}")
    for label, snapshot in (("Before", old), ("After", new)):
        if snapshot.freshness != "CURRENT":
            issues.append(
                f"{label} offers are {snapshot.freshness.lower()} on the selected as-of date."
            )
        if snapshot.validation_status != "PASS":
            issues.append(f"{label} snapshot fails local catalog/identity validation.")
    if len(currencies) > 1:
        issues.append(
            "Offers use multiple currencies; no conversion or combined total is calculated."
        )
    if ambiguous:
        issues.append(
            f"Part identities have multiple BOM revisions: {', '.join(sorted(ambiguous))}."
        )
    if unresolved:
        issues.append(f"Fitted references lack a resolved BOM line: {', '.join(unresolved)}.")

    def verify_inputs() -> None:
        if _load_inputs(root, project_id, parts_receipt, before, after) != inputs:
            raise ValueError("Parts source or selected sourcing snapshots changed during analysis")

    verify_inputs()
    target = output or Path("build/supplier-analysis") / f"{project_id}-{uuid4().hex[:12]}"
    directory = receipt_directory(root, project_id, target)
    retained = {
        "parts-report.json": inputs.parts_path,
        "before-snapshot.json": inputs.before_path,
        "after-snapshot.json": inputs.after_path,
    }
    hashes: dict[str, str] = {}
    for name, path in retained.items():
        raw, _ = read_regular_bytes(path, maximum=16 * 1024 * 1024)
        expected = (
            inputs.parts_sha256
            if name == "parts-report.json"
            else inputs.before_sha256
            if name == "before-snapshot.json"
            else inputs.after_sha256
        )
        checksum = hashlib.sha256(raw).hexdigest()
        if checksum != expected:
            raise ValueError(f"Selected evidence changed during copy: {name}")
        (directory / name).write_bytes(raw)
        hashes[name] = checksum
    report = SupplierAnalysisReport(
        project_id=project_id,
        parts_receipt=inputs.parts_path.relative_to(root).as_posix(),
        parts_receipt_sha256=inputs.parts_sha256,
        parts_source_hashes=inputs.parts.source_hashes,
        parts_input_hashes=inputs.parts.input_hashes,
        parts_source_current=inputs.source_issue is None,
        as_of=as_of,
        max_age_days=max_age_days,
        before=old,
        after=new,
        offers=differences,
        unresolved_references=unresolved,
        currencies=currencies,
        issues=tuple(issues),
        output_directory=str(directory),
    )
    (directory / "index.html").write_text(render_supplier_analysis(report), encoding="utf-8")
    hashes["index.html"] = digest(directory / "index.html")
    verify_inputs()
    report = report.model_copy(update={"artifacts_sha256": hashes})
    write_model(directory / "supplier-analysis.json", report)
    return report
