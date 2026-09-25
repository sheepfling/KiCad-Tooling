"""Bounded foreign-board conversion for the optional MCP adapter."""
from __future__ import annotations

from pathlib import Path

from . import foreign_pcb
from .contracts import repo_path
from .doctor import NativeRunner
from .models import ForeignFormat, ForeignPcbReport


def source_path(root: Path, source: str, import_roots: tuple[Path, ...]) -> Path:
    """Check source containment before any native command or receipt is created."""
    candidate = Path(source).expanduser()
    if ".." in candidate.parts:
        raise ValueError("Conversion source must not contain parent traversal")
    candidate = candidate if candidate.is_absolute() else root / candidate
    for scope in (root, *import_roots):
        if candidate.is_relative_to(scope):
            relative = candidate.relative_to(scope).as_posix()
            if relative == ".":
                raise ValueError("Select one foreign PCB file, not an import directory")
            path = repo_path(scope, relative)
            if path.exists() and not path.is_file():
                raise ValueError("Conversion source must be a regular file")
            return path
    raise ValueError("Conversion source is outside the checkout and configured --import-root directories")


def convert_pcb(
    root: Path, source: str, project_id: str, toolchain_id: str,
    input_format: ForeignFormat = "auto", runner: NativeRunner = "auto", *,
    import_roots: tuple[Path, ...] = (),
) -> ForeignPcbReport:
    """Convert into a fresh ignored receipt; a separate reviewed import is required."""
    root = root.resolve()
    if runner not in {"auto", "local", "container"}:
        raise ValueError(f"Unknown native runner: {runner}")
    selected = source_path(root, source, import_roots)
    repo_path(root, "build/diagnostics")
    return foreign_pcb.convert_pcb(root, selected, project_id, toolchain_id,
                                  input_format, runner, cli="kicad-cli")
