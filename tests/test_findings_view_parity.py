"""CLI and MCP export the same retained-evidence findings review."""

from __future__ import annotations

from pathlib import Path

import pytest
from mcp import Client

from kicad_tooling.hwrepo.findings_view_models import FindingsViewReport
from kicad_tooling.hwrepo.mcp_server import create_server
from tests.findings_view_support import (
    add_lint_snapshot,
    add_native_review,
    select_schematic_geometry_toolchain,
)
from tests.mcp_parity_support import McpParityHarness, run_mcp_parity

pytestmark = [pytest.mark.design_lint, pytest.mark.parity_lint, pytest.mark.template_checkout]


class _FindingsViewParityCases(McpParityHarness):
    async def _case_test_cli_mcp_findings_view_parity(self) -> None:
        select_schematic_geometry_toolchain(self.island)
        native = self.native_evidence()
        add_native_review(self.root, native)
        lint = add_lint_snapshot(self.root, native)
        cli = await self.cli(
            "kicad_tooling.findings_view",
            FindingsViewReport,
            "--project",
            "controller",
            "--native-summary",
            str(native),
            "--lint-report",
            str(lint),
            "--output",
            "build/findings-view/cli",
        )
        args = {
            "project_id": "controller",
            "native_summary": native.relative_to(self.root).as_posix(),
            "lint_report": lint.relative_to(self.root).as_posix(),
            "view_id": "mcp",
        }
        async with Client(create_server(self.root), mode="legacy") as client:
            result = await client.call_tool("export_findings_view", args)
            self.assertTrue(result.is_error)
        async with Client(create_server(self.root, allow_exports=True), mode="legacy") as client:
            mcp = await self.call(client, "export_findings_view", FindingsViewReport, args)
            self.assertTrue((await client.call_tool("export_findings_view", args)).is_error)
        self.receipt_equal(cli, mcp, "output_directory")
        self.assertEqual(len(mcp.findings), 4)
        self.assertEqual(len(mcp.findings[-1].markers), 1)
        for name in ("index.html", "pcb.svg", "schematic-1.svg"):
            self.assertEqual(
                (Path(cli.output_directory) / name).read_bytes(),
                (Path(mcp.output_directory) / name).read_bytes(),
            )


def test_cli_mcp_findings_view_parity() -> None:
    run_mcp_parity(_FindingsViewParityCases, "_case_test_cli_mcp_findings_view_parity")
