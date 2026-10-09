"""Current-state metrics tests; historical tracking remains an external system."""

from __future__ import annotations

import json
import sys
from datetime import date

import pytest

from kicad_tooling.hwrepo.metrics import collect, deviation_metrics
from kicad_tooling.hwrepo.models import (
    CheckMetric,
    DeviationMetrics,
    DeviationStatus,
    ReleaseDeviation,
    TemplateMetricsReport,
)
from kicad_tooling.metrics import main as metrics_main
from tests.support import reference_root

ROOT = reference_root()


def sample_metrics_report() -> TemplateMetricsReport:
    return TemplateMetricsReport(
        checks=(
            CheckMetric(name="registry", status="PASS", findings=0),
            CheckMetric(name="repository", status="FAIL", findings=2),
        ),
        stale_evidence=1,
        deviations=DeviationMetrics(total=2, approved=1, open=1, closed=0, expired=1),
    )


def test_current_policy_metrics_are_non_authorizing() -> None:
    report = collect(ROOT, today=date(2026, 9, 7))
    assert all(metric.status == "PASS" for metric in report.checks)
    assert report.stale_evidence == 0
    assert not report.build_authorized


def test_deviation_metrics_preserve_status_and_expiry_counts() -> None:
    values = (
        ReleaseDeviation(
            id="DV-APPROVED",
            scope=("status-indicator-system",),
            owner="Configuration manager",
            reason="Test-only approved deviation.",
            status=DeviationStatus.APPROVED,
            expires=date(2026, 9, 8),
            evidence=("EV-1",),
        ),
        ReleaseDeviation(
            id="DV-EXPIRED",
            scope=("status-indicator-system",),
            owner="Configuration manager",
            reason="Test-only open deviation.",
            status=DeviationStatus.OPEN,
            expires=date(2026, 9, 6),
            evidence=("EV-2",),
        ),
    )
    report = deviation_metrics(values, today=date(2026, 9, 7))
    assert (report.total, report.approved, report.open, report.expired) == (2, 1, 1, 1)


def test_cli_defaults_to_json(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    report = sample_metrics_report()
    monkeypatch.setattr(sys, "argv", ["metrics.py"])
    monkeypatch.setattr("kicad_tooling.metrics.collect", lambda *_args: report)

    assert metrics_main() == 0
    assert json.loads(capsys.readouterr().out)["checks"][1]["findings"] == 2


def test_cli_text_summarizes_current_findings(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(sys, "argv", ["metrics.py", "--format", "text"])
    monkeypatch.setattr("kicad_tooling.metrics.collect", lambda *_args: sample_metrics_report())

    assert metrics_main() == 0
    output = capsys.readouterr().out
    assert "Template metrics: 1/2 checks pass" in output
    assert "repository: FAIL (2 findings)" in output
    assert "Stale evidence: 1" in output
    assert "Deviations: 2 total; 1 open, 1 approved" in output
    assert "Next: run python -B -m kicad_tooling.ci" in output
    assert "Build authorized: no" in output
