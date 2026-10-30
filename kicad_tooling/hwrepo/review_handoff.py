"""Export selected historical findings and attributed notes into one offline packet."""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from .artifact_access import read_regular_bytes
from .contract_coach import receipt_directory
from .contracts import parse_model_text, write_model
from .findings_view_evidence import verified_findings_drawing
from .findings_view_models import finding_fingerprint
from .project_source_access import project_owned_source_path
from .review_handoff_html import render_review_handoff
from .review_handoff_models import (
    HandoffEvidenceLink,
    HandoffFinding,
    HandoffNote,
    HandoffSnapshot,
    ReviewerNotesFile,
    ReviewHandoffReport,
    SnapshotRole,
)
from .review_overview_evidence import recorded_directory, selected_receipt
from .verification_history_evidence import SavedSnapshot, current_source, load_snapshot


@dataclass(frozen=True, slots=True)
class _Input:
    baseline: SavedSnapshot
    candidate: SavedSnapshot
    notes_path: Path
    notes_sha256: str
    notes_bytes: bytes
    notes: ReviewerNotesFile
    current_source: tuple[dict[str, str], str]


def _read_input(
    root: Path, project_id: str, baseline: Path, candidate: Path, notes: Path
) -> _Input:
    current = current_source(root, project_id)
    old = load_snapshot(root, project_id, baseline, *current)
    new = load_snapshot(root, project_id, candidate, *current)
    if old.identity.overview == new.identity.overview:
        raise ValueError("Select two different overview receipts")
    path, _ = project_owned_source_path(root, project_id, notes, ".json")
    raw, _ = read_regular_bytes(path, maximum=1024 * 1024)
    parsed = parse_model_text(raw.decode("utf-8"), ReviewerNotesFile)
    if parsed.project_id != project_id:
        raise ValueError("Reviewer notes identify a different project")
    return _Input(
        baseline=old,
        candidate=new,
        notes_path=path,
        notes_sha256=hashlib.sha256(raw).hexdigest(),
        notes_bytes=raw,
        notes=parsed,
        current_source=current,
    )


def _fingerprints(selected: tuple[str, ...]) -> tuple[str, ...]:
    if not 1 <= len(selected) <= 100:
        raise ValueError("Select 1 to 100 finding fingerprints")
    if len(set(selected)) != len(selected) or any(
        re.fullmatch(r"[a-f0-9]{64}", value) is None for value in selected
    ):
        raise ValueError("Finding fingerprints must be unique lowercase SHA-256 values")
    return selected


def _snapshot(
    role: SnapshotRole,
    saved: SavedSnapshot,
    selected: tuple[str, ...],
) -> tuple[HandoffSnapshot, tuple[HandoffFinding, ...]]:
    evidence = next(item for item in saved.evidence if item.kind == "findings")
    report = saved.findings
    issues = list(evidence.issues)
    records: list[HandoffFinding] = []
    if report is not None:
        seen: set[str] = set()
        for finding in report.findings:
            fingerprint = finding_fingerprint(finding)
            if fingerprint in seen:
                raise ValueError(f"{role} findings repeat fingerprint {fingerprint}")
            seen.add(fingerprint)
            if fingerprint in selected:
                records.append(
                    HandoffFinding(snapshot=role, fingerprint=fingerprint, finding=finding)
                )
        for fingerprint in selected:
            if fingerprint not in seen:
                issues.append(f"Selected finding {fingerprint} is absent from {role}.")
    else:
        issues.append(f"{role} findings receipt is unavailable; selected findings cannot be shown.")
    return (
        HandoffSnapshot(
            snapshot=role,
            identity=saved.identity,
            findings_receipt=evidence.selected_path,
            findings_receipt_sha256=evidence.report_sha256,
            findings_integrity=evidence.integrity,
            issues=tuple(issues),
        ),
        tuple(records),
    )


def _notes(
    authored: ReviewerNotesFile,
    baseline: HandoffSnapshot,
    candidate: HandoffSnapshot,
    findings: tuple[HandoffFinding, ...],
    selected: tuple[str, ...],
) -> tuple[HandoffNote, ...]:
    snapshots = {"baseline": baseline, "candidate": candidate}
    available = {(item.snapshot, item.fingerprint) for item in findings}
    records: list[HandoffNote] = []
    for note in authored.notes:
        if note.finding_fingerprint not in selected:
            continue
        snapshot = snapshots[note.snapshot]
        if note.overview_sha256 != snapshot.identity.overview_sha256:
            state = "OUTDATED_RECEIPT"
        elif snapshot.findings_integrity != "CURRENT":
            state = "UNAVAILABLE"
        elif (note.snapshot, note.finding_fingerprint) not in available:
            state = "OUTDATED_FINGERPRINT"
        else:
            state = "CURRENT"
        records.append(HandoffNote(note=note, state=state))
    assessments: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    for record in records:
        if record.state == "CURRENT":
            note = record.note
            assessments[(note.snapshot, note.overview_sha256, note.finding_fingerprint)].add(
                note.assessment
            )
    return tuple(
        record.model_copy(
            update={
                "conflict": record.state == "CURRENT"
                and len(
                    assessments[
                        (
                            record.note.snapshot,
                            record.note.overview_sha256,
                            record.note.finding_fingerprint,
                        )
                    ]
                )
                > 1
            }
        )
        for record in records
    )


def _evidence_bytes(
    root: Path, role: SnapshotRole, saved: SavedSnapshot
) -> tuple[dict[str, bytes], tuple[HandoffEvidenceLink, ...], tuple[str, ...]]:
    files: dict[str, bytes] = {}
    links: list[HandoffEvidenceLink] = []
    issues: list[str] = []

    def copy(source: Path, name: str, expected: str) -> None:
        try:
            raw, _ = read_regular_bytes(source, maximum=32 * 1024 * 1024)
            if hashlib.sha256(raw).hexdigest() != expected:
                raise ValueError("digest mismatch")
        except (OSError, ValueError) as exc:
            issues.append(f"Evidence changed or is missing: {source.relative_to(root)} ({exc})")
            return
        target = f"{role}/{name}"
        files[target] = raw
        links.append(
            HandoffEvidenceLink(
                snapshot=role,
                source_path=source.relative_to(root).as_posix(),
                packet_file=target,
                sha256=expected,
            )
        )

    overview = selected_receipt(root, Path(saved.identity.overview), "overview.json")
    copy(overview, "overview.json", saved.identity.overview_sha256)
    evidence = next(item for item in saved.evidence if item.kind == "findings")
    if saved.findings is None or evidence.selected_path is None or evidence.report_sha256 is None:
        return files, tuple(links), tuple(issues)
    report_path = selected_receipt(root, Path(evidence.selected_path), "review.json")
    if not recorded_directory(root, saved.findings.output_directory, report_path.parent):
        issues.append(f"{role} findings output directory differs from its selected receipt.")
        return files, tuple(links), tuple(issues)
    copy(report_path, "review.json", evidence.report_sha256)
    for drawing in saved.findings.drawings:
        name = drawing.file
        try:
            verified_findings_drawing(root, report_path, drawing, saved.findings)
        except (OSError, ValueError) as exc:
            issues.append(f"{role} drawing is missing or cannot be safely retained: {name} ({exc})")
            continue
        copy(report_path.parent / name, name, drawing.sha256)
    return files, tuple(links), tuple(issues)


def export_review_handoff(
    root: Path,
    project_id: str,
    baseline: Path,
    candidate: Path,
    notes: Path,
    fingerprints: tuple[str, ...],
    output: Path | None = None,
) -> ReviewHandoffReport:
    """Package exact selected evidence without writing reviewer decisions to project source."""
    root = root.resolve()
    selected = _fingerprints(fingerprints)
    inputs = _read_input(root, project_id, baseline, candidate, notes)
    old_snapshot, old_findings = _snapshot("baseline", inputs.baseline, selected)
    new_snapshot, new_findings = _snapshot("candidate", inputs.candidate, selected)
    findings = (*old_findings, *new_findings)
    note_rows = _notes(inputs.notes, old_snapshot, new_snapshot, findings, selected)
    old_files, old_links, old_issues = _evidence_bytes(root, "baseline", inputs.baseline)
    new_files, new_links, new_issues = _evidence_bytes(root, "candidate", inputs.candidate)

    def verify_inputs() -> None:
        if _read_input(root, project_id, baseline, candidate, notes) != inputs:
            raise ValueError("Selected source or reviewer notes changed during handoff export")
        if _evidence_bytes(root, "baseline", inputs.baseline) != (old_files, old_links, old_issues):
            raise ValueError("Baseline handoff evidence changed during export")
        if _evidence_bytes(root, "candidate", inputs.candidate) != (
            new_files,
            new_links,
            new_issues,
        ):
            raise ValueError("Candidate handoff evidence changed during export")

    verify_inputs()
    target = output or Path("build/review-handoff") / f"{project_id}-{uuid4().hex[:12]}"
    directory = receipt_directory(root, project_id, target)
    files: dict[str, str] = {}
    for name, raw in {**old_files, **new_files, "notes.json": inputs.notes_bytes}.items():
        destination = directory / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(raw)
        files[name] = hashlib.sha256(raw).hexdigest()
    report = ReviewHandoffReport(
        project_id=project_id,
        requested_fingerprints=selected,
        baseline=old_snapshot,
        candidate=new_snapshot,
        findings=findings,
        notes_path=inputs.notes_path.relative_to(root).as_posix(),
        notes_sha256=inputs.notes_sha256,
        notes=note_rows,
        evidence_links=(*old_links, *new_links),
        issues=(*old_issues, *new_issues),
        output_directory=str(directory),
    )
    (directory / "index.html").write_text(render_review_handoff(report), encoding="utf-8")
    files["index.html"] = hashlib.sha256((directory / "index.html").read_bytes()).hexdigest()
    verify_inputs()
    report = report.model_copy(update={"artifacts_sha256": files})
    write_model(directory / "handoff.json", report)
    return report
