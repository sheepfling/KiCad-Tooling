"""CLI/MCP parity for one-sided open I3C pin review."""

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
from tests.design_lint_fixtures.i3c_same_net import i3c_same_net_netlist
from tests.mcp_parity_support import parity_design_lint_policy, semantic_design_lint_report
from tests.synthetic_design_lint_project import (
    install_synthetic_netlist,
    run_design_lint_cli,
    synthetic_design_lint_project,
)

RULE_ID = "bus.i3c_unconnected_pin"
pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.parity_lint,
    pytest.mark.slow,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def test_i3c_unconnected_cli_mcp_parity(tmp_path: Path) -> None:
    rule_policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode="review",
                reason="Exercise the synthetic I3C open-pin review prompt.",
            ),
        )
    )
    policy = parity_design_lint_policy(rule_policy)
    root, native = synthetic_design_lint_project(tmp_path, policy)
    fault = i3c_same_net_netlist().model_copy(update={"nets": {"I3C_SCL": ("U1.2",)}})
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
    assert cli_findings[0].subject == "U1.1: I3C1_SDA"
