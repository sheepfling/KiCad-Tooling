"""Bounded command execution helper for digest-pinned native KiCad fixtures."""

from __future__ import annotations

import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from kicad_tooling.hwrepo.models import CommandEvidence


def execute_kicad_cli(
    image: str,
    argv: tuple[str, ...],
    work: Path,
    *,
    home_directory: str,
    timeout_seconds: int = 300,
) -> CommandEvidence:
    """Run one native CLI command in a read-only, network-disabled pinned image."""
    user = () if os.name == "nt" else ("--user", f"{os.getuid()}:{os.getgid()}")
    mapped: list[str] = []
    for argument in argv[1:]:
        candidate = Path(argument)
        if candidate.is_absolute() and candidate.is_relative_to(work):
            mapped.append(f"/probe/{candidate.relative_to(work).as_posix()}")
        else:
            mapped.append(argument)
    docker_argv = (
        "docker",
        "run",
        "--rm",
        "--platform",
        "linux/amd64",
        "--network",
        "none",
        "--read-only",
        "--tmpfs",
        "/tmp:rw,nosuid,nodev,size=64m",
        *user,
        "-e",
        f"HOME=/tmp/{home_directory}",
        "-v",
        f"{work.resolve()}:/probe:rw",
        "--entrypoint",
        "kicad-cli",
        image,
        *mapped,
    )
    command = CommandEvidence(
        argv=docker_argv,
        started_utc=datetime.now(UTC).isoformat(),
        returncode=127,
    )
    try:
        result = subprocess.run(
            docker_argv,
            cwd=work,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        return command.model_copy(
            update={
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return command.model_copy(update={"error": str(exc)})
