"""CLI and MCP index the same selected project receipts."""

from __future__ import annotations

from pathlib import Path

import pytest
from mcp import Client

from kicad_tooling.hwrepo.findings_view import build_findings_view
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.review_overview_models import ReviewOverviewReport
from tests.findings_view_support import add_native_review, select_schematic_geometry_toolchain
from tests.mcp_parity_support import McpParityHarness, run_mcp_parity

pytestmark = [pytest.mark.template_checkout, pytest.mark.parity_lint]


class _ReviewOverviewParityCases(McpParityHarness):
    async def _case_test_cli_mcp_review_overview_parity(self) -> None:
        select_schematic_geometry_toolchain(self.island)
        native = self.native_evidence()
        add_native_review(self.root, native)
        findings = build_findings_view(
            self.root, "controller", native, Path("build/findings-view/saved")
        )
        selected = {
            "native_summary": native.relative_to(self.root).as_posix(),
            "findings_view": (Path(findings.output_directory) / "review.json")
            .relative_to(self.root)
            .as_posix(),
            "parts_report": "build/parts/absent/report.json",
        }
        cli = await self.cli(
            "kicad_tooling.review_overview",
            ReviewOverviewReport,
            "--project",
            "controller",
            "--native-summary",
            selected["native_summary"],
            "--findings-view",
            selected["findings_view"],
            "--parts-report",
            selected["parts_report"],
            "--output",
            "build/review-overview/cli",
        )
        arguments = {"project_id": "controller", "view_id": "mcp", **selected}
        async with Client(create_server(self.root), mode="legacy") as client:
            self.assertTrue((await client.call_tool("export_review_overview", arguments)).is_error)
        async with Client(create_server(self.root, allow_exports=True), mode="legacy") as client:
            mcp = await self.call(client, "export_review_overview", ReviewOverviewReport, arguments)
            self.assertTrue((await client.call_tool("export_review_overview", arguments)).is_error)
        self.receipt_equal(cli, mcp, "output_directory")
        self.assertEqual(
            (Path(cli.output_directory) / "index.html").read_bytes(),
            (Path(mcp.output_directory) / "index.html").read_bytes(),
        )
        self.assertEqual(cli.items[2].freshness, "MISSING")


def test_cli_mcp_review_overview_parity() -> None:
    run_mcp_parity(_ReviewOverviewParityCases, "_case_test_cli_mcp_review_overview_parity")
