"""Capture native KiCad commands and validate their exported files."""

from __future__ import annotations

import csv
import subprocess
import xml.etree.ElementTree as ET
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path

from .contracts import write_model
from .generation import csv_cell
from .models import CommandEvidence
from .project_models import ComponentContract


def svg_files(output: Path, name: str) -> list[Path]:
    files: list[Path] = (
        list((output / "schematic").glob("*.svg"))
        if name == "schematic_svg"
        else [output / "pcb.svg"]
    )
    if not files or any(not p.is_file() or p.stat().st_size == 0 for p in files):
        raise ValueError("Missing SVG export")
    for path in files:
        if ET.parse(path).getroot().tag != "{http://www.w3.org/2000/svg}svg":
            raise ValueError("Export is not an SVG document")
    return files
def execute(argv: Sequence[str], cwd: Path, output: Path, name: str) -> CommandEvidence:
    record = CommandEvidence(
        argv=tuple(argv),
        started_utc=datetime.now(UTC).isoformat(),
        returncode=127,
    )
    try:
        result = subprocess.run(
            argv,
            cwd=cwd,
            text=True,
            capture_output=True,
            timeout=180,
            check=False,
        )
        record = record.model_copy(
            update={
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        record = record.model_copy(update={"error": str(exc)})
    write_model(output / f"{name}.command.json", record)
    return record
def write_native_bom(
    path: Path,
    components: Mapping[str, ComponentContract],
    disposition: str,
) -> None:
    """Write the native review BOM with the same CSV cell policy as other exports."""
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(("Reference", "Value", "Footprint", "Disposition"))
        for reference, component in components.items():
            writer.writerow(
                tuple(
                    csv_cell(cell)
                    for cell in (
                        reference,
                        component.value,
                        component.footprint,
                        disposition,
                    )
                )
            )
