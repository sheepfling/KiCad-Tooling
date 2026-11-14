"""CLI/MCP parity for the Ethernet MDC/MDIO same-net review."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from mcp import Client

from kicad_tooling.hwrepo.contracts import parse_model_text
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    DesignLintPolicy,
    DesignLintReport,
    DesignLintRuleOverride,
)
from tests.component_peer_power_assignment_support import peer_pin_netlist_xml
from tests.design_lint_fixtures.ethernet_management_same_net import (
    ethernet_management_same_net_netlist,
)
from tests.mcp_parity_support import parity_design_lint_policy, semantic_design_lint_report
from tests.pcb_drc_parity_support import install_source_bound_drc_receipt
from tests.synthetic_design_lint_project import (
    install_synthetic_netlist,
    run_design_lint_cli,
    synthetic_design_lint_project,
)

RULE_ID = "bus.ethernet_management_same_net"
pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.parity_lint,
    pytest.mark.slow,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def test_ethernet_management_same_net_cli_mcp_parity(tmp_path: Path) -> None:
    policy = parity_design_lint_policy(
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="review",
                    reason="Exercise the synthetic Ethernet shared-management-net review.",
                ),
            )
        )
    )
    root, native = synthetic_design_lint_project(tmp_path, policy)
    source = ethernet_management_same_net_netlist()
    install_synthetic_netlist(native, peer_pin_netlist_xml(source))
    install_source_bound_drc_receipt(root, native)

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

    process = run_design_lint_cli(tmp_path, root, native)
    assert process.returncode == 1, process.stderr + process.stdout
    cli = parse_model_text(process.stdout, DesignLintReport)
    mcp = asyncio.run(inspect_mcp())
    assert semantic_design_lint_report(cli) == semantic_design_lint_report(mcp)

    cli_findings = tuple(item for item in cli.findings if item.rule_id == RULE_ID)
    mcp_findings = tuple(item for item in mcp.findings if item.rule_id == RULE_ID)
    assert cli_findings == mcp_findings
    assert len(cli_findings) == 1, cli.model_dump_json(indent=2)
    assert cli_findings[0].mode == "review"
    assert cli_findings[0].subject == "U1: MDC U1.5 and MDIO U1.6 share MII_MANAGEMENT"
