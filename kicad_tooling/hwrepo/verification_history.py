"""Compare saved project review snapshots without rerunning engineering checks."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from pathlib import Path
from uuid import uuid4

from .contract_coach import receipt_directory
from .contracts import write_model
from .evidence import digest
from .findings_view_models import ReviewFinding, finding_fingerprint
from .models import CheckEvidence
from .review_overview_models import OverviewKind
from .verification_history_evidence import (
    SavedSnapshot,
    current_source,
    load_release,
    load_snapshot,
)
from .verification_history_html import render_verification_history
from .verification_history_models import (
    Change,
    CheckState,
    HistoryArtifact,
    HistoryArtifactChange,
    HistoryCheckChange,
    HistoryEvidence,
    HistoryEvidenceChange,
    HistoryFindingChange,
    HistoryRelease,
    HistorySourceChange,
    VerificationHistoryReport,
)


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


def _evidence(snapshot: SavedSnapshot, kind: OverviewKind) -> HistoryEvidence:
    return next(
        (item for item in snapshot.evidence if item.kind == kind),
        HistoryEvidence(
            kind=kind, status="NOT_RUN", captured_freshness="NOT_SELECTED", integrity="NOT_SELECTED"
        ),
    )


def _evidence_changes(
    before: SavedSnapshot, after: SavedSnapshot
) -> tuple[HistoryEvidenceChange, ...]:
    kinds: tuple[OverviewKind, ...] = (
        "native",
        "findings",
        "parts",
        "three_d",
        "simulation",
        "verification",
    )
    return tuple(
        HistoryEvidenceChange(
            kind=kind,
            change=_change(_evidence(before, kind), _evidence(after, kind)),
            before=_evidence(before, kind),
            after=_evidence(after, kind),
        )
        for kind in kinds
    )


def _source_changes(before: SavedSnapshot, after: SavedSnapshot) -> tuple[HistorySourceChange, ...]:
    old, new = before.identity.source_hashes, after.identity.source_hashes
    return tuple(
        HistorySourceChange(
            path=path,
            change=_change(old.get(path), new.get(path)),
            before_sha256=old.get(path),
            after_sha256=new.get(path),
        )
        for path in sorted(old.keys() | new.keys())
    )


def _check_state(snapshot: SavedSnapshot, name: str) -> CheckState:
    if snapshot.native is not None:
        check = snapshot.native.checks.get(name)
        return "NOT_RUN" if check is None else check.status
    state = _evidence(snapshot, "native").integrity
    if state == "NOT_SELECTED":
        return "NOT_RUN"
    if state == "MISSING":
        return "MISSING"
    if state == "STALE":
        return "STALE"
    return "UNAVAILABLE"


def _check_changes(before: SavedSnapshot, after: SavedSnapshot) -> tuple[HistoryCheckChange, ...]:
    old: Mapping[str, CheckEvidence] = before.native.checks if before.native is not None else {}
    new: Mapping[str, CheckEvidence] = after.native.checks if after.native is not None else {}
    result: list[HistoryCheckChange] = []
    for name in sorted(old.keys() | new.keys()):
        baseline = old.get(name)
        candidate = new.get(name)
        details: list[str] = []
        if baseline is not None and candidate is not None:
            if baseline.findings != candidate.findings:
                details.append(f"Findings: {baseline.findings} → {candidate.findings}")
            if baseline.error != candidate.error:
                details.append(f"Error: {baseline.error or 'none'} → {candidate.error or 'none'}")
        result.append(
            HistoryCheckChange(
                name=name,
                before=_check_state(before, name),
                after=_check_state(after, name),
                detail="; ".join(details),
            )
        )
    return tuple(result)


def _finding_groups(snapshot: SavedSnapshot) -> dict[tuple[str, str, str], list[ReviewFinding]]:
    groups: dict[tuple[str, str, str], list[ReviewFinding]] = defaultdict(list)
    if snapshot.findings is not None:
        for finding in snapshot.findings.findings:
            groups[(finding.origin, finding.rule, finding.title)].append(finding)
    return groups


def _finding_explanation(before: ReviewFinding, after: ReviewFinding) -> str:
    changed = sorted(
        key
        for key in before.evidence.keys() | after.evidence.keys()
        if before.evidence.get(key) != after.evidence.get(key)
    )
    details = [
        f"Evidence fields changed: {', '.join(changed)}"
        if changed
        else "No evidence field changed; compare the retained finding records"
    ]
    if before.severity != after.severity:
        details.append(f"Severity: {before.severity} → {after.severity}")
    if before.description != after.description:
        details.append("Description changed")
    if before.markers != after.markers:
        details.append("Location markers changed")
    return "; ".join(details)


def _finding_changes(
    before: SavedSnapshot, after: SavedSnapshot
) -> tuple[HistoryFindingChange, ...]:
    # A missing or changed report never becomes evidence that findings were resolved.
    if before.findings is None or after.findings is None:
        return ()
    old, new = _finding_groups(before), _finding_groups(after)
    result: list[HistoryFindingChange] = []
    for key in sorted(old.keys() | new.keys()):
        prior = old.get(key, [])
        later = new.get(key, [])
        if len(prior) == len(later) == 1:
            left, right = prior[0], later[0]
            left_fingerprint = finding_fingerprint(left)
            right_fingerprint = finding_fingerprint(right)
            change = (
                "CHANGED_FINGERPRINT"
                if left_fingerprint != right_fingerprint
                else "CHANGED_DETAIL"
                if left != right
                else "UNCHANGED"
            )
            result.append(
                HistoryFindingChange(
                    origin=left.origin,
                    rule=left.rule,
                    title=left.title,
                    change=change,
                    before_fingerprint=left_fingerprint,
                    after_fingerprint=right_fingerprint,
                    explanation=_finding_explanation(left, right) if change != "UNCHANGED" else "",
                )
            )
            continue
        old_by_fingerprint = {finding_fingerprint(item): item for item in prior}
        new_by_fingerprint = {finding_fingerprint(item): item for item in later}
        for fingerprint in sorted(old_by_fingerprint.keys() | new_by_fingerprint.keys()):
            left, right = old_by_fingerprint.get(fingerprint), new_by_fingerprint.get(fingerprint)
            item = left or right
            assert item is not None
            result.append(
                HistoryFindingChange(
                    origin=item.origin,
                    rule=item.rule,
                    title=item.title,
                    change="ADDED"
                    if left is None
                    else "REMOVED"
                    if right is None
                    else "CHANGED_DETAIL"
                    if left != right
                    else "UNCHANGED",
                    before_fingerprint=fingerprint if left is not None else None,
                    after_fingerprint=fingerprint if right is not None else None,
                    explanation="Same rule and title have multiple findings; identity is not inferred."
                    if len(prior) > 1 or len(later) > 1
                    else "",
                )
            )
    return tuple(result)


def _artifact_changes(
    before: HistoryRelease, after: HistoryRelease
) -> tuple[HistoryArtifactChange, ...]:
    old: dict[str, HistoryArtifact] = {item.id: item for item in before.artifacts}
    new: dict[str, HistoryArtifact] = {item.id: item for item in after.artifacts}
    return tuple(
        HistoryArtifactChange(
            id=name,
            change=_change(old.get(name), new.get(name)),
            before=old.get(name),
            after=new.get(name),
        )
        for name in sorted(old.keys() | new.keys())
    )


def compare_verification_history(
    root: Path,
    project_id: str,
    baseline: Path,
    candidate: Path,
    *,
    baseline_release: Path | None = None,
    candidate_release: Path | None = None,
    output: Path | None = None,
) -> VerificationHistoryReport:
    """Retain two explicitly chosen history anchors and their check/finding deltas."""
    root = root.resolve()
    current_hashes, current_manifest = current_source(root, project_id)
    old = load_snapshot(root, project_id, baseline, current_hashes, current_manifest)
    new = load_snapshot(root, project_id, candidate, current_hashes, current_manifest)
    old_release = load_release(root, baseline_release, old, project_id)
    new_release = load_release(root, candidate_release, new, project_id)

    def verify_inputs() -> None:
        if current_source(root, project_id) != (current_hashes, current_manifest):
            raise ValueError("Current project source changed during history export")
        for requested, saved in ((baseline, old), (candidate, new)):
            if (
                load_snapshot(root, project_id, requested, current_hashes, current_manifest)
                != saved
            ):
                raise ValueError("Selected overview or receipt changed during history export")
        if (
            load_release(root, baseline_release, old, project_id) != old_release
            or load_release(root, candidate_release, new, project_id) != new_release
        ):
            raise ValueError("Selected release manifest or artifact changed during history export")

    verify_inputs()
    target = output or Path("build/verification-history") / f"{project_id}-{uuid4().hex[:12]}"
    directory = receipt_directory(root, project_id, target)
    report = VerificationHistoryReport(
        project_id=project_id,
        baseline=old.identity,
        candidate=new.identity,
        baseline_release=old_release,
        candidate_release=new_release,
        source_changes=_source_changes(old, new),
        evidence_changes=_evidence_changes(old, new),
        check_changes=_check_changes(old, new),
        finding_changes=_finding_changes(old, new),
        artifact_changes=_artifact_changes(old_release, new_release),
        output_directory=str(directory),
    )
    (directory / "index.html").write_text(
        render_verification_history(root, report), encoding="utf-8"
    )
    verify_inputs()
    report = report.model_copy(
        update={"artifacts_sha256": {"index.html": digest(directory / "index.html")}}
    )
    write_model(directory / "history.json", report)
    return report
