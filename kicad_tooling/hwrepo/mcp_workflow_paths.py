"""Shared project and generated-artifact path selection for MCP workflows."""

from __future__ import annotations

import stat
from pathlib import Path

from pydantic import TypeAdapter

from .contracts import repo_path
from .discovery import load_registry
from .mcp_files import artifact_path
from .models import Identifier, ProjectRecord

_IDENTIFIER: TypeAdapter[str] = TypeAdapter(Identifier)


def identifier(value: str) -> str:
    """Validate a single path component using the repository's identifier contract."""
    return _IDENTIFIER.validate_python(value, strict=True)


def selected_project(root: Path, project_id: str) -> ProjectRecord:
    """Resolve one registered project by its validated identifier."""
    identifier(project_id)
    project = next((item for item in load_registry(root).projects if item.id == project_id), None)
    if project is None:
        raise ValueError(f"Unknown project ID: {project_id}. Call list_projects first.")
    return project


def artifact_file(root: Path, value: str) -> Path:
    """Require a repository-contained generated artifact file."""
    path = artifact_path(root, value)
    if not path.is_file():
        raise ValueError(f"Select an existing generated artifact file: {value}")
    return path


def native_summary_path(root: Path, value: str) -> Path:
    """Constrain a native summary and any sibling evidence read by workflow coaches."""
    path = artifact_path(root, value)
    if path.is_dir():
        path = artifact_file(root, (path / "summary.json").relative_to(root).as_posix())
    elif not path.is_file():
        raise ValueError(f"Select an existing native summary: {value}")
    for name in ("erc.json", "drc.json", "netlist.xml", "netlist.command.json"):
        sibling = artifact_path(root, (path.parent / name).relative_to(root).as_posix())
        if sibling.exists() and not stat.S_ISREG(sibling.lstat().st_mode):
            raise ValueError("Native evidence siblings must be regular files")
    return path


def fresh_output(root: Path, directory: str, output_id: str, suffix: str = "") -> Path:
    """Resolve a unique ignored workflow output path from a checked identifier."""
    path = repo_path(root, f"build/{directory}/{identifier(output_id)}{suffix}")
    if path.exists():
        raise ValueError(f"Output already exists; choose a fresh ID: {path.relative_to(root)}")
    return path
