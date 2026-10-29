"""CLI/MCP parity for the one-sided open Ethernet data-pair review."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from mcp import Client

from kicad_tooling.hwrepo.contracts import parse_model_text
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import DesignLintPolicy, DesignLintReport, DesignLintRuleOverride
from tests.component_peer_power_assignment_support import peer_pin_netlist_xml
from tests.design_lint_fixtures.ethernet_data_unconnected import (
    ethernet_data_unconnected_netlist,
)
from tests.mcp_parity_support import parity_design_lint_policy, semantic_design_lint_report
from tests.synthetic_design_lint_project import (
    install_synthetic_netlist,
    run_design_lint_cli,
    synthetic_design_lint_project,
)

RULE_ID = "bus.ethernet_data_unconnected_pin"
pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.parity_lint,
    pytest.mark.slow,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def test_ethernet_data_unconnected_cli_mcp_parity(tmp_path: Path) -> None:
    policy = parity_design_lint_policy(
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="review",
                    reason="Exercise the synthetic Ethernet open-data review prompt.",
                ),
            )
        )
    )
    root, native = synthetic_design_lint_project(tmp_path, policy)
    fault = ethernet_data_unconnected_netlist(open_pins=("U1.1",))
    install_synthetic_netlist(native, peer_pin_netlist_xml(fault))
    process = run_design_lint_cli(tmp_path, root, native)
    assert process.returncode == 1, process.stderr + process.stdout
    cli = parse_model_text(process.stdout, DesignLintReport)

    async def inspect_mcp() -> DesignLintReport:
        async with Client(create_server(root), mode="legacy") as client:
            result = await client.call_tool(
                "inspect_design_lint",
                {
                    "project_id": "controller",
                    "native_summary": native.relative_to(root).as_posix(),
                },
            )
            assert not result.is_error, result.content
            assert result.structured_content is not None
            return DesignLintReport.model_validate_json(json.dumps(result.structured_content))

    mcp = asyncio.run(inspect_mcp())
    assert semantic_design_lint_report(cli) == semantic_design_lint_report(mcp)
    cli_findings = tuple(item for item in cli.findings if item.rule_id == RULE_ID)
    mcp_findings = tuple(item for item in mcp.findings if item.rule_id == RULE_ID)
    assert cli_findings == mcp_findings
    assert len(cli_findings) == 1
    assert cli_findings[0].subject == "U1.1: TDP is open while TDN U1.2 is assigned to ETH_TX_N"
