"""Recheck a saved verification summary's captured manifest for history."""

from __future__ import annotations

from pathlib import Path

from .contracts import repo_path
from .review_overview_evidence import checked_artifact_digest, selected_receipt
from .review_overview_models import OverviewItem
from .verification_history_models import HistoryEvidence
from .verification_receipts import read_verification_output_manifest


def recheck_verification(
    root: Path, item: OverviewItem, record: HistoryEvidence
) -> HistoryEvidence:
    """Keep historical source differences separate from changed saved files."""
    if record.integrity != "CURRENT" or item.selected_path is None:
        return record

    def stale(reason: str) -> HistoryEvidence:
        return record.model_copy(update={"integrity": "STALE", "issues": (*record.issues, reason)})

    report_path = selected_receipt(root, Path(item.selected_path), "verification.json")
    manifest_path = repo_path(report_path.parent, "verification-artifacts.json")
    relative = manifest_path.relative_to(root).as_posix()
    recorded = tuple(link for link in item.links if link.path == relative)
    if not recorded and not item.source_hashes:
        return record  # Legacy overview: the selected summary hash is all it recorded.
    if len(recorded) != 1 or not item.source_hashes:
        return stale("Verification manifest binding is absent or ambiguous in the overview.")
    actual = checked_artifact_digest(root, manifest_path)
    if actual is None or actual != recorded[0].sha256:
        return stale("Verification manifest changed or is missing after the overview.")
    try:
        manifest = read_verification_output_manifest(report_path.parent, item.report_sha256 or "")
    except (OSError, ValueError):
        return stale("Verification manifest no longer validates against its summary.")
    if manifest is None:
        return stale("Verification manifest is missing after the overview.")
    if not manifest.source_stable or dict(manifest.source_hashes) != dict(item.source_hashes):
        return stale("Verification input inventory differs from the captured overview.")
    if len(manifest.artifacts_sha256) > 2000:
        return stale("Verification output inventory exceeds the review limit.")
    for name, expected in manifest.artifacts_sha256.items():
        path = repo_path(report_path.parent, name)
        if checked_artifact_digest(root, path) != expected:
            return stale(f"Verification output changed or is missing: {name}")
    for link in item.links:
        if link.path in {item.selected_path, relative}:
            continue
        path = Path(link.path)
        if path.parent == Path(item.selected_path).parent and (
            manifest.artifacts_sha256.get(path.name) != link.sha256
        ):
            return stale(f"Verification output link differs from its manifest: {path.name}")
    return record
