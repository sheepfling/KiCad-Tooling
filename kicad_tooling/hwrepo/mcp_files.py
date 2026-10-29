"""MCP artifact reads and compatibility exports for project-source operations."""

from __future__ import annotations

import stat
from pathlib import Path

from .artifact_access import artifact_path, read_regular_bytes
from .bounded_file_content import (
    MAX_CHUNK,
    MAX_TEXT_BYTES,
    file_digest,
    read_file_content,
    validate_bounds,
)
from .file_access_models import McpFileContent
from .models import McpArtifactEntry, McpArtifactList
from .project_source_access import (
    CAD_TEXT_SUFFIXES,
    FORBIDDEN_SOURCE_PARTS,
    MAX_DIFF,
    MAX_EDIT_BYTES,
    apply_project_edit,
    preview_project_edit,
    project_file_path,
    read_project_file,
)

__all__ = [
    "ARTIFACT_TEXT_SUFFIXES",
    "CAD_TEXT_SUFFIXES",
    "FORBIDDEN_SOURCE_PARTS",
    "MAX_CHUNK",
    "MAX_DIFF",
    "MAX_DIRECTORY_ENTRIES",
    "MAX_EDIT_BYTES",
    "MAX_TEXT_BYTES",
    "apply_project_edit",
    "artifact_path",
    "list_artifacts",
    "preview_project_edit",
    "project_file_path",
    "read_artifact",
    "read_project_file",
    "read_regular_bytes",
]

MAX_DIRECTORY_ENTRIES = 10_000
ARTIFACT_TEXT_SUFFIXES = frozenset(
    {
        ".json",
        ".jsonl",
        ".csv",
        ".tsv",
        ".txt",
        ".log",
        ".md",
        ".svg",
        ".xml",
        ".net",
        ".gbr",
        ".ger",
        ".gbrjob",
        ".drl",
        ".pos",
        ".yaml",
        ".yml",
        ".toml",
        ".cir",
        ".raw",
    }
)


def list_artifacts(
    root: Path, directory: str = "build", offset: int = 0, limit: int = 100
) -> McpArtifactList:
    """List one directory level with stable ordering and bounded response size."""
    validate_bounds(offset, limit, 100)
    base = artifact_path(root, directory)
    if not base.is_dir():
        raise ValueError("Artifact directory does not exist")
    children: list[Path] = []
    for child in base.iterdir():
        if child.name == "restores":
            continue
        if len(children) >= MAX_DIRECTORY_ENTRIES:
            raise ValueError("Artifact directory has too many entries; choose a narrower receipt")
        children.append(child)
    children.sort(key=lambda child: child.name)
    entries: list[McpArtifactEntry] = []
    for child in children[offset : offset + limit]:
        name = child.relative_to(root.resolve()).as_posix()
        safe = artifact_path(root, name)
        information = safe.stat()
        if stat.S_ISDIR(information.st_mode):
            entries.append(McpArtifactEntry(path=name, kind="directory"))
        elif stat.S_ISREG(information.st_mode):
            digest = file_digest(safe)[0] if information.st_size <= MAX_EDIT_BYTES else None
            entries.append(
                McpArtifactEntry(
                    path=name, kind="file", size_bytes=information.st_size, sha256=digest
                )
            )
        else:
            raise ValueError(f"Artifact is not a regular file or directory: {name}")
    next_offset = offset + len(entries)
    more = next_offset < len(children)
    return McpArtifactList(
        directory=base.relative_to(root.resolve()).as_posix(),
        entries=tuple(entries),
        offset=offset,
        total_entries=len(children),
        truncated=more,
        next_offset=next_offset if more else None,
    )


def read_artifact(root: Path, path: str, offset: int = 0, limit: int = MAX_CHUNK) -> McpFileContent:
    """Read a UTF-8 artifact chunk; unsupported/binary files return metadata only."""
    selected = artifact_path(root, path)
    return read_file_content(
        root, selected, offset, limit, selected.suffix.lower() in ARTIFACT_TEXT_SUFFIXES
    )
