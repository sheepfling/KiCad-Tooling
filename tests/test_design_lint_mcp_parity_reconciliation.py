"""The CLI and MCP reconcile the same saved source-bound lint report."""

from __future__ import annotations

import pytest
from mcp import Client

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.evidence_lint,
    pytest.mark.parity_lint,
    pytest.mark.slow,
    pytest.mark.template_checkout,
]

from kicad_tooling.hwrepo.design_lint_reconciliation_models import (
    DesignLintReconciliationReport,
)
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.mcp_server import create_server
from tests.mcp_parity_support import McpParityHarness, run_mcp_parity


class _DesignLintReconciliationParityCases(McpParityHarness):
    async def _case_test_design_lint_reconciliation_cli_mcp_parity(self) -> None:
        """Compare the same saved report through file and serialized JSON adapters."""
        native = self.native_evidence()
        baseline_process = await self.cli_process(
            "kicad_tooling.design_lint",
            "--project",
            "controller",
            "--native-summary",
            str(native),
            "--format",
            "json",
        )
        self.assertIn(baseline_process.returncode, (0, 1), baseline_process.stderr)
        baseline = DesignLintReport.model_validate_json(baseline_process.stdout)
        baseline_path = self.root / "lint-baseline.json"
        baseline_path.write_text(baseline.model_dump_json(), encoding="utf-8")

        cli_process = await self.cli_process(
            "kicad_tooling.design_lint",
            "--project",
            "controller",
            "--native-summary",
            str(native),
            "--baseline-report",
            baseline_path.name,
            "--format",
            "json",
        )
        cli = DesignLintReconciliationReport.model_validate_json(cli_process.stdout)
        self.assertEqual(cli_process.returncode, 0 if cli.status == "UNCHANGED" else 1)
        async with Client(create_server(self.root), mode="legacy") as client:
            mcp = await self.call(
                client,
                "reconcile_design_lint",
                DesignLintReconciliationReport,
                {
                    "project_id": "controller",
                    "native_summary": native.relative_to(self.root).as_posix(),
                    "baseline_report_json": baseline.model_dump_json(),
                },
            )

        self.assertEqual(cli, mcp)
        self.assertIn(cli.status, {"UNCHANGED", "REVIEW"})
        self.assertEqual(cli.baseline_project_id, "controller")
        self.assertTrue(cli.baseline_source_hashes)
        self.assertTrue(cli.current_source_hashes)
        self.assertIsNotNone(baseline.connectivity_snapshot)
        self.assertIn(cli.connectivity_comparison, {"COMPLETE", "PARTIAL"})
        self.assertEqual(cli.connectivity_changes, ())
        self.assertIn(cli.pin_metadata_comparison, {"COMPLETE", "PARTIAL"})
        self.assertEqual(cli.pin_metadata_changes, ())


def test_design_lint_reconciliation_cli_mcp_parity() -> None:
    run_mcp_parity(
        _DesignLintReconciliationParityCases,
        "_case_test_design_lint_reconciliation_cli_mcp_parity",
    )
