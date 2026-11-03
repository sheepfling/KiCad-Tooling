"""Recheck saved release readiness captures against selected history anchors."""

from __future__ import annotations

from pathlib import Path

from .contracts import repo_path
from .evidence import digest
from .release_readiness_view_models import ReleaseReadinessViewReport
from .review_overview_evidence import (
    checked_artifact_digest,
    read_receipt,
    recorded_directory,
    selected_receipt,
)
from .verification_history_evidence import SavedSnapshot
from .verification_history_models import HistoryReadiness, HistoryRelease


def load_readiness(
    root: Path,
    requested: Path | None,
    snapshot: SavedSnapshot,
    release: HistoryRelease,
) -> HistoryReadiness:
    if requested is None:
        return HistoryReadiness()
    path = selected_receipt(root, requested, "readiness.json")
    relative = path.relative_to(root).as_posix()
    if not path.is_file():
        return HistoryReadiness(
            receipt=relative,
            status="MISSING",
            integrity="MISSING",
            issues=("Selected release readiness receipt is missing.",),
        )
    try:
        report, checksum = read_receipt(path, ReleaseReadinessViewReport)
    except (OSError, ValueError, TypeError) as exc:
        return HistoryReadiness(
            receipt=relative,
            status="UNAVAILABLE",
            integrity="UNAVAILABLE",
            issues=(f"Selected release readiness receipt is unavailable: {exc}",),
        )
    issues: list[str] = []
    if not recorded_directory(root, report.output_directory, path.parent):
        issues.append("Receipt output directory differs from its selected location.")
    page = path.parent / "index.html"
    if checked_artifact_digest(root, page) != report.artifacts_sha256.get("index.html"):
        issues.append("Readiness page is missing or changed.")
    if not report.source_stable:
        issues.append("Checkout inputs changed while the readiness check ran.")
    if not report.dependency_inventory_complete:
        issues.append(
            "Readiness capture could not enumerate every selected evidence report artifact."
        )
    if report.source_commit != snapshot.identity.source_commit:
        issues.append("Readiness source commit differs from the selected native snapshot.")
    if any(
        report.source_hashes.get(name) != sha
        for name, sha in snapshot.identity.source_hashes.items()
    ):
        issues.append("Readiness source inventory differs from the selected overview.")
    if release.manifest is None or release.manifest != report.manifest:
        issues.append("Readiness manifest differs from the selected release manifest.")
    if release.manifest_sha256 != report.manifest_sha256:
        issues.append("Selected release manifest bytes differ from the readiness check.")
    if release.release_id != report.readiness.release_id:
        issues.append("Readiness release ID differs from the selected release manifest.")
    for name, recorded in sorted(report.declared_files_sha256.items()):
        try:
            selected = repo_path(root, name)
            current = digest(selected) if selected.is_file() else None
        except (OSError, ValueError):
            current = None
        if current != recorded:
            issues.append(f"Declared release input changed or is missing: {name}")
    integrity = "STALE" if issues else "CURRENT"
    return HistoryReadiness(
        receipt=relative,
        receipt_sha256=checksum,
        release_id=report.readiness.release_id,
        checked_on=report.checked_on.isoformat(),
        status=report.readiness.status,
        integrity=integrity,
        issue_codes=tuple(sorted({issue.code for issue in report.readiness.issues})),
        issues=tuple(issues),
    )
