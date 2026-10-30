"""Typed reviewer-note scope and portable findings handoff evidence."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from pydantic import Field, model_validator

from .findings_view_models import ReviewFinding
from .model_primitives import Digest, Identifier, NonEmptyText, RepositoryPath, StrictModel
from .verification_history_models import HistorySnapshot

SnapshotRole = Literal["baseline", "candidate"]
NoteAssessment = Literal["observation", "needs_review", "resolved_claim"]
NoteState = Literal["CURRENT", "OUTDATED_RECEIPT", "OUTDATED_FINGERPRINT", "UNAVAILABLE"]


class ReviewerNote(StrictModel):
    id: Identifier
    reviewer: NonEmptyText
    recorded_at: NonEmptyText
    snapshot: SnapshotRole
    overview_sha256: Digest
    finding_fingerprint: Digest
    assessment: NoteAssessment
    text: NonEmptyText


class ReviewerNotesFile(StrictModel):
    schema_version: Literal["1"] = "1"
    project_id: Identifier
    notes: tuple[ReviewerNote, ...]

    @model_validator(mode="after")
    def unique_ids(self) -> ReviewerNotesFile:
        ids = [item.id for item in self.notes]
        if len(ids) != len(set(ids)):
            raise ValueError("Reviewer note IDs must be unique")
        return self


class HandoffFinding(StrictModel):
    snapshot: SnapshotRole
    fingerprint: Digest
    finding: ReviewFinding


class HandoffNote(StrictModel):
    note: ReviewerNote
    state: NoteState
    conflict: bool = False


class HandoffSnapshot(StrictModel):
    snapshot: SnapshotRole
    identity: HistorySnapshot
    findings_receipt: RepositoryPath | None = None
    findings_receipt_sha256: Digest | None = None
    findings_integrity: NonEmptyText
    issues: tuple[NonEmptyText, ...] = ()


class HandoffEvidenceLink(StrictModel):
    snapshot: SnapshotRole
    source_path: RepositoryPath
    packet_file: RepositoryPath
    sha256: Digest


class ReviewHandoffReport(StrictModel):
    schema_version: Literal["1"] = "1"
    lane: Literal["REVIEW_HANDOFF"] = "REVIEW_HANDOFF"
    build_authorized: Literal[False] = False
    project_id: Identifier
    requested_fingerprints: tuple[Digest, ...]
    baseline: HandoffSnapshot
    candidate: HandoffSnapshot
    findings: tuple[HandoffFinding, ...]
    notes_path: RepositoryPath
    notes_sha256: Digest
    notes: tuple[HandoffNote, ...]
    evidence_links: tuple[HandoffEvidenceLink, ...] = ()
    issues: tuple[NonEmptyText, ...] = ()
    output_directory: str
    artifacts_sha256: Mapping[RepositoryPath, Digest] = Field(default_factory=dict)
