"""Bounded project-file membership snapshots for repository discovery checks."""

from __future__ import annotations

from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .contracts import repo_path
from .discovery import MAX_PROJECT_DISCOVERY_ENTRIES
from .layout import RESERVED_DIRECTORIES
from .model_primitives import RepositoryPath

ProjectFileRootState = Literal["MISSING", "UNAVAILABLE", "EVALUATED"]


@dataclass(frozen=True, slots=True)
class ProjectFileRootMembership:
    """Observed native project files beneath one configured discovery root."""

    root: RepositoryPath
    state: ProjectFileRootState
    files: tuple[RepositoryPath, ...]
    issue: str | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "files", tuple(sorted(set(self.files))))
        if self.state == "EVALUATED":
            if self.issue is not None:
                raise ValueError("Evaluated project roots cannot have an availability issue")
        elif self.files or self.issue is None:
            raise ValueError("Unevaluated project roots require an issue and no file list")


@dataclass(frozen=True, slots=True)
class ProjectFileMembershipSnapshot:
    """Named root states and exact project-file membership for one lint operation."""

    roots: tuple[ProjectFileRootMembership, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "roots", tuple(self.roots))
        names = tuple(item.root for item in self.roots)
        if len(names) != len(set(names)):
            raise ValueError("Project membership roots must be unique")

    @property
    def files(self) -> tuple[RepositoryPath, ...]:
        return tuple(sorted({path for item in self.roots for path in item.files}))

    @property
    def issues(self) -> tuple[str, ...]:
        return tuple(
            f"project discovery: project-file membership {item.state.lower()} under "
            f"{item.root}: {item.issue}"
            for item in self.roots
            if item.state != "EVALUATED"
        )


def _capture_project_file_root(root: Path, value: RepositoryPath) -> ProjectFileRootMembership:
    try:
        directory = repo_path(root, value)
        if not directory.exists():
            return ProjectFileRootMembership(
                value, "MISSING", (), "configured project root is missing"
            )
        if not directory.is_dir():
            return ProjectFileRootMembership(
                value, "UNAVAILABLE", (), "configured project root is not a directory"
            )
        files: list[RepositoryPath] = []
        visited = 0
        pending = [directory]
        while pending:
            current = pending.pop()
            for child in sorted(current.iterdir(), key=lambda path: path.name, reverse=True):
                visited += 1
                if visited > MAX_PROJECT_DISCOVERY_ENTRIES:
                    raise ValueError(
                        f"project-file membership exceeded {MAX_PROJECT_DISCOVERY_ENTRIES} entries"
                    )
                if (
                    child.name.startswith(".")
                    or child.name.casefold() in RESERVED_DIRECTORIES
                    or child.name.endswith("-backups")
                ):
                    continue
                if child.is_symlink():
                    raise ValueError(f"project-file membership contains a symlink: {child}")
                if child.is_dir():
                    pending.append(child)
                    continue
                if child.is_file() and child.suffix == ".kicad_pro":
                    relative = child.relative_to(root).as_posix()
                    repo_path(root, relative)
                    files.append(relative)
    except FileNotFoundError as exc:
        return ProjectFileRootMembership(value, "MISSING", (), str(exc))
    except (OSError, ValueError) as exc:
        message = str(exc)
        return ProjectFileRootMembership(value, "UNAVAILABLE", (), message)
    return ProjectFileRootMembership(value, "EVALUATED", tuple(files), None)


def capture_project_file_membership(
    root: Path, discovery_roots: tuple[RepositoryPath, ...]
) -> ProjectFileMembershipSnapshot:
    """Capture project-file membership in the supplied configured roots."""
    root = root.resolve()
    return ProjectFileMembershipSnapshot(
        tuple(_capture_project_file_root(root, value) for value in discovery_roots)
    )


def project_file_membership_issues(
    snapshot: ProjectFileMembershipSnapshot,
    declared_projects: AbstractSet[RepositoryPath],
) -> tuple[str, ...]:
    """Compare observed project files with the registry-derived declarations."""
    issues = list(snapshot.issues)
    if any(item.state != "EVALUATED" for item in snapshot.roots):
        return tuple(issues)
    observed = set(snapshot.files)
    if observed != declared_projects:
        issues.append(
            f"project discovery: undeclared or missing project files "
            f"{sorted(declared_projects ^ observed)}"
        )
    return tuple(issues)


def project_file_membership_freshness_issues(
    root: Path, captured: ProjectFileMembershipSnapshot
) -> tuple[str, ...]:
    """Recheck root availability and exact project-file membership."""
    current = capture_project_file_membership(root, tuple(item.root for item in captured.roots))
    issues: list[str] = []
    for before, after in zip(captured.roots, current.roots, strict=True):
        if before.state != after.state:
            issues.append(
                f"Project-file membership root {before.root} changed state during operation "
                f"({before.state} to {after.state})"
            )
        elif before.state == "EVALUATED" and before.files != after.files:
            issues.append(f"Project-file membership changed during operation under {before.root}")
    return tuple(issues)
