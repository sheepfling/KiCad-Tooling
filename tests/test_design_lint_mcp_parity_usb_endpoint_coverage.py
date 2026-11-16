"""CLI/MCP parity for incomplete USB endpoint-path coverage prompts."""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest
from mcp import Client

from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import DesignLintReport
from tests.component_peer_power_assignment_support import peer_pin_netlist_xml
from tests.mcp_parity_support import McpParityHarness, run_mcp_parity
from tests.usb_peer_reference_support import usb_peer_netlist

RULE_ID = "bus.usb_endpoint_path_coverage_incomplete"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.parity_lint,
    pytest.mark.slow,
    pytest.mark.template_checkout,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


class _UsbEndpointCoverageParity(McpParityHarness):
    async def _case_incomplete_usb_endpoint_coverage_cli_mcp_parity(self) -> None:
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"
        root = ET.fromstring(peer_pin_netlist_xml(usb_peer_netlist()))
        for native_net in root.findall("./nets/net"):
            for node in tuple(native_net.findall("node")):
                if node.get("ref") == "U1" and node.get("pin") == "3":
                    native_net.remove(node)
        netlist.write_bytes(ET.tostring(root, encoding="utf-8", xml_declaration=True))
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

        assert cli == mcp
        findings = tuple(item for item in cli.findings if item.rule_id == RULE_ID)
        assert len(findings) == 1, (
            cli.usb_peer_reference_coverage,
            tuple(item.rule_id for item in cli.findings),
        )
        assert findings[0].subject == "USB path coverage: 2 endpoint group(s) unassessed"


def test_incomplete_usb_endpoint_coverage_cli_mcp_parity() -> None:
    run_mcp_parity(
        _UsbEndpointCoverageParity,
        "_case_incomplete_usb_endpoint_coverage_cli_mcp_parity",
    )
