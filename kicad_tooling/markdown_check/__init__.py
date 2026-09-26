"""Adapter for the native executable recorded by the installed rumdl distribution."""

from __future__ import annotations

import subprocess
import sys
from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path


def executable() -> Path:
    """Resolve the wheel-owned binary, never a guessed prefix or ambient PATH entry."""
    installed = distribution("rumdl")
    candidates = [
        Path(str(installed.locate_file(item)))
        for item in installed.files or ()
        if item.name in {"rumdl", "rumdl.exe"}
    ]
    if len(candidates) != 1 or not candidates[0].is_file():
        raise ValueError("Installed rumdl metadata must identify exactly one native executable")
    return candidates[0]


def run(arguments: list[str]) -> int:
    """Keep the Rust tool exception behind a package-owned Python module interface."""
    try:
        return subprocess.run((str(executable()), *arguments), check=False).returncode
    except (OSError, PackageNotFoundError, ValueError) as exc:
        print(
            f"Markdown checker unavailable: {exc}. Reinstall the project tooling extras.",
            file=sys.stderr,
        )
        return 127
