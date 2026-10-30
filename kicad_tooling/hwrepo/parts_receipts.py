"""Read and validate explicitly selected, source-bound parts receipts."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from pathlib import Path
from typing import Literal

from pydantic import Field

from .artifact_access import artifact_path, read_regular_bytes
from .contracts import parse_model_text, read_model, repo_path
from .evidence import digest
from .model_primitives import Digest, RepositoryPath, StrictModel
from .models import PurchasingReport


class PartsOutputManifest(StrictModel):
    """Bind the saved parts report to its local HTML and CSV outputs."""

    schema_version: Literal["1"] = "1"
    report_sha256: Digest
    artifacts_sha256: Mapping[RepositoryPath, Digest] = Field(min_length=1)


def read_parts_output_manifest(directory: Path, report_sha256: str) -> PartsOutputManifest | None:
    """Legacy receipts may lack a manifest; present ones must bind the report."""
    path = directory / "parts-artifacts.json"
    if path.is_symlink():
        raise ValueError("Parts artifact manifest must be a regular local file")
    if not path.exists():
        return None
    path = repo_path(directory, "parts-artifacts.json")
    manifest = read_model(path, PartsOutputManifest)
    if manifest.report_sha256 != report_sha256:
        raise ValueError("Parts artifact manifest does not bind the selected report")
    return manifest


def read_parts_receipt(
    root: Path, selected: Path, project_id: str
) -> tuple[Path, PurchasingReport, str]:
    """Require a saved plan, its own directory, and retained native netlist bytes."""
    root = root.resolve()
    try:
        relative = selected.relative_to(root) if selected.is_absolute() else selected
    except ValueError as exc:
        raise ValueError("Select a parts report under this checkout's build/") from exc
    path = artifact_path(root, relative.as_posix())
    report_path = path / "report.json" if path.is_dir() else path
    if report_path.name != "report.json" or not report_path.is_file():
        raise ValueError("Select a saved parts report.json or its receipt directory")
    raw, _ = read_regular_bytes(report_path, maximum=16 * 1024 * 1024)
    report = parse_model_text(raw.decode("utf-8"), PurchasingReport)
    report_hash = hashlib.sha256(raw).hexdigest()
    read_parts_output_manifest(report_path.parent, report_hash)
    if report.project_id != project_id or Path(report.receipt_dir) != report_path.parent:
        raise ValueError("Parts receipt belongs to another project or directory")
    if report.plan is None or not report.source_hashes or not report.input_hashes:
        raise ValueError("Parts receipt has no source-bound BOM plan")
    if (
        report.netlist_sha256 is None
        or digest(report_path.parent / "netlist.xml") != report.netlist_sha256
    ):
        raise ValueError("Parts receipt netlist is missing or changed")
    return report_path, report, report_hash
