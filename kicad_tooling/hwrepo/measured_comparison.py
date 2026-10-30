"""Compare two saved measured traces with explicit time alignment and units."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Literal
from uuid import uuid4

from .artifact_access import read_regular_bytes
from .contract_coach import receipt_directory
from .contracts import write_model
from .evidence import digest
from .measured_comparison_html import display_indices, render_measured_comparison
from .measured_comparison_models import MeasuredComparisonReport, MeasuredRunIdentity
from .measured_series import MAX_SOURCE_BYTES, parse_measured_samples
from .measured_series_models import MeasuredSeriesReport
from .measured_series_receipts import measured_artifact_issues, read_measured_receipt
from .project_source_access import project_owned_source_path


@dataclass(frozen=True, slots=True)
class MeasuredRun:
    path: Path
    report: MeasuredSeriesReport
    identity: MeasuredRunIdentity
    source_bytes: bytes
    times: tuple[Decimal, ...]
    values: tuple[Decimal, ...]


def _source_state(
    root: Path, project_id: str, source: str, expected: str
) -> tuple[Literal["CURRENT", "CHANGED", "MISSING", "UNAVAILABLE"], str | None]:
    try:
        path, _ = project_owned_source_path(
            root, project_id, Path(source), ".csv", require_existing=False
        )
    except (OSError, ValueError):
        return "UNAVAILABLE", None
    if not path.exists():
        return "MISSING", None
    try:
        current, _ = read_regular_bytes(path, maximum=MAX_SOURCE_BYTES)
    except (OSError, ValueError):
        return "UNAVAILABLE", None
    checksum = hashlib.sha256(current).hexdigest()
    return ("CURRENT" if checksum == expected else "CHANGED"), checksum


def _read_run(root: Path, project_id: str, selected: Path, channel: str) -> MeasuredRun:
    path, report, report_sha = read_measured_receipt(root, project_id, selected)
    if report.status != "PASS":
        raise ValueError("Selected measured receipt did not pass import")
    issues = measured_artifact_issues(path, report)
    if issues:
        raise ValueError("Selected measured receipt has changed artifacts: " + "; ".join(issues))
    matches = [item for item in report.channels if item.column == channel]
    if len(matches) != 1:
        raise ValueError(f"Selected channel is absent or ambiguous: {channel}")
    raw, _ = read_regular_bytes(path.parent / "source.csv", maximum=MAX_SOURCE_BYTES)
    times, groups = parse_measured_samples(
        raw, report.time_column, report.time_unit, report.channels
    )
    if len(times) != report.samples:
        raise ValueError("Measured receipt sample count differs from retained source")
    index = report.channels.index(matches[0])
    state, observed = _source_state(root, project_id, report.source, report.source_sha256)
    identity = MeasuredRunIdentity(
        receipt=path.relative_to(root).as_posix(),
        receipt_sha256=report_sha,
        source=report.source,
        source_sha256=report.source_sha256,
        source_state=state,
        observed_source_sha256=observed,
        channel=channel,
        unit=matches[0].unit,
        samples=len(times),
        first_time_seconds=str(times[0]),
        last_time_seconds=str(times[-1]),
    )
    return MeasuredRun(path, report, identity, raw, times, groups[index])


def compare_measured_series(
    root: Path,
    project_id: str,
    baseline: Path,
    candidate: Path,
    channel: str,
    alignment: Literal["absolute", "elapsed"],
    output: Path | None = None,
) -> MeasuredComparisonReport:
    """Overlay two selected traces without interpolation or inferred acceptance limits."""
    if alignment not in {"absolute", "elapsed"}:
        raise ValueError("Select absolute or elapsed time alignment")
    root = root.resolve()
    first = _read_run(root, project_id, baseline, channel)
    second = _read_run(root, project_id, candidate, channel)
    if first.path == second.path:
        raise ValueError("Select two distinct measured receipts")
    if first.identity.unit != second.identity.unit:
        raise ValueError("Selected channels have different units")
    before_times = (
        tuple(value - first.times[0] for value in first.times)
        if alignment == "elapsed"
        else first.times
    )
    after_times = (
        tuple(value - second.times[0] for value in second.times)
        if alignment == "elapsed"
        else second.times
    )
    overlap = (
        "OVERLAP"
        if max(before_times[0], after_times[0]) < min(before_times[-1], after_times[-1])
        else "DISJOINT"
    )
    before_indices = display_indices(first.values)
    after_indices = display_indices(second.values)
    if (
        _read_run(root, project_id, baseline, channel) != first
        or _read_run(root, project_id, candidate, channel) != second
    ):
        raise ValueError("Selected measured evidence changed during comparison")
    directory = receipt_directory(
        root,
        project_id,
        output or Path("build/measured-comparison") / f"{project_id}-{uuid4().hex[:12]}",
    )
    (directory / "baseline-source.csv").write_bytes(first.source_bytes)
    (directory / "candidate-source.csv").write_bytes(second.source_bytes)
    report = MeasuredComparisonReport(
        project_id=project_id,
        alignment=alignment,
        channel=channel,
        unit=first.identity.unit,
        baseline=first.identity,
        candidate=second.identity,
        source_status="CURRENT"
        if first.identity.source_state == second.identity.source_state == "CURRENT"
        else "HISTORICAL",
        overlap=overlap,
        display_points_baseline=len(before_indices),
        display_points_candidate=len(after_indices),
        output_directory=str(directory),
    )
    (directory / "index.html").write_text(
        render_measured_comparison(
            report,
            before_times,
            first.values,
            before_indices,
            after_times,
            second.values,
            after_indices,
        ),
        encoding="utf-8",
    )
    if (
        _read_run(root, project_id, baseline, channel) != first
        or _read_run(root, project_id, candidate, channel) != second
    ):
        raise ValueError("Selected measured evidence changed during comparison")
    report = report.model_copy(
        update={
            "artifacts_sha256": {
                "baseline-source.csv": digest(directory / "baseline-source.csv"),
                "candidate-source.csv": digest(directory / "candidate-source.csv"),
                "index.html": digest(directory / "index.html"),
            }
        }
    )
    write_model(directory / "comparison.json", report)
    return report
