"""CLI and MCP parity for generic USB SuperSpeed connector review."""

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
from tests.design_lint_fixtures.usb_superspeed_generic_connector import (
    generic_usb_superspeed_connector_pair_netlist,
)
from tests.mcp_parity_support import McpParityHarness, run_mcp_parity

RULE_ID = "bus.usb_superspeed_generic_connector_pair_review"


class _GenericUsbSuperspeedConnectorParity(McpParityHarness):
    async def _case_generic_superspeed_connector_cli_mcp_parity(self) -> None:
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"
        netlist.write_text(
            peer_pin_netlist_xml(generic_usb_superspeed_connector_pair_netlist()),
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
        assert len(findings) == 1
        assert findings[0].subject == "J1 / U1: generic pins match USB SuperSpeed TX pair"
        assert findings[0].evidence["other_connector_contacts"] == (
            "J1.3 function=GND nets=USB_GND",
            "J1.4 function=VBUS nets=unassigned",
        )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_generic_superspeed_connector_cli_mcp_parity() -> None:
    run_mcp_parity(
        _GenericUsbSuperspeedConnectorParity,
        "_case_generic_superspeed_connector_cli_mcp_parity",
    )
