"""Interactive simulation charts and exact saved AC comparison evidence."""

from __future__ import annotations

import asyncio
import json
import re
import shutil
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Literal, TypedDict
from unittest.mock import patch

import pytest
from mcp import Client

from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.electrical_ac_comparison import compare_ac_runs
from kicad_tooling.hwrepo.electrical_chart_interactive import (
    InteractiveTrace,
    display_indices,
)
from kicad_tooling.hwrepo.electrical_chart_interactive import (
    render_interactive_chart as original_chart,
)
from kicad_tooling.hwrepo.electrical_chart_models import AcComparisonReport
from kicad_tooling.hwrepo.electrical_charts import build_charts
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import ElectricalAnalysisReport

pytestmark = [pytest.mark.template_checkout]


class InteractivePlotTrace(TypedDict):
    id: str
    label: str
    unit: str
    x: list[float]
    y: list[float]
    phase_deg: list[float] | None
    window_start: float
    window_stop: float
    statistic: str
    minimum: float | None
    maximum: float | None


class InteractivePlotData(TypedDict):
    axis: Literal["time", "frequency"]
    traces: list[InteractivePlotTrace]


@pytest.fixture
def saved_runs() -> Iterator[tuple[Path, Path, Path]]:
    from tests.test_electrical_charts import ElectricalChartsTests

    fixture = ElectricalChartsTests()
    fixture.setUp()
    fixture.complete()
    first = fixture.source
    second = first.with_name("controller-candidate")
    shutil.copytree(first, second)
    report = read_model(second / "electrical.json", ElectricalAnalysisReport)
    write_model(
        second / "electrical.json", report.model_copy(update={"run_directory": str(second)})
    )
    try:
        yield fixture.root, first, second
    finally:
        fixture.doCleanups()


def _retag_artifact(receipt: Path, name: str) -> None:
    report = read_model(receipt / "electrical.json", ElectricalAnalysisReport)
    hashes = dict(report.artifacts_sha256)
    hashes[name] = digest(receipt / name)
    write_model(receipt / "electrical.json", report.model_copy(update={"artifacts_sha256": hashes}))


def _data_from_html(page: str) -> InteractivePlotData:
    match = re.search(r'<script type="application/json" id="plot-data">(.*?)</script>', page)
    assert match is not None
    return json.loads(match.group(1))


def test_interactive_time_and_ac_views_retain_full_exports(
    saved_runs: tuple[Path, Path, Path],
) -> None:
    root, first, _ = saved_runs
    report = build_charts(root, first)
    directory = Path(report.run_directory)
    assert report.viewer_index == "index.html"
    assert (directory / "index.html").is_file()
    assert report.artifacts_sha256["index.html"] == digest(directory / "index.html")
    for case in report.cases:
        html_name = case.html
        csv_name = case.csv
        assert html_name is not None and html_name == f"{case.id}.html"
        assert csv_name is not None
        assert report.artifacts_sha256[html_name] == digest(directory / html_name)
        assert (directory / csv_name).is_file()
    transient = _data_from_html((directory / "steady-state.html").read_text())
    ac = _data_from_html((directory / "passband.html").read_text())
    assert transient["axis"] == "time"
    assert {trace["unit"] for trace in transient["traces"]} == {"A", "W", "V"}
    assert ac["axis"] == "frequency"
    phase = ac["traces"][0]["phase_deg"]
    assert phase is not None
    assert phase[-1] == pytest.approx(-45)
    html = (directory / "passband.html").read_text()
    assert "Reset zoom" in html and "ArrowRight" in html and "Full CSV" in html
    assert "<script src=" not in html and "https://" not in html


def test_display_limit_keeps_narrow_value_and_phase_extrema() -> None:
    axis = tuple(float(index + 1) for index in range(20_000))
    value = tuple(1000.0 if index == 7011 else 0.0 for index in range(len(axis)))
    phase = tuple(-120.0 if index == 12013 else 0.0 for index in range(len(axis)))
    indices = display_indices(axis, (value, phase))
    assert len(indices) <= 4000
    assert {0, 7011, 12013, len(axis) - 1} <= set(indices)


def test_ac_overlay_uses_exact_receipts_and_original_frequency_grids(
    saved_runs: tuple[Path, Path, Path],
) -> None:
    root, first, second = saved_runs
    raw = second / "passband/waveforms.raw"
    before = raw.read_text()
    changed = before.replace("-3,0\n", "-2,0\n").replace("1000000,0\n", "500000,0\n")
    assert changed != before
    raw.write_text(changed)
    _retag_artifact(second, "passband/waveforms.raw")
    report = compare_ac_runs(root, "controller", first, second, "passband", "gain")
    assert report.overlap == "OVERLAP"
    assert report.quantity_kind == "SCALAR"
    assert report.baseline.report_sha256 != report.candidate.report_sha256
    assert report.baseline.waveform_sha256 != report.candidate.waveform_sha256
    output = Path(report.output_directory)
    assert read_model(output / "comparison.json", AcComparisonReport) == report
    assert report.artifacts_sha256["index.html"] == digest(output / "index.html")
    assert report.artifacts_sha256["baseline.csv"] == digest(output / "baseline.csv")
    data = _data_from_html((output / "index.html").read_text())
    assert data["axis"] == "frequency"
    assert [trace["id"] for trace in data["traces"]] == ["baseline", "candidate"]
    assert data["traces"][0]["x"] != data["traces"][1]["x"]
    assert data["traces"][0]["y"] != data["traces"][1]["y"]
    assert "No interpolation" in (output / "index.html").read_text()


def test_ac_overlay_rejects_changed_evidence_and_incompatible_scope(
    saved_runs: tuple[Path, Path, Path],
) -> None:
    root, first, second = saved_runs
    with pytest.raises(ValueError, match="distinct"):
        compare_ac_runs(root, "controller", first, first, "passband", "gain")
    with pytest.raises(ValueError, match="another project"):
        compare_ac_runs(root, "unrelated", first, second, "passband", "gain")
    raw = second / "passband/waveforms.raw"
    raw.write_text(raw.read_text() + "\n")
    with pytest.raises(ValueError, match="changed or is missing"):
        compare_ac_runs(root, "controller", first, second, "passband", "gain")
    _retag_artifact(second, "passband/waveforms.raw")
    requirements = second / "requirements.json"
    content = requirements.read_text()
    changed = content.replace("db(v(out)/v(in))", "db(v(out))")
    assert changed != content
    requirements.write_text(changed)
    _retag_artifact(second, "requirements.json")
    with pytest.raises(ValueError, match="incompatible expressions"):
        compare_ac_runs(root, "controller", first, second, "passband", "gain")


def test_ac_overlay_rechecks_inputs_after_render(saved_runs: tuple[Path, Path, Path]) -> None:
    root, first, second = saved_runs
    raw = first / "passband/waveforms.raw"

    def mutate_after_render(
        title: str,
        axis: Literal["time", "frequency"],
        traces: tuple[InteractiveTrace, ...],
        evidence: tuple[tuple[str, str], ...],
        downloads: tuple[tuple[str, str], ...],
    ) -> str:
        page = original_chart(title, axis, traces, evidence, downloads)
        raw.write_text(raw.read_text() + "\n")
        return page

    with (
        patch(
            "kicad_tooling.hwrepo.electrical_ac_comparison.render_interactive_chart",
            side_effect=mutate_after_render,
        ),
        pytest.raises(ValueError, match="changed or is missing"),
    ):
        compare_ac_runs(root, "controller", first, second, "passband", "gain")


def test_cli_mcp_ac_comparison_parity(saved_runs: tuple[Path, Path, Path]) -> None:
    root, first, second = saved_runs
    process = subprocess.run(
        (
            sys.executable,
            "-I",
            "-m",
            "kicad_tooling.electrical_ac_comparison",
            "--root",
            str(root),
            "--project",
            "controller",
            "--baseline",
            str(first),
            "--candidate",
            str(second),
            "--case",
            "passband",
            "--measure",
            "gain",
            "--output",
            "build/electrical-ac-comparison/cli",
            "--format",
            "json",
        ),
        text=True,
        capture_output=True,
        check=False,
    )
    assert process.returncode == 0, process.stderr
    cli = AcComparisonReport.model_validate_json(process.stdout)

    async def call_mcp() -> AcComparisonReport:
        async with Client(create_server(root, allow_exports=True), mode="legacy") as client:
            response = await client.call_tool(
                "compare_electrical_ac_runs",
                {
                    "project_id": "controller",
                    "baseline": first.relative_to(root).as_posix(),
                    "candidate": second.relative_to(root).as_posix(),
                    "case_id": "passband",
                    "measure_id": "gain",
                    "view_id": "mcp",
                },
            )
            assert not response.is_error, response.content
            return AcComparisonReport.model_validate_json(json.dumps(response.structured_content))

    mcp = asyncio.run(call_mcp())
    assert cli.model_dump(exclude={"output_directory"}) == mcp.model_dump(
        exclude={"output_directory"}
    )
    assert (Path(cli.output_directory) / "index.html").read_bytes() == (
        Path(mcp.output_directory) / "index.html"
    ).read_bytes()
