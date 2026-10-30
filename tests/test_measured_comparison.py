"""Saved measured-run overlays, source integrity, alignment, and CLI/MCP parity."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from mcp import Client

from kicad_tooling.hwrepo.contracts import read_model
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.measured_comparison import compare_measured_series
from kicad_tooling.hwrepo.measured_comparison_html import display_indices
from kicad_tooling.hwrepo.measured_comparison_models import MeasuredComparisonReport
from kicad_tooling.hwrepo.measured_series import import_measured_series
from tests.mcp_parity_support import McpParityHarness, parity_workspace, run_mcp_parity

pytestmark = pytest.mark.template_checkout


def _runs(root: Path, island: Path, *, candidate_unit: str = "V") -> tuple[Path, Path]:
    first = island / "docs/baseline.csv"
    second = island / "docs/candidate.csv"
    first.write_text("t,v\n0,1.0000000000000000001\n1,2\n2,3\n", encoding="utf-8")
    second.write_text("t,v\n10,2\n11,4\n12,6\n", encoding="utf-8")
    baseline = import_measured_series(
        root,
        "controller",
        first,
        "t",
        "s",
        ("v=V",),
        Path("build/measured-series/baseline"),
    )
    candidate = import_measured_series(
        root,
        "controller",
        second,
        "t",
        "s",
        (f"v={candidate_unit}",),
        Path("build/measured-series/candidate"),
    )
    assert baseline.status == candidate.status == "PASS"
    return (
        Path(baseline.output_directory) / "measured-series.json",
        Path(candidate.output_directory) / "measured-series.json",
    )


def test_elapsed_and_absolute_alignment_preserve_full_sources(tmp_path: Path) -> None:
    root, island, _ = parity_workspace(tmp_path)
    baseline, candidate = _runs(root, island)
    elapsed = compare_measured_series(
        root,
        "controller",
        baseline,
        candidate,
        "v",
        "elapsed",
        Path("build/measured-comparison/elapsed"),
    )
    absolute = compare_measured_series(
        root,
        "controller",
        baseline,
        candidate,
        "v",
        "absolute",
        Path("build/measured-comparison/absolute"),
    )
    assert elapsed.overlap == "OVERLAP" and absolute.overlap == "DISJOINT"
    assert elapsed.source_status == "CURRENT" and elapsed.unit == "V"
    assert elapsed.display_points_baseline == elapsed.baseline.samples == 3
    assert elapsed.baseline.first_time_seconds == "0"
    assert elapsed.candidate.first_time_seconds == "10"
    directory = Path(elapsed.output_directory)
    assert (directory / "baseline-source.csv").read_bytes() == (
        island / "docs/baseline.csv"
    ).read_bytes()
    assert (directory / "candidate-source.csv").read_bytes() == (
        island / "docs/candidate.csv"
    ).read_bytes()
    assert all(digest(directory / name) == sha for name, sha in elapsed.artifacts_sha256.items())
    assert read_model(directory / "comparison.json", MeasuredComparisonReport) == elapsed
    html = (directory / "index.html").read_text(encoding="utf-8")
    assert 'id="baseline"' in html and 'id="candidate"' in html
    assert "Nearest displayed points" in html
    assert "does not interpolate" in html


def test_changed_source_is_historical_but_tampered_artifact_is_rejected(tmp_path: Path) -> None:
    root, island, _ = parity_workspace(tmp_path)
    baseline, candidate = _runs(root, island)
    (island / "docs/baseline.csv").write_text("t,v\n0,7\n1,8\n2,9\n", encoding="utf-8")
    report = compare_measured_series(root, "controller", baseline, candidate, "v", "elapsed")
    assert report.source_status == "HISTORICAL"
    assert report.baseline.source_state == "CHANGED"
    assert report.candidate.source_state == "CURRENT"
    assert (
        (Path(report.output_directory) / "baseline-source.csv")
        .read_text()
        .startswith("t,v\n0,1.0000000000000000001")
    )
    (island / "docs/baseline.csv").unlink()
    missing = compare_measured_series(root, "controller", baseline, candidate, "v", "elapsed")
    assert missing.baseline.source_state == "MISSING"
    (baseline.parent / "plot.svg").write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="changed artifacts"):
        compare_measured_series(root, "controller", baseline, candidate, "v", "elapsed")


def test_unit_and_receipt_scope_must_match(tmp_path: Path) -> None:
    root, island, _ = parity_workspace(tmp_path)
    baseline, candidate = _runs(root, island, candidate_unit="mV")
    with pytest.raises(ValueError, match="different units"):
        compare_measured_series(root, "controller", baseline, candidate, "v", "elapsed")
    with pytest.raises(ValueError, match="distinct"):
        compare_measured_series(root, "controller", baseline, baseline, "v", "elapsed")
    with pytest.raises(ValueError, match="absent or ambiguous"):
        compare_measured_series(root, "controller", baseline, candidate, "missing", "elapsed")


def test_display_reduction_keeps_a_narrow_extreme() -> None:
    values = tuple(Decimal(100) if index == 50_001 else Decimal(0) for index in range(100_000))
    selected = display_indices(values)
    assert len(selected) <= 4002
    assert selected[0] == 0 and selected[-1] == 99_999
    assert 50_001 in selected


class _MeasuredComparisonParity(McpParityHarness):
    async def _case_test_cli_mcp_measured_comparison_parity(self) -> None:
        baseline, candidate = _runs(self.root, self.island)
        cli = await self.cli(
            "kicad_tooling.measured_comparison",
            MeasuredComparisonReport,
            "--project",
            "controller",
            "--baseline",
            str(baseline),
            "--candidate",
            str(candidate),
            "--channel",
            "v",
            "--alignment",
            "elapsed",
            "--output",
            "build/measured-comparison/cli",
        )
        arguments = {
            "project_id": "controller",
            "baseline": baseline.relative_to(self.root).as_posix(),
            "candidate": candidate.relative_to(self.root).as_posix(),
            "channel": "v",
            "alignment": "elapsed",
            "view_id": "mcp",
        }
        async with Client(create_server(self.root), mode="legacy") as client:
            self.assertTrue((await client.call_tool("compare_measured_runs", arguments)).is_error)
        async with Client(create_server(self.root, allow_exports=True), mode="legacy") as client:
            mcp = await self.call(
                client, "compare_measured_runs", MeasuredComparisonReport, arguments
            )
        self.receipt_equal(cli, mcp, "output_directory")
        self.assertEqual(
            (Path(cli.output_directory) / "index.html").read_text(),
            (Path(mcp.output_directory) / "index.html").read_text(),
        )


def test_cli_mcp_measured_comparison_parity() -> None:
    run_mcp_parity(_MeasuredComparisonParity, "_case_test_cli_mcp_measured_comparison_parity")
