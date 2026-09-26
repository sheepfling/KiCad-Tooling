"""Portable log retention and Actions summaries for the shared 3D renderer."""

from __future__ import annotations

import html
import os
import shutil
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from .contracts import repo_path
from .doctor import NativeRunner

if TYPE_CHECKING:
    from ..ci_hosted import HostedLog


def preview_lane(
    root: Path,
    project: str,
    log: HostedLog,
    *,
    runner: NativeRunner = "auto",
    cli: str = "kicad-cli",
    output: Path = Path("build/3d-preview"),
) -> None:
    """Keep fresh renderer evidence, including errors before a receipt is created."""
    root = root.resolve()
    output = root / output if not output.is_absolute() else output
    output = repo_path(root, output.relative_to(root).as_posix())
    if not output.is_relative_to(root / "build") or output == root / "build":
        raise ValueError("3D preview output must be a fresh directory under ignored build/")
    if output.exists():
        raise ValueError(f"3D preview output already exists; choose a fresh --output: {output}")
    stdout = log.directory / "preview.stdout.log"
    stderr = log.directory / "preview.stderr.log"
    try:
        log.run(
            "preview",
            (
                sys.executable,
                "-I",
                "-X",
                "utf8",
                "-B",
                "-m",
                "kicad_tooling.visualize",
                "--root",
                str(root),
                "--project",
                project,
                "--runner",
                runner,
                "--cli",
                cli,
                "--output",
                str(output),
                "--format",
                "text",
            ),
            cwd=root,
        )
    finally:
        # Validate again before writing into a directory created by the child.
        repo_path(root, output.relative_to(root).as_posix())
        output.mkdir(parents=True, exist_ok=True)
        for source, name in ((stdout, "cli.stdout.txt"), (stderr, "cli.stderr.txt")):
            if source.is_file():
                destination = repo_path(root, (output / name).relative_to(root).as_posix())
                shutil.copyfile(source, destination)
        if stdout.is_file():
            print(stdout.read_text(encoding="utf-8", errors="replace"), end="", flush=True)
        summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary:
            report = repo_path(root, (output / "visualization.txt").relative_to(root).as_posix())
            text = (
                report.read_text(encoding="utf-8")
                if report.is_file()
                else "No visualization report was produced. Inspect the retained CLI logs."
            )
            with Path(summary).open("a", encoding="utf-8") as stream:
                stream.write("## KiCad 3D preview\n\n<pre>" + html.escape(text) + "</pre>\n")
