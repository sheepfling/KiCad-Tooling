"""Typed comparison of two explicitly selected project review snapshots."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from pydantic import Field

from .model_primitives import Digest, Identifier, RepositoryPath, StrictModel
from .review_overview_models import Freshness, OverviewKind

EvidenceState = Literal["CURRENT", "STALE", "MISSING", "UNAVAILABLE", "NOT_SELECTED"]
CheckState = Literal["PASS", "FAIL", "NOT_RUN", "MISSING", "STALE", "UNAVAILABLE"]
StageState = Literal[
    "PASS",
    "FAIL",
    "ERROR",
    "REVIEW",
    "BLOCKED",
    "NOT_CONFIGURED",
    "NEEDS_WORK",
    "NOT_RUN",
    "MISSING",
    "STALE",
    "UNAVAILABLE",
]
Change = Literal["ADDED", "REMOVED", "CHANGED", "UNCHANGED"]


class HistorySnapshot(StrictModel):
    overview: RepositoryPath
    overview_sha256: Digest
    project_manifest_sha256: Digest
    source_hashes: Mapping[RepositoryPath, Digest]
    source_fingerprint: Digest
    source_relation: Literal["CURRENT", "HISTORICAL", "UNKNOWN"]
    source_commit: str | None = None
    issues: tuple[str, ...] = ()


class HistoryEvidence(StrictModel):
    kind: OverviewKind
    selected_path: RepositoryPath | None = None
    status: str
    captured_freshness: Freshness
    integrity: EvidenceState
    report_sha256: Digest | None = None
    issues: tuple[str, ...] = ()


class HistoryEvidenceChange(StrictModel):
    kind: OverviewKind
    change: Change
    before: HistoryEvidence
    after: HistoryEvidence


class HistoryCheckChange(StrictModel):
    name: Identifier
    before: CheckState
    after: CheckState
    detail: str = ""


class HistoryStageChange(StrictModel):
    name: Literal[
        "verification", "portable", "doctor", "native", "design_lint", "electrical", "diagnosis"
    ]
    change: Change
    before: StageState
    after: StageState


class HistorySourceChange(StrictModel):
    path: RepositoryPath
    change: Change
    before_sha256: Digest | None = None
    after_sha256: Digest | None = None


class HistoryFindingChange(StrictModel):
    origin: Literal["ERC", "DRC", "DESIGN_LINT"]
    rule: str
    title: str
    change: Literal["ADDED", "REMOVED", "CHANGED_FINGERPRINT", "CHANGED_DETAIL", "UNCHANGED"]
    before_fingerprint: Digest | None = None
    after_fingerprint: Digest | None = None
    explanation: str = ""


class HistoryArtifact(StrictModel):
    id: Identifier
    kind: str
    path: RepositoryPath
    sha256: Digest
    integrity: Literal["CURRENT", "STALE", "MISSING"]


class HistoryRelease(StrictModel):
    manifest: RepositoryPath | None = None
    manifest_sha256: Digest | None = None
    release_id: Identifier | None = None
    source_commit: str | None = None
    source_relation: Literal["MATCHED", "MISMATCH", "UNKNOWN", "NOT_SELECTED"] = "NOT_SELECTED"
    status: str = "NOT_SELECTED"
    artifacts: tuple[HistoryArtifact, ...] = ()
    issues: tuple[str, ...] = ()


class HistoryArtifactChange(StrictModel):
    id: Identifier
    change: Change
    before: HistoryArtifact | None = None
    after: HistoryArtifact | None = None


class VerificationHistoryReport(StrictModel):
    schema_version: Literal["1"] = "1"
    lane: Literal["VERIFICATION_HISTORY"] = "VERIFICATION_HISTORY"
    build_authorized: Literal[False] = False
    project_id: Identifier
    baseline: HistorySnapshot
    candidate: HistorySnapshot
    baseline_release: HistoryRelease
    candidate_release: HistoryRelease
    source_changes: tuple[HistorySourceChange, ...]
    evidence_changes: tuple[HistoryEvidenceChange, ...]
    check_changes: tuple[HistoryCheckChange, ...]
    stage_changes: tuple[HistoryStageChange, ...] = ()
    finding_changes: tuple[HistoryFindingChange, ...]
    artifact_changes: tuple[HistoryArtifactChange, ...]
    output_directory: str
    artifacts_sha256: Mapping[RepositoryPath, Digest] = Field(default_factory=dict)
