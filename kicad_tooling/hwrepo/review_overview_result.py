"""Build a consistent overview card from one inspected receipt."""

from __future__ import annotations

from pathlib import Path

from .review_overview_evidence import ReviewContext, checked_link
from .review_overview_models import OverviewItem, OverviewKind, OverviewLink


def receipt_result(
    context: ReviewContext,
    kind: OverviewKind,
    path: Path,
    report_hash: str,
    status: str,
    *,
    source_hashes: dict[str, str] | None = None,
    source_commit: str | None = None,
    links: tuple[OverviewLink, ...] = (),
    stale: tuple[str, ...] = (),
    unknown: tuple[str, ...] = (),
    notes: tuple[str, ...] = (),
) -> OverviewItem:
    report_link = checked_link(context, path, "Selected receipt", report_hash)
    if report_link is None:
        stale = (*stale, "Selected receipt changed during overview creation.")
    else:
        report_link = report_link.model_copy(update={"receipt_bound": False})
    return OverviewItem(
        kind=kind,
        selected_path=path.relative_to(context.root).as_posix(),
        status=status,
        freshness="STALE" if stale else "UNKNOWN" if unknown else "CURRENT",
        report_sha256=report_hash,
        source_commit=source_commit,
        source_hashes=source_hashes or {},
        links=((report_link,) if report_link is not None else ()) + links,
        issues=(*stale, *unknown, *notes),
    )
