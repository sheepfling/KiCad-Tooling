"""Source-bound library and mechanical records consumed by governance lint."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .governance_records import (
    GovernanceSourceFileInput,
    capture_governance_source_file,
    governance_source_file_freshness_issue,
)
from .model_primitives import Digest, RepositoryPath
from .models import LibraryRecord
from .project_models import ProjectRecord

LibraryEvidenceKind = Literal["provenance", "licensing"]
MechanicalHandoffState = Literal["NOT_DECLARED", "MISSING", "UNAVAILABLE", "EVALUATED"]


@dataclass(frozen=True, slots=True)
class LibraryEvidenceFileInput:
    """One library evidence document and the digest authored in its catalog."""

    kind: LibraryEvidenceKind
    expected_sha256: Digest
    file: GovernanceSourceFileInput


@dataclass(frozen=True, slots=True)
class LibraryEvidenceInput:
    """Captured provenance and licensing files for one selected library."""

    library_id: str
    provenance: LibraryEvidenceFileInput
    licensing: LibraryEvidenceFileInput


@dataclass(frozen=True, slots=True)
class ProjectMechanicalHandoffInput:
    """Declared mechanical handoff state for one production project."""

    project_id: str
    path: RepositoryPath | None
    file: GovernanceSourceFileInput | None

    def __post_init__(self) -> None:
        if self.path is None and self.file is not None:
            raise ValueError("Undeclared mechanical handoffs cannot contain a file input")
        if self.path is not None and (self.file is None or self.file.requested_path != self.path):
            raise ValueError("Declared mechanical handoffs require their requested file input")

    @property
    def state(self) -> MechanicalHandoffState:
        if self.file is None:
            return "NOT_DECLARED"
        return self.file.state


@dataclass(frozen=True, slots=True)
class GovernanceLintFilesystemInputs:
    """Named filesystem inputs retained for one governance lint operation."""

    library_evidence: tuple[LibraryEvidenceInput, ...]
    mechanical_handoffs: tuple[ProjectMechanicalHandoffInput, ...]

    @property
    def issues(self) -> tuple[str, ...]:
        issues: list[str] = []
        for library in self.library_evidence:
            for evidence in (library.provenance, library.licensing):
                file = evidence.file
                if file.state == "MISSING":
                    issues.append(
                        f"library {library.library_id}: {evidence.kind} record is missing: "
                        f"{file.requested_path}"
                    )
                elif file.state == "UNAVAILABLE":
                    issues.append(
                        f"library {library.library_id}: {evidence.kind} record is unavailable: "
                        f"{file.issue}"
                    )
                elif file.source is not None and file.source.sha256 != evidence.expected_sha256:
                    issues.append(
                        f"library {library.library_id}: {evidence.kind} record hash does not match"
                    )

        for handoff in self.mechanical_handoffs:
            if handoff.state == "NOT_DECLARED":
                issues.append(f"project {handoff.project_id}: mechanical_handoff record is missing")
            elif handoff.state == "MISSING":
                issues.append(f"project {handoff.project_id}: mechanical handoff record is missing")
            elif handoff.state == "UNAVAILABLE" and handoff.file is not None:
                issues.append(
                    f"project {handoff.project_id}: mechanical_handoff: {handoff.file.issue}"
                )
        return tuple(issues)


def capture_governance_lint_filesystem_inputs(
    root: Path,
    libraries: tuple[LibraryRecord, ...],
    projects: tuple[ProjectRecord, ...],
) -> GovernanceLintFilesystemInputs:
    """Capture selected library evidence and declared production handoff files."""
    library_evidence = tuple(
        LibraryEvidenceInput(
            library_id=library.id,
            provenance=LibraryEvidenceFileInput(
                kind="provenance",
                expected_sha256=library.provenance_sha256,
                file=capture_governance_source_file(root, library.provenance_path),
            ),
            licensing=LibraryEvidenceFileInput(
                kind="licensing",
                expected_sha256=library.licensing_sha256,
                file=capture_governance_source_file(root, library.licensing_path),
            ),
        )
        for library in libraries
    )
    mechanical_handoffs = tuple(
        ProjectMechanicalHandoffInput(
            project_id=project.id,
            path=project.mechanical_handoff,
            file=(
                None
                if project.mechanical_handoff is None
                else capture_governance_source_file(root, project.mechanical_handoff)
            ),
        )
        for project in projects
        if project.assurance_profile == "production"
    )
    return GovernanceLintFilesystemInputs(
        library_evidence=library_evidence,
        mechanical_handoffs=mechanical_handoffs,
    )


def governance_lint_filesystem_freshness_issues(
    root: Path, inputs: GovernanceLintFilesystemInputs
) -> tuple[str, ...]:
    """Recheck each captured document or explicit missing/unavailable state."""
    issues: list[str] = []
    for library in inputs.library_evidence:
        for evidence in (library.provenance, library.licensing):
            issue = governance_source_file_freshness_issue(root, evidence.file)
            if issue is not None:
                issues.append(f"library {library.library_id}: {issue}")
    for handoff in inputs.mechanical_handoffs:
        if handoff.file is None:
            continue
        issue = governance_source_file_freshness_issue(root, handoff.file)
        if issue is not None:
            issues.append(f"project {handoff.project_id}: {issue}")
    return tuple(issues)
