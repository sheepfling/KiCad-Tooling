"""MCP request boundaries for authorized source paths and serialized operations."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from subprocess import SubprocessError
from threading import Lock
from zipfile import BadZipFile

from mcp.server.mcpserver.exceptions import ToolError

from .contracts import repo_path


def import_path(
    root: Path,
    source: str,
    scopes: tuple[Path, ...],
    *,
    directory: bool = False,
) -> Path:
    """Authorize a source before the importer resolves its parent or reads siblings."""
    candidate = Path(source).expanduser()
    if ".." in candidate.parts:
        raise ValueError("Import source must not contain parent traversal")
    candidate = candidate if candidate.is_absolute() else root / candidate
    for scope in scopes:
        if candidate.is_relative_to(scope):
            relative = candidate.relative_to(scope).as_posix()
            path = scope.resolve() if relative == "." else repo_path(scope, relative)
            if directory:
                if not path.is_dir():
                    raise ValueError("Select an existing import source directory")
            elif path.suffix != ".kicad_pro" or not path.is_file():
                raise ValueError("Select an existing .kicad_pro file, not a directory")
            return path
    raise ValueError(
        "Import source is outside the checkout and configured --import-root directories"
    )


@contextmanager
def service_operation(operation: Lock) -> Generator[None, None, None]:
    """Preserve actionable service/input errors in the MCP tool response."""
    with operation:
        try:
            yield
        except (OSError, ValueError, BadZipFile, SubprocessError) as exc:
            raise ToolError(str(exc)) from exc
