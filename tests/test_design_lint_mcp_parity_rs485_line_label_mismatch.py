"""CLI/MCP parity for source-bound RS-485 line-label review findings."""

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

from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import DesignLintReport, ValidationSummary
from tests.component_peer_power_assignment_support import peer_pin_netlist_xml
from tests.design_lint_fixtures.rs485_line_label_mismatch import rs485_line_label_mismatch_netlist
from tests.mcp_parity_support import McpParityHarness, run_mcp_parity

RULE_ID = "bus.rs485_line_label_mismatch"


class _Rs485LineLabelParityCases(McpParityHarness):
    async def _case_rs485_line_label_findings_match_cli_and_mcp(self) -> None:
        native = self.native_evidence()
        netlist_path = native.parent / "netlist.xml"
        summary = read_model(native, ValidationSummary)

        async with Client(create_server(self.root), mode="legacy") as client:
            for crossed, expected_count in ((True, 2), (False, 0)):
                observed = rs485_line_label_mismatch_netlist(crossed=crossed)
                netlist_path.write_text(peer_pin_netlist_xml(observed), encoding="utf-8")
                write_model(
                    native,
                    summary.model_copy(
                        update={
                            "artifacts_sha256": {
                                **summary.artifacts_sha256,
                                "netlist.xml": digest(netlist_path),
                            }
                        }
                    ),
                )
                cli = await self.cli(
                    "kicad_tooling.design_lint",
                    DesignLintReport,
                    "--project",
                    "controller",
                    "--native-summary",
                    str(native),
                    expected_exit=1 if expected_count else 0,
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
                findings = tuple(item for item in mcp.findings if item.rule_id == RULE_ID)
                self.assertEqual(len(findings), expected_count)
                self.assertEqual(mcp.status, "REVIEW" if expected_count else "PASS")


def test_rs485_line_label_findings_match_cli_and_mcp() -> None:
    run_mcp_parity(_Rs485LineLabelParityCases, "_case_rs485_line_label_findings_match_cli_and_mcp")
