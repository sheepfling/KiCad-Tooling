"""CLI/MCP parity for open-collector control pull-up voltage review."""

from __future__ import annotations

import pytest

pytestmark = [
    pytest.mark.parity_lint,
    pytest.mark.slow,
    pytest.mark.template_checkout,
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.power_lint,
]

from mcp import Client

from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import DesignLintReport
from tests.component_peer_power_assignment_support import peer_pin_netlist_xml
from tests.design_lint_fixtures.open_drain_control_voltage import (
    open_drain_control_voltage_netlist,
)
from tests.mcp_parity_support import McpParityHarness, run_mcp_parity

RULE_ID = "power.open_drain_control_input_pullup_voltage_review"


class _OpenDrainControlVoltageParityCases(McpParityHarness):
    async def _case_open_drain_control_fault_and_control_match_cli_mcp(self) -> None:
        native = self.native_evidence()
        netlist_path = native.parent / "netlist.xml"

        async with Client(create_server(self.root), mode="legacy") as client:
            for case, source, expected_count in (
                ("fault", open_drain_control_voltage_netlist(), 1),
                (
                    "control",
                    open_drain_control_voltage_netlist(
                        pullup_rail="+3V3", driver_rail="+3V3", receiver_rail="+3V3"
                    ),
                    0,
                ),
            ):
                with self.subTest(case=case):
                    netlist_path.write_text(peer_pin_netlist_xml(source), encoding="utf-8")
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
                    cli_findings = tuple(item for item in cli.findings if item.rule_id == RULE_ID)
                    mcp_findings = tuple(item for item in mcp.findings if item.rule_id == RULE_ID)

                    self.assertEqual(cli.status, mcp.status)
                    self.assertEqual(cli_findings, mcp_findings)
                    self.assertEqual(len(cli_findings), expected_count)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_open_drain_control_fault_and_control_match_cli_mcp() -> None:
    run_mcp_parity(
        _OpenDrainControlVoltageParityCases,
        "_case_open_drain_control_fault_and_control_match_cli_mcp",
    )
