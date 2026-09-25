"""Current-state metrics tests; historical tracking remains an external system."""
from __future__ import annotations

import json
import sys
import unittest
from datetime import date
from io import StringIO
from unittest.mock import patch

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


class TemplateMetricsTests(unittest.TestCase):
    def test_current_policy_metrics_are_non_authorizing(self) -> None:
        report = collect(ROOT, today=date(2026, 9, 7))
        self.assertTrue(all(metric.status == "PASS" for metric in report.checks))
        self.assertEqual(report.stale_evidence, 0)
        self.assertFalse(report.build_authorized)

    def test_deviation_metrics_preserve_status_and_expiry_counts(self) -> None:
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
        self.assertEqual((report.total, report.approved, report.open, report.expired), (2, 1, 1, 1))

    def test_cli_defaults_to_json_and_text_summarizes_current_findings(self) -> None:
        report = TemplateMetricsReport(
            checks=(
                CheckMetric(name="registry", status="PASS", findings=0),
                CheckMetric(name="repository", status="FAIL", findings=2),
            ),
            stale_evidence=1,
            deviations=DeviationMetrics(total=2, approved=1, open=1, closed=0, expired=1),
        )
        with (
            patch.object(sys, "argv", ["metrics.py"]),
            patch("kicad_tooling.metrics.collect", return_value=report),
            patch("sys.stdout", new_callable=StringIO) as output,
        ):
            self.assertEqual(metrics_main(), 0)
        self.assertEqual(json.loads(output.getvalue())["checks"][1]["findings"], 2)

        with (
            patch.object(sys, "argv", ["metrics.py", "--format", "text"]),
            patch("kicad_tooling.metrics.collect", return_value=report),
            patch("sys.stdout", new_callable=StringIO) as output,
        ):
            self.assertEqual(metrics_main(), 0)
        self.assertIn("Template metrics: 1/2 checks pass", output.getvalue())
        self.assertIn("repository: FAIL (2 findings)", output.getvalue())
        self.assertIn("Stale evidence: 1", output.getvalue())
        self.assertIn("Deviations: 2 total; 1 open, 1 approved", output.getvalue())
        self.assertIn("Next: run python -B -m kicad_tooling.ci", output.getvalue())
        self.assertIn("Build authorized: no", output.getvalue())


if __name__ == "__main__":
    unittest.main()
