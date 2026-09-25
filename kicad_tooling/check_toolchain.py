"""Fail before editing when the locally installed KiCad does not match the approved toolchain."""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from .hwrepo.contracts import read_model, repo_path
from .hwrepo.discovery import settings
from .hwrepo.models import ToolchainAssessment, ToolchainRecord, ToolchainsCatalog

MACOS_KICAD_CLI = Path("/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli")


def toolchain(root: Path, identifier: str) -> ToolchainRecord:
    catalog = read_model(repo_path(root, settings(root).catalogs.toolchains), ToolchainsCatalog)
    for record in catalog.toolchains:
        if record.id == identifier:
            return record
    raise ValueError(f"Unknown toolchain {identifier!r}")


def assessment(
    record: ToolchainRecord, observed_version: str | None
) -> ToolchainAssessment:
    matches = observed_version == record.kicad_version
    return ToolchainAssessment(
        toolchain_id=record.id,
        expected_version=record.kicad_version,
        observed_version=observed_version,
        desktop_editing_allowed=matches,
        status="PASS" if matches else "FAIL",
        next_action=(
            "Use this KiCad build for editing."
            if matches
            else "Do not save or convert this project. Use the approved build or open a dedicated migration branch."
        ),
    )


def cli_executable(cli: str) -> str | None:
    """Resolve a command or explicit path against the caller's current directory.

    Native checks run subprocesses from the repository root, so never return a
    relative executable path that would change meaning after that cwd switch.
    """
    executable: str | None = shutil.which(cli)
    if executable is not None:
        return str(Path(executable).resolve())
    explicit: Path = Path(cli)
    if explicit.is_file():
        return str(explicit.resolve())
    if cli != "kicad-cli":
        return None
    if sys.platform == "darwin" and MACOS_KICAD_CLI.is_file():
        return str(MACOS_KICAD_CLI)
    roots: list[Path] = []
    for variable in ("LOCALAPPDATA", "ProgramFiles"):
        value: str | None = os.environ.get(variable)
        if value:
            roots.append(Path(value) / "Programs" / "KiCad") if variable == "LOCALAPPDATA" else roots.append(Path(value) / "KiCad")
    candidates: list[Path] = [
        candidate for root in roots if root.is_dir()
        for candidate in root.glob("*/bin/kicad-cli.exe") if candidate.is_file()
    ]
    return str(candidates[0].resolve()) if len(candidates) == 1 else None


def observed_version(cli: str) -> str | None:
    executable: str | None = cli_executable(cli)
    if executable is None:
        return None
    try:
        result: subprocess.CompletedProcess[str] = subprocess.run(
            [executable, "version"], text=True, capture_output=True, timeout=30, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--toolchain", default="kicad-10.0.0")
    parser.add_argument(
        "--cli", default="kicad-cli",
        help="KiCad CLI command or path (relative paths use the caller's cwd)",
    )
    args = parser.parse_args()
    result = assessment(toolchain(args.root.resolve(), args.toolchain), observed_version(args.cli))
    print(result.model_dump_json(indent=2))
    return 0 if result.status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
