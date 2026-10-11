"""CLI/MCP parity for source-bound CAN shared-pair reference review."""

from __future__ import annotations

import pytest

pytestmark = [
    pytest.mark.parity_lint,
    pytest.mark.slow,
    pytest.mark.template_checkout,
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
]

from mcp import Client

from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import DesignLintReport
from tests.can_peer_reference_support import can_peer_reference_netlist
from tests.component_peer_power_assignment_support import peer_pin_netlist_xml
from tests.mcp_parity_support import McpParityHarness, run_mcp_parity


class _CanPeerReferenceParityCases(McpParityHarness):
    async def _case_can_peer_reference_cli_mcp_parity(self) -> None:
        native = self.native_evidence()
        netlist_path = native.parent / "netlist.xml"

        async with Client(create_server(self.root), mode="legacy") as client:
            for references, expected_count in (
                ({"U1": "GND_A", "U2": "GND_B"}, 1),
                ({"U1": "GND", "U2": "GND"}, 0),
            ):
                observed = can_peer_reference_netlist(reference_nets=references)
                netlist_path.write_text(peer_pin_netlist_xml(observed), encoding="utf-8")
                self.rehash_native_netlist(native)
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
                    item for item in cli.findings if item.rule_id == "bus.can_peer_reference_review"
                )
                mcp_findings = tuple(
                    item for item in mcp.findings if item.rule_id == "bus.can_peer_reference_review"
                )
                self.assertEqual(cli.status, mcp.status)
                self.assertEqual(cli_findings, mcp_findings)
                self.assertEqual(cli.can_peer_reference_coverage, mcp.can_peer_reference_coverage)
                self.assertEqual(len(mcp_findings), expected_count)
                self.assertEqual(
                    mcp.can_peer_reference_coverage.candidate_group_count,
                    expected_count,
                )


def test_can_peer_reference_cli_mcp_parity() -> None:
    run_mcp_parity(
        _CanPeerReferenceParityCases,
        "_case_can_peer_reference_cli_mcp_parity",
    )
