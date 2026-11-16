"""CLI/MCP parity for shared RS-485 receiver-output review findings."""

from __future__ import annotations

import json

import pytest

pytestmark = [
    pytest.mark.parity_lint,
    pytest.mark.slow,
    pytest.mark.template_checkout,
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
]

from mcp import Client

from kicad_tooling.hwrepo.command_evidence_models import CommandEvidence
from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.discovery import load_config
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    CheckEvidence,
    DesignLintReport,
    ValidationSummary,
)
from tests.component_peer_power_assignment_support import peer_pin_netlist_xml
from tests.design_lint_fixtures.rs485_receiver_output_sharing import (
    rs485_receiver_output_sharing_netlist,
)
from tests.mcp_parity_support import McpParityHarness, run_mcp_parity

RULE_ID = "bus.rs485_receiver_outputs_share_net"


class _Rs485ReceiverOutputParityCases(McpParityHarness):
    async def _case_shared_receiver_output_findings_match_cli_and_mcp(self) -> None:
        native = self.native_evidence()
        netlist_path = native.parent / "netlist.xml"
        summary = read_model(native, ValidationSummary)
        content = peer_pin_netlist_xml(rs485_receiver_output_sharing_netlist())
        required_part_controls = """<comp ref="R1"><value>1k</value><footprint>Pilot:R_Test</footprint>
<fields><field name="PART_ID">resistor-1k</field></fields></comp>
<comp ref="R2"><value>1k</value><footprint>Pilot:R_Test</footprint>
<fields><field name="PART_ID">resistor-1k</field></fields></comp>
<comp ref="C1"><value>Unfitted</value><property name="dnp"/></comp>"""
        netlist_path.write_text(
            content.replace("</components>", required_part_controls + "</components>", 1),
            encoding="utf-8",
        )
        config = load_config(self.root, self.island / "project.json")
        board_path = (self.root / config.project).with_suffix(".kicad_pcb")
        drc_path = native.parent / "drc.json"
        drc_command_path = native.parent / "drc.command.json"
        drc_path.write_text(
            json.dumps(
                {
                    "$schema": "https://schemas.kicad.org/drc.v1.json",
                    "coordinate_units": "mm",
                    "kicad_version": config.kicad_version,
                    "included_severities": ["error", "warning", "exclusion"],
                    "ignored_checks": [],
                    "source": board_path.name,
                    "violations": [],
                    "unconnected_items": [],
                    "schematic_parity": [],
                }
            ),
            encoding="utf-8",
        )
        write_model(
            drc_command_path,
            CommandEvidence(
                argv=(
                    "kicad-cli",
                    "pcb",
                    "drc",
                    "--format",
                    "json",
                    "--severity-all",
                    "--output",
                    str(drc_path),
                    str(board_path),
                ),
                started_utc="2026-11-15T00:00:00+00:00",
                returncode=0,
            ),
        )
        write_model(
            native,
            summary.model_copy(
                update={
                    "artifacts_sha256": {
                        **summary.artifacts_sha256,
                        "netlist.xml": digest(netlist_path),
                        "drc.json": digest(drc_path),
                        "drc.command.json": digest(drc_command_path),
                    },
                    "checks": {
                        **summary.checks,
                        "drc": CheckEvidence(status="PASS", returncode=0),
                    },
                }
            ),
        )

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
        self.assertFalse(mcp.issues, str(mcp.issues))
        finding = next(item for item in mcp.findings if item.rule_id == RULE_ID)
        self.assertEqual(
            finding.subject,
            "U1, U2: RS-485 receiver-output pins share RX_SHARED",
        )
        self.assertEqual(finding.mode, "review")


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_rs485_receiver_output_findings_match_cli_and_mcp() -> None:
    run_mcp_parity(
        _Rs485ReceiverOutputParityCases,
        "_case_shared_receiver_output_findings_match_cli_and_mcp",
    )
