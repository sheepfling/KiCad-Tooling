"""Regression tests for pytest metrics retained by the CI driver."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from kicad_tooling.pytest_metrics import pytest_metrics, report_pytest_metrics
from scripts import ci

pytestmark = [pytest.mark.design_lint, pytest.mark.rule_gate_integrity]


def test_pytest_metrics_parse_outcomes_elapsed_time_and_slowest_tests() -> None:
    output = """
============================= slowest 10 durations =============================
41.84s call tests/test_power.py::test_budget
0.03s setup tests/test_small.py::test_case
=========================== short test summary info ============================
357 passed, 4 skipped, 7979 deselected in 129.87s (0:02:09)
"""

    metrics = pytest_metrics(output)

    assert metrics == {
        "summary_available": True,
        "summary_line": "357 passed, 4 skipped, 7979 deselected in 129.87s (0:02:09)",
        "pytest_elapsed_seconds": 129.87,
        "counts": {"passed": 357, "skipped": 4, "deselected": 7979},
        "duration_section_available": True,
        "slowest": [
            {
                "seconds": 41.84,
                "phase": "call",
                "nodeid": "tests/test_power.py::test_budget",
            },
            {
                "seconds": 0.03,
                "phase": "setup",
                "nodeid": "tests/test_small.py::test_case",
            },
        ],
    }


@pytest.mark.parametrize(
    ("summary", "expected"),
    [
        ("2 failed, 1 error in 0.50s", {"failed": 2, "errors": 1}),
        ("1 xfailed, 1 xpassed, 2 warnings in 0.25s", {"xfailed": 1, "xpassed": 1, "warnings": 2}),
        ("no tests ran in 0.01s", {}),
    ],
)
def test_pytest_metrics_parse_other_outcomes(summary: str, expected: dict[str, int]) -> None:
    metrics = pytest_metrics(summary)

    assert metrics["summary_available"] is True
    assert metrics["counts"] == expected


def test_pytest_metrics_reports_missing_summary_without_fabricating_counts() -> None:
    metrics = pytest_metrics("pytest output without a recognized summary")

    assert metrics["summary_available"] is False
    assert metrics["counts"] == {}
    assert metrics["pytest_elapsed_seconds"] is None
    assert metrics["slowest"] == []


def test_pytest_metrics_limits_duration_samples_and_rejects_negative_limit() -> None:
    output = """============================= slowest 10 durations =============================
0.30s call tests/test_a.py::test_a
0.20s call tests/test_b.py::test_b
0.10s call tests/test_c.py::test_c
"""

    assert len(pytest_metrics(output, slowest_limit=2)["slowest"]) == 2
    assert pytest_metrics(output, slowest_limit=0)["slowest"] == []
    with pytest.raises(ValueError, match="must not be negative"):
        pytest_metrics(output, slowest_limit=-1)


def test_unit_stage_adds_pytest_metrics_to_event_and_prints_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    stdout = """============================= slowest 10 durations =============================
2.50s call tests/test_power.py::test_budget
=========================== short test summary info ============================
3 passed, 1 deselected in 3.00s
"""
    monkeypatch.setattr(
        ci.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess("pytest", 0, stdout, ""),
    )
    event_path = tmp_path / "events.jsonl"

    ci.stage("unit", ("python", "-m", "pytest"), tmp_path, cwd=tmp_path)

    event = json.loads(event_path.read_text(encoding="utf-8"))
    assert event["pytest_metrics"]["counts"] == {"passed": 3, "deselected": 1}
    assert event["pytest_metrics"]["slowest"][0]["nodeid"] == "tests/test_power.py::test_budget"
    logged = capsys.readouterr().out
    assert "unit pytest 3 passed, 1 deselected; pytest elapsed 3.00s" in logged
    assert "unit slowest 2.50s call tests/test_power.py::test_budget" in logged


def test_report_pytest_metrics_marks_unrecognized_output_on_event(
    capsys: pytest.CaptureFixture[str],
) -> None:
    event: dict[str, object] = {}

    event["pytest_metrics"] = report_pytest_metrics("unrecognized output")

    assert event["pytest_metrics"] == pytest_metrics("unrecognized output")
    assert "metrics unavailable" in capsys.readouterr().out
