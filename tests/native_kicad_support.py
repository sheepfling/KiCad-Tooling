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
    fixture_directory: Path | None = None,
    output_directory: Path | None = None,
    timeout_seconds: int = 300,
) -> CommandEvidence:
    """Run a native CLI command in a read-only, network-disabled pinned image.

    When fixture and output directories are supplied, mount them separately so
    native commands can read only the fixture tree and write only their outputs.
    """
    if (fixture_directory is None) != (output_directory is None):
        raise ValueError("Fixture and output directories must be supplied together")

    user = () if os.name == "nt" else ("--user", f"{os.getuid()}:{os.getgid()}")
    mapped: list[str] = []
    fixture_root = fixture_directory.resolve() if fixture_directory is not None else None
    output_root = output_directory.resolve() if output_directory is not None else None
    for argument in argv[1:]:
        candidate = Path(argument)
        if (
            fixture_root is not None
            and candidate.is_absolute()
            and candidate.is_relative_to(fixture_root)
        ):
            mapped.append(f"/fixtures/{candidate.relative_to(fixture_root).as_posix()}")
        elif (
            output_root is not None
            and candidate.is_absolute()
            and candidate.is_relative_to(output_root)
        ):
            mapped.append(f"/output/{candidate.relative_to(output_root).as_posix()}")
        elif candidate.is_absolute() and candidate.is_relative_to(work):
            mapped.append(f"/probe/{candidate.relative_to(work).as_posix()}")
        else:
            mapped.append(argument)

    if fixture_root is not None and output_root is not None:
        mounts = (
            "-v",
            f"{fixture_root}:/fixtures:ro",
            "-v",
            f"{output_root}:/output:rw",
            "-w",
            "/fixtures",
        )
    else:
        mounts = ("-v", f"{work.resolve()}:/probe:rw")

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
        *mounts,
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
