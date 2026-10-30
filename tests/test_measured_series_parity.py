"""CLI and MCP share the measured CSV import service and receipt contract."""

from __future__ import annotations

from pathlib import Path

import pytest
from mcp import Client

from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.measured_series_models import MeasuredSeriesReport
from tests.mcp_parity_support import McpParityHarness, run_mcp_parity

pytestmark = pytest.mark.template_checkout


class _MeasuredSeriesParity(McpParityHarness):
    async def _case_test_cli_mcp_measured_series_parity(self) -> None:
        source = self.island / "docs/measurement.csv"
        source.write_text(
            "time,v,i\n0,1.0000000000000000001,0.1\n1,2.0000000000000000002,0.2\n", encoding="utf-8"
        )
        cli = await self.cli(
            "kicad_tooling.measured_series",
            MeasuredSeriesReport,
            "--project",
            "controller",
            "--source",
            str(source),
            "--time-column",
            "time",
            "--time-unit",
            "s",
            "--channel",
            "v=V",
            "--channel",
            "i=A",
            "--output",
            "build/measured-series/cli",
        )
        arguments = {
            "project_id": "controller",
            "view_id": "mcp",
            "source": source.relative_to(self.root).as_posix(),
            "time_column": "time",
            "time_unit": "s",
            "channels": ["v=V", "i=A"],
        }
        async with Client(create_server(self.root), mode="legacy") as client:
            self.assertTrue(
                (await client.call_tool("import_measured_time_series", arguments)).is_error
            )
        async with Client(create_server(self.root, allow_exports=True), mode="legacy") as client:
            mcp = await self.call(
                client, "import_measured_time_series", MeasuredSeriesReport, arguments
            )
        self.receipt_equal(cli, mcp, "output_directory")
        for name in ("source.csv", "data.csv", "plot.png", "plot.svg"):
            self.assertEqual(
                (Path(cli.output_directory) / name).read_bytes(),
                (Path(mcp.output_directory) / name).read_bytes(),
            )


def test_cli_mcp_measured_series_parity() -> None:
    run_mcp_parity(_MeasuredSeriesParity, "_case_test_cli_mcp_measured_series_parity")
