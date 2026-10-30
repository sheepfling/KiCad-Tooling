"""Bounded measured CSV import and source-bound data receipts."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.contracts import read_model
from kicad_tooling.hwrepo.measured_series import (
    MAX_SOURCE_BYTES,
    _samples,
    import_measured_series,
    parse_channel_mappings,
)
from kicad_tooling.hwrepo.measured_series_models import MeasuredSeriesReport
from tests.mcp_parity_support import parity_workspace


def test_exact_numeric_time_and_channel_precision() -> None:
    channels = parse_channel_mappings(("voltage=V", "current=mA"))
    times, values = _samples(
        b"t,voltage,current\n1000.000000000000000000000001,1.2345678901234567890123456789,2\n"
        b"1000.000000000000000000000002,1.2345678901234567890123456790,3\n",
        "t",
        "ms",
        channels,
    )
    assert str(times[1] - times[0]) == "1E-27"
    assert str(values[0][0]) == "1.2345678901234567890123456789"
    assert channels[1].unit == "mA"


def test_iso_timestamps_require_offsets_and_preserve_subseconds() -> None:
    channel = parse_channel_mappings(("temperature=°C",))
    times, _ = _samples(
        b"when,temperature\n2026-01-01T00:00:00.000001Z,20\n2025-12-31T18:00:00.000002-06:00,21\n",
        "when",
        "iso8601",
        channel,
    )
    assert times[1] - times[0] == Decimal("0.000001")
    nanoseconds, _ = _samples(
        b"when,temperature\n2026-01-01T00:00:00.000000001Z,20\n2026-01-01T00:00:00.000000002Z,21\n",
        "when",
        "iso8601",
        channel,
    )
    assert nanoseconds[1] - nanoseconds[0] == Decimal("0.000000001")
    with pytest.raises(ValueError, match="UTC offset"):
        _samples(
            b"when,temperature\n2026-01-01T00:00:00,20\n2026-01-01T00:00:01,21\n",
            "when",
            "iso8601",
            channel,
        )


def test_sample_count_and_mapping_bounds() -> None:
    with pytest.raises(ValueError, match="100000 samples"):
        _samples(
            b"t,v\n" + b"".join(f"{index},1\n".encode() for index in range(100_001)),
            "t",
            "s",
            parse_channel_mappings(("v=V",)),
        )
    with pytest.raises(ValueError, match="unique"):
        parse_channel_mappings(("v=V", "v=mV"))


@pytest.mark.parametrize(
    ("document", "message"),
    [
        (b"t,v\n0,1\n0,2\n", "strictly increasing"),
        (b"t,v\n0,1\n1,NaN\n", "non-finite"),
        (b"t,v\n0,1\n1,\n", "invalid v sample"),
        (b"t,v\n0,1\n1\n", "expected 2 columns"),
        (b"t,v,v\n0,1,2\n1,2,3\n", "duplicate"),
        (b"t,v\n0,1\n\n1,2\n", "blank sample"),
    ],
)
def test_invalid_samples_are_specific(document: bytes, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        _samples(document, "t", "s", parse_channel_mappings(("v=V",)))


@pytest.mark.template_checkout
def test_receipt_retains_source_mapping_and_failure(tmp_path: Path) -> None:
    root, island, _ = parity_workspace(tmp_path)
    source = island / "docs/measurement.csv"
    source.write_text(
        "time,voltage\n0,1.0000000000000000000001\n0.5,1.0000000000000000000002\n", encoding="utf-8"
    )
    report = import_measured_series(
        root,
        "controller",
        source,
        "time",
        "s",
        ("voltage=V",),
        Path("build/measured-series/valid"),
    )
    directory = Path(report.output_directory)
    assert report.status == "PASS" and report.samples == 2
    assert (directory / "source.csv").read_bytes() == source.read_bytes()
    assert "1.0000000000000000000002" in (directory / "data.csv").read_text(encoding="utf-8")
    assert (directory / "plot.png").is_file() and (directory / "plot.svg").is_file()
    assert read_model(directory / "measured-series.json", MeasuredSeriesReport) == report
    source.write_text("time,voltage\n0,1\n0,2\n", encoding="utf-8")
    failed = import_measured_series(
        root,
        "controller",
        source,
        "time",
        "s",
        ("voltage=V",),
        Path("build/measured-series/invalid"),
    )
    assert failed.status == "FAIL" and "strictly increasing" in failed.errors[0]
    assert set(failed.artifacts_sha256) == {"source.csv"}
    assert (
        read_model(Path(failed.output_directory) / "measured-series.json", MeasuredSeriesReport)
        == failed
    )


@pytest.mark.template_checkout
def test_bounds_and_source_scope_precede_receipt(tmp_path: Path) -> None:
    root, island, _ = parity_workspace(tmp_path)
    source = island / "docs/large.csv"
    with source.open("wb") as stream:
        stream.truncate(MAX_SOURCE_BYTES + 1)
    with pytest.raises(ValueError, match="byte limit"):
        import_measured_series(root, "controller", source, "t", "s", ("v=V",))
    outside = root / "outside.csv"
    outside.write_text("t,v\n0,1\n1,2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="project island"):
        import_measured_series(root, "controller", outside, "t", "s", ("v=V",))
    assert not (root / "build/measured-series").exists()
