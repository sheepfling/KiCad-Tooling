"""Import bounded project-owned measurement CSV into a source-bound plot receipt."""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import io
import math
import re
import textwrap
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path
from typing import Literal
from uuid import uuid4

from .artifact_access import read_regular_bytes
from .contract_coach import receipt_directory
from .contracts import write_model
from .measured_series_models import MeasuredChannel, MeasuredSeriesReport
from .project_source_access import project_owned_source_path

MAX_SOURCE_BYTES = 8 * 1024 * 1024
MAX_SAMPLES = 100_000
MAX_CHANNELS = 8
MAX_FIELD_CHARS = 256
_TIME_SCALE = {
    "s": Decimal(1),
    "ms": Decimal("0.001"),
    "us": Decimal("0.000001"),
    "ns": Decimal("0.000000001"),
}


def parse_channel_mappings(values: tuple[str, ...]) -> tuple[MeasuredChannel, ...]:
    """Parse the identical column=unit contract used by CLI and MCP."""
    if not 1 <= len(values) <= MAX_CHANNELS:
        raise ValueError(f"Select 1 to {MAX_CHANNELS} channel=unit mappings")
    channels: list[MeasuredChannel] = []
    for value in values:
        if "=" not in value:
            raise ValueError(f"Expected channel=unit mapping: {value!r}")
        column, unit = value.split("=", 1)
        if (
            not column
            or column != column.strip()
            or len(column) > 80
            or not unit
            or unit != unit.strip()
            or len(unit) > 32
            or any(ord(char) < 32 or ord(char) == 127 for char in column + unit)
        ):
            raise ValueError(f"Invalid channel=unit mapping: {value!r}")
        channels.append(MeasuredChannel(column=column, unit=unit))
    names = [channel.column for channel in channels]
    if len(set(names)) != len(names):
        raise ValueError("Channel columns must be unique")
    return tuple(channels)


def _timestamp(value: str, unit: str, row: int) -> Decimal:
    if unit != "iso8601":
        try:
            with localcontext() as context:
                context.prec = max(28, len(value) + 12)
                result = Decimal(value) * _TIME_SCALE[unit]
        except (InvalidOperation, KeyError) as exc:
            raise ValueError(f"CSV row {row}: invalid numeric time {value!r}") from exc
        if not result.is_finite():
            raise ValueError(f"CSV row {row}: time is non-finite")
        return result
    try:
        moment = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"CSV row {row}: invalid ISO 8601 timestamp {value!r}") from exc
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError(f"CSV row {row}: ISO 8601 timestamp needs a UTC offset")
    delta = moment.astimezone(UTC) - datetime(1970, 1, 1, tzinfo=UTC)
    fraction = re.search(r"[T ]\d{2}:\d{2}:\d{2}[.,](\d+)", value)
    with localcontext() as context:
        context.prec = max(28, len(value) + 12)
        remainder = (
            Decimal(f"0.{fraction.group(1)}") - Decimal(moment.microsecond) / 1_000_000
            if fraction is not None
            else Decimal(0)
        )
        return (
            Decimal(delta.days * 86400 + delta.seconds)
            + Decimal(delta.microseconds) / 1_000_000
            + remainder
        )


def parse_measured_samples(
    raw: bytes, time_column: str, time_unit: str, channels: tuple[MeasuredChannel, ...]
) -> tuple[tuple[Decimal, ...], tuple[tuple[Decimal, ...], ...]]:
    try:
        text = raw.decode("utf-8-sig", errors="strict")
    except UnicodeDecodeError as exc:
        raise ValueError("Measurement CSV must be UTF-8") from exc
    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    try:
        header = next(reader)
    except StopIteration as exc:
        raise ValueError("Measurement CSV is empty") from exc
    except csv.Error as exc:
        raise ValueError(f"CSV header is malformed: {exc}") from exc
    if len(header) != len(set(header)) or any(
        not item or item != item.strip() or len(item) > MAX_FIELD_CHARS for item in header
    ):
        raise ValueError("CSV header has duplicate, blank, or padded columns")
    requested = (time_column, *(channel.column for channel in channels))
    if len(set(requested)) != len(requested):
        raise ValueError("Time and channel columns must be distinct")
    absent = [name for name in requested if name not in header]
    if absent:
        raise ValueError(f"CSV columns not found: {absent}")
    indexes = [header.index(name) for name in requested]
    times: list[Decimal] = []
    values: list[list[Decimal]] = [[] for _ in channels]
    try:
        for row in reader:
            number = reader.line_num
            if len(times) >= MAX_SAMPLES:
                raise ValueError(f"Measurement CSV exceeds {MAX_SAMPLES} samples")
            if not row:
                raise ValueError(f"CSV row {number}: blank sample row")
            if len(row) != len(header):
                raise ValueError(
                    f"CSV row {number}: expected {len(header)} columns, found {len(row)}"
                )
            if any(len(item) > MAX_FIELD_CHARS for item in row):
                raise ValueError(f"CSV row {number}: field exceeds {MAX_FIELD_CHARS} characters")
            time_value = _timestamp(row[indexes[0]], time_unit, number)
            if times and time_value <= times[-1]:
                raise ValueError(f"CSV row {number}: time must be strictly increasing")
            times.append(time_value)
            for channel, index, destination in zip(channels, indexes[1:], values, strict=True):
                try:
                    sample = Decimal(row[index])
                except InvalidOperation as exc:
                    raise ValueError(
                        f"CSV row {number}: invalid {channel.column} sample {row[index]!r}"
                    ) from exc
                if not sample.is_finite():
                    raise ValueError(f"CSV row {number}: non-finite {channel.column} sample")
                destination.append(sample)
    except csv.Error as exc:
        raise ValueError(f"CSV row {reader.line_num}: malformed CSV: {exc}") from exc
    if len(times) < 2:
        raise ValueError("Measurement CSV needs at least two samples")
    return tuple(times), tuple(tuple(group) for group in values)


# Existing internal tests and callers use the original parser name.
_samples = parse_measured_samples


def _plot(
    directory: Path,
    times: tuple[Decimal, ...],
    values: tuple[tuple[Decimal, ...], ...],
    channels: tuple[MeasuredChannel, ...],
    source: str,
    source_sha256: str,
    time_unit: str,
) -> None:
    if importlib.util.find_spec("matplotlib") is None:
        raise ValueError("Install chart support with python -m pip install -e '.[charts]'")
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib import pyplot as plt

    matplotlib.rcParams["svg.hashsalt"] = "kicad-measured-series"

    with localcontext() as context:
        context.prec = max(28, max(len(value.as_tuple().digits) for value in times) + 12)
        elapsed = [float(value - times[0]) for value in times]
    if any(not math.isfinite(value) for value in elapsed) or any(
        not (elapsed[index] > elapsed[index - 1]) for index in range(1, len(elapsed))
    ):
        raise ValueError(
            "Time separation is too small for a floating-point plot; data remains in source.csv"
        )
    units = tuple(dict.fromkeys(channel.unit for channel in channels))
    figure, axes = plt.subplots(
        len(units), 1, figsize=(11, max(3, 2.5 * len(units))), sharex=True, squeeze=False
    )
    try:
        for unit, axis in zip(units, axes[:, 0], strict=True):
            for channel, series in zip(channels, values, strict=True):
                if channel.unit == unit:
                    axis.plot(
                        elapsed,
                        [float(value) for value in series],
                        label=channel.column,
                        linewidth=1.2,
                    )
            axis.set_ylabel(unit)
            axis.grid(alpha=0.25)
            axis.legend(loc="best")
        axes[-1, 0].set_xlabel("Elapsed time (s)")
        figure.suptitle("Imported time series")  # pyright: ignore[reportUnknownMemberType]
        figure.text(  # pyright: ignore[reportUnknownMemberType]
            0.01,
            0.01,
            f"Source: {textwrap.shorten(source, width=95, placeholder='…')}  "
            f"SHA-256: {source_sha256[:12]}…  Input time: {time_unit}",
            fontsize=8,
        )
        figure.tight_layout(rect=(0, 0.06, 1, 0.95))
        figure.savefig(directory / "plot.png", dpi=140)  # pyright: ignore[reportUnknownMemberType]
        figure.savefig(  # pyright: ignore[reportUnknownMemberType]
            directory / "plot.svg", metadata={"Date": None}
        )
    finally:
        plt.close(figure)


def import_measured_series(
    root: Path,
    project_id: str,
    source: Path,
    time_column: str,
    time_unit: Literal["s", "ms", "us", "ns", "iso8601"],
    channel_mappings: tuple[str, ...],
    output: Path | None = None,
) -> MeasuredSeriesReport:
    """Keep original bytes, full-precision normalized values, and reviewable failures."""
    root = root.resolve()
    if time_unit not in {*_TIME_SCALE, "iso8601"}:
        raise ValueError("Time unit must be s, ms, us, ns, or iso8601")
    if not time_column or time_column != time_column.strip() or len(time_column) > 80:
        raise ValueError("Select one exact time column")
    channels = parse_channel_mappings(channel_mappings)
    source_path, source_name = project_owned_source_path(root, project_id, source, ".csv")
    raw, _ = read_regular_bytes(source_path, maximum=MAX_SOURCE_BYTES)
    source_hash = hashlib.sha256(raw).hexdigest()
    destination = receipt_directory(
        root,
        project_id,
        output or Path("build/measured-series") / f"{project_id}-{uuid4().hex[:12]}",
    )
    (destination / "source.csv").write_bytes(raw)
    artifacts = {"source.csv": source_hash}
    errors: list[str] = []
    samples = 0
    try:
        times, values = parse_measured_samples(raw, time_column, time_unit, channels)
        samples = len(times)
        with (destination / "data.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(
                [
                    "time_utc_seconds" if time_unit == "iso8601" else "time_seconds",
                    *(channel.column for channel in channels),
                ]
            )
            for index, value in enumerate(times):
                writer.writerow([str(value), *(str(group[index]) for group in values)])
        _plot(destination, times, values, channels, source_name, source_hash, time_unit)
    except (OSError, ValueError, OverflowError) as exc:
        errors.append(str(exc))
    for name in ("data.csv", "plot.png", "plot.svg"):
        if (destination / name).is_file():
            artifacts[name] = hashlib.sha256((destination / name).read_bytes()).hexdigest()
    try:
        current, _ = read_regular_bytes(source_path, maximum=MAX_SOURCE_BYTES)
        if hashlib.sha256(current).hexdigest() != source_hash:
            errors.append("Source CSV changed during import")
    except (OSError, ValueError):
        errors.append("Source CSV could not be rechecked after import")
    report = MeasuredSeriesReport(
        status="FAIL" if errors else "PASS",
        project_id=project_id,
        source=source_name,
        source_sha256=source_hash,
        time_column=time_column,
        time_unit=time_unit,
        channels=channels,
        samples=samples,
        output_directory=str(destination),
        errors=tuple(errors),
        artifacts_sha256=artifacts,
    )
    write_model(destination / "measured-series.json", report)
    return report
