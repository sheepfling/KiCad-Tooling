"""CLI/MCP parity for source-bound SPI shared-clock reference review."""

from __future__ import annotations

import pytest

pytestmark = [
    pytest.mark.parity_lint,
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
]

from mcp import Client

from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import DesignLintReport
from tests.component_peer_power_assignment_support import peer_pin_netlist_xml
from tests.mcp_parity_support import McpParityHarness, run_mcp_parity
from tests.spi_peer_reference_support import spi_peer_netlist


class _DesignLintMcpParitySpiReferenceCases(McpParityHarness):
    async def _case_test_spi_peer_reference_cli_mcp_parity(self) -> None:
        native = self.native_evidence()
        netlist_path = native.parent / "netlist.xml"

        async with Client(create_server(self.root), mode="legacy") as client:
            for references, expected_review in (
                ({"U1": "GND_A", "U2": "GND_B"}, True),
                ({"U1": "GND", "U2": "GND"}, False),
            ):
                with self.subTest(expected_review=expected_review):
                    observed = spi_peer_netlist(reference_nets=references)
                    netlist_path.write_text(peer_pin_netlist_xml(observed), encoding="utf-8")
                    self.rehash_native_netlist(native)
                    # The reused native summary already leaves the overall report nonzero.
                    cli = await self.cli(
                        "kicad_tooling.design_lint",
                        DesignLintReport,
                        "--project",
                        "controller",
                        "--native-summary",
                        str(native),
                        expected_exit=1,
                    )
                    mcp = await self.call(
                        client,
                        "inspect_design_lint",
                        DesignLintReport,
                        {
                            "project_id": "controller",
                            "native_summary": native.relative_to(self.root).as_posix(),
                        },
                    )
                    cli_findings = tuple(
                        item
                        for item in cli.findings
                        if item.rule_id == "bus.spi_peer_reference_review"
                    )
                    mcp_findings = tuple(
                        item
                        for item in mcp.findings
                        if item.rule_id == "bus.spi_peer_reference_review"
                    )
                    self.assertEqual(cli.status, mcp.status)
                    self.assertEqual(cli_findings, mcp_findings)
                    self.assertEqual(
                        cli.spi_peer_reference_coverage, mcp.spi_peer_reference_coverage
                    )
                    self.assertEqual(len(mcp_findings), int(expected_review))
                    self.assertEqual(
                        mcp.spi_peer_reference_coverage.candidate_group_count,
                        int(expected_review),
                    )


def test_spi_peer_reference_cli_mcp_parity() -> None:
    run_mcp_parity(
        _DesignLintMcpParitySpiReferenceCases,
        "_case_test_spi_peer_reference_cli_mcp_parity",
    )
