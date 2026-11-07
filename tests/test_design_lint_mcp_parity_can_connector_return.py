"""CLI and MCP parity for two-pin CAN connector return review."""

from __future__ import annotations

import pytest
from mcp import Client

from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import DesignLintReport
from tests.component_peer_power_assignment_support import peer_pin_netlist_xml
from tests.design_lint_fixtures.can_generic_connector_pair import can_connector_return_netlist
from tests.mcp_parity_support import McpParityHarness, run_mcp_parity

pytestmark = [
    pytest.mark.parity_lint,
    pytest.mark.slow,
    pytest.mark.template_checkout,
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.return_path_lint,
]

RULE_ID = "connector.can_pair_without_return_review"


class _CanConnectorReturnParity(McpParityHarness):
    async def _case_two_pin_can_return_cli_mcp_parity(self) -> None:
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"
        netlist.write_text(peer_pin_netlist_xml(can_connector_return_netlist()), encoding="utf-8")
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
        assert len(findings) == 1
        assert findings[0].subject == (
            "J1: two-pin CAN connector has no identified reference return"
        )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_two_pin_can_return_cli_mcp_parity() -> None:
    run_mcp_parity(
        _CanConnectorReturnParity,
        "_case_two_pin_can_return_cli_mcp_parity",
    )
