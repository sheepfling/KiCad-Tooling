"""CLI and MCP parity for one local CAN terminator across multiple endpoints."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.parity_lint,
    pytest.mark.slow,
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
]

from mcp import Client

from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import DesignLintPolicy, DesignLintReport
from tests.component_peer_power_assignment_support import peer_pin_netlist_xml
from tests.design_lint_fixtures import can_peer_netlist
from tests.mcp_parity_support import parity_design_lint_policy, semantic_design_lint_report
from tests.pcb_drc_parity_support import install_source_bound_drc_receipt
from tests.synthetic_design_lint_project import (
    install_synthetic_netlist,
    run_design_lint_cli,
    synthetic_design_lint_project,
)

RULE_ID = "bus.can_single_local_termination"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_can_single_local_termination_cli_mcp_parity(tmp_path: Path) -> None:
    root, native = synthetic_design_lint_project(
        tmp_path,
        parity_design_lint_policy(DesignLintPolicy()),
    )
    install_synthetic_netlist(native, peer_pin_netlist_xml(can_peer_netlist()))
    install_source_bound_drc_receipt(root, native)
    process = run_design_lint_cli(tmp_path, root, native)
    assert process.returncode == 1, process.stderr + process.stdout
    cli = DesignLintReport.model_validate_json(process.stdout)

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
    findings = tuple(item for item in cli.findings if item.rule_id == RULE_ID)
    assert cli.status == "REVIEW", cli.issues
    assert len(findings) == 1
    assert findings[0].subject == (
        "CANH NET_A / CANL NET_B: one local terminator across 3 fitted endpoints"
    )
