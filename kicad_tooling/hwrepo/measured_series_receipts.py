"""Shared validation for explicitly selected measured-series receipts."""

from __future__ import annotations

from pathlib import Path

from .contracts import repo_path
from .evidence import digest
from .measured_series_models import MeasuredSeriesReport
from .review_overview_evidence import read_receipt, recorded_directory, selected_receipt

RETAINED_MEASUREMENT_ARTIFACTS = ("source.csv", "data.csv", "plot.svg", "plot.png")


def read_measured_receipt(
    root: Path, project_id: str, selected: Path
) -> tuple[Path, MeasuredSeriesReport, str]:
    path = selected_receipt(root, selected, "measured-series.json")
    report, checksum = read_receipt(path, MeasuredSeriesReport)
    if report.project_id != project_id or not recorded_directory(
        root, report.output_directory, path.parent
    ):
        raise ValueError("Measured receipt identifies a different project or output directory")
    return path, report, checksum


def measured_artifact_issues(path: Path, report: MeasuredSeriesReport) -> tuple[str, ...]:
    issues: list[str] = []
    for name in RETAINED_MEASUREMENT_ARTIFACTS:
        expected = report.artifacts_sha256.get(name)
        try:
            selected = repo_path(path.parent, name)
            current = digest(selected) if selected.is_file() else None
        except (OSError, ValueError):
            current = None
        if expected is None or current != expected:
            issues.append(f"Retained measurement artifact is missing or changed: {name}")
    if report.artifacts_sha256.get("source.csv") != report.source_sha256:
        issues.append("Retained source CSV hash differs from the measured receipt source hash.")
    return tuple(issues)
