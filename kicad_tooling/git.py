"""Run Git commands against an explicit repository root."""

from __future__ import annotations

import subprocess
from collections.abc import Mapping
from pathlib import Path


def _command(root: Path, args: tuple[str, ...]) -> tuple[str, ...]:
    resolved = root.resolve()
    return (
        "git",
        "-c",
        f"safe.directory={resolved.as_posix()}",
        "-C",
        str(resolved),
        *args,
    )


def run_git_text(
    root: Path,
    *args: str,
    check: bool = True,
    timeout: float | None = None,
    env: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run Git with text output while preserving stdout and stderr exactly."""
    return subprocess.run(
        _command(root, args),
        capture_output=True,
        check=check,
        env=env,
        text=True,
        timeout=timeout,
    )


def run_git_bytes(
    root: Path,
    *args: str,
    input_bytes: bytes | None = None,
    check: bool = True,
    timeout: float | None = None,
    env: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[bytes]:
    """Run Git with byte output for NUL-delimited paths and object content."""
    return subprocess.run(
        _command(root, args),
        capture_output=True,
        check=check,
        env=env,
        input=input_bytes,
        timeout=timeout,
    )


def git_output(root: Path, *args: str, timeout: float | None = None) -> str:
    """Return one stripped text fact from a successful Git command."""
    return run_git_text(root, *args, timeout=timeout).stdout.strip()
