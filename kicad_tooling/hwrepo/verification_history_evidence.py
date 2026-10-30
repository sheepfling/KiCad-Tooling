"""Read saved overview, check, finding, and release evidence for history review."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from ..validate import hashes
from .artifact_access import read_regular_bytes
from .contracts import parse_model_text, repo_path
from .evidence import digest
from .findings_view_models import FindingsViewReport
from .models import ReleaseManifest, ValidationSummary
from .review_overview_evidence import read_receipt, recorded_directory, selected_receipt
from .review_overview_models import OverviewItem, ReviewOverviewReport
from .schematic_geometry_source import source_tree_sha256
from .verification_history_models import (
    HistoryArtifact,
    HistoryEvidence,
    HistoryRelease,
    HistorySnapshot,
)


@dataclass(frozen=True, slots=True)
class SavedSnapshot:
    identity: HistorySnapshot
    overview: ReviewOverviewReport
    evidence: tuple[HistoryEvidence, ...]
    native: ValidationSummary | None
    findings: FindingsViewReport | None


def _relative(root: Path, requested: Path) -> str:
    try:
        relative = requested.relative_to(root) if requested.is_absolute() else requested
    except ValueError as exc:
        raise ValueError("Select a path inside this project checkout") from exc
    return relative.as_posix()


def _item(root: Path, item: OverviewItem) -> tuple[HistoryEvidence, object | None]:
    if item.selected_path is None:
        return (
            HistoryEvidence(
                kind=item.kind,
                status="NOT_RUN",
                captured_freshness=item.freshness,
                integrity="NOT_SELECTED",
            ),
            None,
        )
    path = selected_receipt(root, Path(item.selected_path), Path(item.selected_path).name)
    state = "MISSING" if not path.is_file() else "CURRENT"
    issues: list[str] = list(item.issues)
    parsed: object | None = None
    if state == "CURRENT":
        try:
            if item.report_sha256 is None or digest(path) != item.report_sha256:
                state = "STALE"
                issues.append("Selected receipt no longer matches the overview hash.")
            elif item.kind == "native":
                parsed = read_receipt(path, ValidationSummary)[0]
            elif item.kind == "findings":
                parsed = read_receipt(path, FindingsViewReport)[0]
        except (OSError, ValueError, TypeError) as exc:
            state = "UNAVAILABLE"
            issues.append(f"Selected receipt is unavailable: {exc}")
    if state == "CURRENT" and item.freshness in {"STALE", "UNAVAILABLE"}:
        state = "STALE"
        issues.append("Receipt was already stale or unavailable when the overview was made.")
    return (
        HistoryEvidence(
            kind=item.kind,
            selected_path=item.selected_path,
            status=item.status,
            captured_freshness=item.freshness,
            integrity=state,
            report_sha256=item.report_sha256,
            issues=tuple(issues),
        ),
        parsed if state == "CURRENT" else None,
    )


def load_snapshot(
    root: Path,
    project_id: str,
    requested: Path,
    current_source_hashes: dict[str, str],
    current_manifest_sha256: str,
) -> SavedSnapshot:
    path = selected_receipt(root, requested, "overview.json")
    overview, checksum = read_receipt(path, ReviewOverviewReport)
    if overview.project_id != project_id or not recorded_directory(
        root, overview.output_directory, path.parent
    ):
        raise ValueError("Selected overview identifies a different project or output directory")
    if len({item.kind for item in overview.items}) != len(overview.items):
        raise ValueError("Selected overview repeats an evidence category")
    issues: list[str] = []
    index_hash = overview.artifacts_sha256.get("index.html")
    if index_hash is None or not (path.parent / "index.html").is_file():
        issues.append("Overview page is missing or has no saved hash.")
    elif digest(path.parent / "index.html") != index_hash:
        issues.append("Overview page changed after capture.")
    records: list[HistoryEvidence] = []
    native: ValidationSummary | None = None
    findings: FindingsViewReport | None = None
    for item in overview.items:
        record, parsed = _item(root, item)
        if item.kind == "native" and isinstance(parsed, ValidationSummary):
            native = parsed
            source = parsed.checks.get("source_scope")
            if (
                parsed.project_id != project_id
                or source is None
                or dict(source.source_hashes) != dict(overview.current_source_hashes)
                or dict(item.source_hashes) != dict(overview.current_source_hashes)
            ):
                native = None
                record = record.model_copy(
                    update={
                        "integrity": "STALE",
                        "issues": (
                            *record.issues,
                            "Native project or source scope differs from the overview.",
                        ),
                    }
                )
        if item.kind == "findings" and isinstance(parsed, FindingsViewReport):
            findings = parsed
            if (
                parsed.project_id != project_id
                or dict(parsed.source_hashes) != dict(overview.current_source_hashes)
                or dict(item.source_hashes) != dict(overview.current_source_hashes)
            ):
                findings = None
                record = record.model_copy(
                    update={
                        "integrity": "STALE",
                        "issues": (
                            *record.issues,
                            "Findings project or source scope differs from the overview.",
                        ),
                    }
                )
        records.append(record)
    commit = native.checked_commit if native is not None else None
    if not overview.current_source_hashes:
        relation = "UNKNOWN"
    elif (
        dict(overview.current_source_hashes) == current_source_hashes
        and overview.project_manifest_sha256 == current_manifest_sha256
    ):
        relation = "CURRENT"
    else:
        relation = "HISTORICAL"
    return SavedSnapshot(
        identity=HistorySnapshot(
            overview=path.relative_to(root).as_posix(),
            overview_sha256=checksum,
            project_manifest_sha256=overview.project_manifest_sha256,
            source_hashes=overview.current_source_hashes,
            source_fingerprint=source_tree_sha256(overview.current_source_hashes),
            source_relation=relation,
            source_commit=commit,
            issues=tuple(issues),
        ),
        overview=overview,
        evidence=tuple(records),
        native=native,
        findings=findings,
    )


def load_release(
    root: Path, requested: Path | None, snapshot: SavedSnapshot, project_id: str
) -> HistoryRelease:
    if requested is None:
        return HistoryRelease()
    relative = _relative(root, requested)
    path = repo_path(root, relative)
    if not path.is_file():
        return HistoryRelease(
            manifest=relative,
            source_relation="UNKNOWN",
            status="MISSING",
            issues=("Selected release manifest is missing.",),
        )
    content, _ = read_regular_bytes(path, maximum=16 * 1024 * 1024)
    manifest = parse_model_text(content.decode("utf-8"), ReleaseManifest)
    checksum = hashlib.sha256(content).hexdigest()
    relation = (
        "UNKNOWN"
        if snapshot.identity.source_commit is None or project_id not in manifest.projects
        else "MATCHED"
        if manifest.source_commit == snapshot.identity.source_commit
        else "MISMATCH"
    )
    issues: tuple[str, ...] = ()
    if project_id not in manifest.projects:
        issues += (
            "Release manifest does not explicitly select this project; product scope is not resolved.",
        )
    if snapshot.identity.source_commit is None:
        issues += ("Snapshot has no verified native commit to bind this release manifest.",)
    elif manifest.source_commit != snapshot.identity.source_commit:
        issues += ("Release manifest commit differs from selected native snapshot.",)
    artifacts: list[HistoryArtifact] = []
    for item in manifest.artifacts:
        selected = repo_path(root, item.path)
        integrity = (
            "MISSING"
            if not selected.is_file()
            else "CURRENT"
            if digest(selected) == item.sha256
            else "STALE"
        )
        artifacts.append(
            HistoryArtifact(
                id=item.id,
                kind=item.kind.value,
                path=item.path,
                sha256=item.sha256,
                integrity=integrity,
            )
        )
    if len({item.id for item in artifacts}) != len(artifacts):
        raise ValueError("Release manifest repeats an artifact ID")
    return HistoryRelease(
        manifest=relative,
        manifest_sha256=checksum,
        release_id=manifest.release_id,
        source_commit=manifest.source_commit,
        source_relation=relation,
        status=manifest.status.value,
        artifacts=tuple(artifacts),
        issues=issues,
    )


def current_source(root: Path, project_id: str) -> tuple[dict[str, str], str]:
    """Read current configured source for historical-versus-current labels."""
    from .discovery import load_config
    from .selection import resolve_project

    project = resolve_project(root, project_id)
    config = load_config(root, project.config)
    manifest = repo_path(root, project.config)
    return hashes(root, config.source_roots), digest(manifest)
