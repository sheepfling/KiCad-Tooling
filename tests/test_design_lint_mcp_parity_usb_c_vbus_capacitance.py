"""CLI/MCP parity for USB-C VBUS capacitor-presence review."""

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
from tests.mcp_parity_support import McpParityHarness, run_mcp_parity
from tests.usb_c_vbus_capacitance_support import usb_c_vbus_netlist

RULE_ID = "bus.usb_c_vbus_capacitance_review"


class _UsbCVbusCapacitanceParityCase(McpParityHarness):
    async def _case_usb_c_vbus_capacitance_review_cli_mcp_parity(self) -> None:
        native = self.native_evidence()
        observed = usb_c_vbus_netlist(connector="X99")
        (native.parent / "netlist.xml").write_text(peer_pin_netlist_xml(observed), encoding="utf-8")
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
        cli_findings = tuple(item for item in cli.findings if item.rule_id == RULE_ID)
        mcp_findings = tuple(item for item in mcp.findings if item.rule_id == RULE_ID)
        self.assertEqual(cli_findings, mcp_findings)
        self.assertEqual(len(cli_findings), 1)
        self.assertEqual(
            cli_findings[0].subject,
            "X99: USB-C VBUS has no recognized return capacitor",
        )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_usb_c_vbus_capacitance_review_cli_mcp_parity() -> None:
    run_mcp_parity(
        _UsbCVbusCapacitanceParityCase,
        "_case_usb_c_vbus_capacitance_review_cli_mcp_parity",
    )
