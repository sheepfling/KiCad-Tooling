"""Inspect one project verification receipt for the offline overview."""

from __future__ import annotations

from pathlib import Path

from .contracts import repo_path
from .evidence import digest
from .models import ProjectVerificationReport
from .repository import checkout_input_hashes
from .review_overview_evidence import (
    ReviewContext,
    artifact_issues,
    checked_link,
    read_receipt,
    recorded_directory,
)
from .review_overview_models import OverviewItem, OverviewLink
from .review_overview_result import receipt_result
from .verification_receipts import read_verification_output_manifest


def inspect_verification(context: ReviewContext, path: Path) -> OverviewItem:
    report, checksum = read_receipt(path, ProjectVerificationReport)
    if report.project_id != context.project_id or not recorded_directory(
        context.root, report.run_directory, path.parent
    ):
        raise ValueError("Verification receipt has a different project or output directory")
    stale: list[str] = []
    unknown: list[str] = []
    links: list[OverviewLink] = []
    source_hashes: dict[str, str] = {}
    try:
        manifest = read_verification_output_manifest(path.parent, checksum)
    except (OSError, ValueError):
        manifest = None
        stale.append("Verification artifact manifest is invalid or does not bind the report.")
    if manifest is None and not stale:
        unknown.append("Verification summary has no standalone source hash inventory.")
    if manifest is not None:
        source_hashes = dict(manifest.source_hashes)
        if not manifest.source_stable:
            stale.append("Repository source changed during verification.")
        try:
            if source_hashes != checkout_input_hashes(context.root):
                stale.append("Repository source differs from the verification run.")
        except (OSError, ValueError):
            unknown.append("Repository source inventory is unavailable.")
        stale.extend(artifact_issues(context, path.parent, manifest.artifacts_sha256))
        for name in (
            "verification.txt",
            "portable.json",
            "doctor.json",
            "native.json",
            "design-lint.json",
            "electrical.json",
            "diagnosis.json",
        ):
            expected = manifest.artifacts_sha256.get(name)
            if expected is not None:
                link = checked_link(context, repo_path(path.parent, name), name, expected)
                if link is not None:
                    links.append(link)
        manifest_path = repo_path(path.parent, "verification-artifacts.json")
        link = checked_link(
            context, manifest_path, "Verification hash manifest", digest(manifest_path)
        )
        if link is not None:
            links.append(link.model_copy(update={"receipt_bound": False}))
    return receipt_result(
        context,
        "verification",
        path,
        checksum,
        report.status,
        source_hashes=source_hashes,
        links=tuple(links),
        stale=tuple(stale),
        unknown=tuple(unknown),
        notes=(f"Depth: {report.depth}", *report.next_actions),
    )
