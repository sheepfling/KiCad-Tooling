"""CLI and MCP parity for the generic SPI connector role-triad prompt."""

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
from tests.design_lint_fixtures.spi_generic_connector_triad import (
    generic_spi_connector_triad_netlist,
)
from tests.mcp_parity_support import McpParityHarness, run_mcp_parity

RULE_ID = "bus.spi_generic_connector_triad_review"


class _GenericSpiConnectorTriadParity(McpParityHarness):
    async def _case_generic_connector_triad_review_cli_mcp_parity(self) -> None:
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"
        netlist.write_text(
            peer_pin_netlist_xml(generic_spi_connector_triad_netlist()), encoding="utf-8"
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
        assert len(findings) == 1
        assert findings[0].subject == "J1: generic pins match SPI clock and both data roles"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_generic_connector_triad_review_cli_mcp_parity() -> None:
    run_mcp_parity(
        _GenericSpiConnectorTriadParity,
        "_case_generic_connector_triad_review_cli_mcp_parity",
    )
