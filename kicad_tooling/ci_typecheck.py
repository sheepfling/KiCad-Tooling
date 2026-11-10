"""Validate scoped Pyright inputs and assemble deterministic commands."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path, PurePosixPath


def validate_typecheck_paths(paths: Iterable[str], root: Path) -> tuple[str, ...]:
    """Accept only existing Python modules contained in the tooling package."""
    source_roots = tuple((root / name).resolve() for name in ("kicad_tooling", "scripts"))
    accepted: set[str] = set()
    for value in paths:
        parsed = PurePosixPath(value)
        candidate = (root / value).resolve()
        if (
            parsed.is_absolute()
            or ".." in parsed.parts
            or "\\" in value
            or value != parsed.as_posix()
            or parsed.suffix != ".py"
            or not value.startswith(("kicad_tooling/", "scripts/"))
            or not any(candidate.is_relative_to(source_root) for source_root in source_roots)
            or not candidate.is_file()
        ):
            raise ValueError(
                f"Pyright targets must be existing Python modules under kicad_tooling/ or scripts/: {value}"
            )
        accepted.add(parsed.as_posix())
    return tuple(sorted(accepted))


def pyright_command(
    python: str,
    *,
    target_paths: tuple[str, ...] = (),
    windows: bool = False,
) -> tuple[str, ...]:
    """Build the Linux-hosted Pyright invocation for the requested platform."""
    command = (python, "-m", "pyright", "--pythonpath", python)
    if windows:
        command += ("--pythonplatform", "Windows", "--pythonversion", "3.11")
    return (*command, *target_paths)
