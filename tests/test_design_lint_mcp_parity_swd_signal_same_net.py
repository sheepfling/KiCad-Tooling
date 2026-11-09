"""CLI and MCP parity for native SWDIO/SWCLK same-net evidence."""

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
from tests.component_peer_power_assignment_support import peer_pin_netlist_xml
from tests.design_lint_fixtures.swd_signal_same_net import swd_signal_same_net_netlist
from tests.mcp_parity_support import McpParityHarness, run_mcp_parity

RULE_ID = "bus.swdio_swclk_same_net"


class _SwdSignalSameNetParity(McpParityHarness):
    async def _case_swd_signal_same_net_cli_mcp_parity(self) -> None:
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"
        netlist.write_text(
            peer_pin_netlist_xml(swd_signal_same_net_netlist()),
            encoding="utf-8",
        )
        self.rehash_native_netlist(native)

        async with Client(create_server(self.root), mode="legacy") as client:
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

        self.assertEqual(cli, mcp)
        findings = tuple(item for item in cli.findings if item.rule_id == RULE_ID)
        assert tuple(item.subject for item in findings) == (
            "U1: SWDIO U1.5 and SWCLK U1.6 share SWD_SHARED",
        )
        assert findings[0].evidence["SWDIO_pin"] == ("U1.5",)
        assert findings[0].evidence["SWCLK_pin"] == ("U1.6",)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_swd_signal_same_net_cli_mcp_parity() -> None:
    run_mcp_parity(_SwdSignalSameNetParity, "_case_swd_signal_same_net_cli_mcp_parity")
