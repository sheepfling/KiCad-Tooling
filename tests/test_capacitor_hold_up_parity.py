"""CLI and MCP expose the same source-bound capacitor hold-up review."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from mcp import Client

from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import DesignLintPolicy, DesignLintReport
from tests.electrical_parity_support import contract_netlist_xml
from tests.mcp_parity_support import semantic_design_lint_report
from tests.synthetic_design_lint_project import (
    install_synthetic_netlist,
    run_design_lint_cli,
    synthetic_design_lint_project,
)
from tests.test_capacitor_hold_up import (
    RULE_ID,
    hold_up_map,
    hold_up_netlist,
    parallel_bank_map,
    parallel_bank_netlist,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.power_lint,
    pytest.mark.parity_lint,
    pytest.mark.slow,
]


def test_project_authored_capacitor_hold_up_matches_cli_and_mcp(tmp_path: Path) -> None:
    source = hold_up_netlist()
    policy = DesignLintPolicy(capacitor_hold_up_map=hold_up_map(minimum_ms=2001.0))
    root, native = synthetic_design_lint_project(tmp_path, policy)
    install_synthetic_netlist(native, contract_netlist_xml(source))

    async def exercise() -> None:
        async with Client(create_server(root), mode="legacy") as client:
            process = run_design_lint_cli(tmp_path, root, native)
            assert process.returncode in {0, 1}, process.stderr + process.stdout
            cli = DesignLintReport.model_validate_json(process.stdout)
            result = await client.call_tool(
                "inspect_design_lint",
                {
                    "project_id": "controller",
                    "native_summary": native.relative_to(root).as_posix(),
                },
            )
            assert not result.is_error, result.content
            assert result.structured_content is not None
            mcp = DesignLintReport.model_validate_json(json.dumps(result.structured_content))
            assert semantic_design_lint_report(cli) == semantic_design_lint_report(mcp)
            assert process.returncode == (0 if cli.status == "PASS" else 1)
            finding = next(item for item in mcp.findings if item.rule_id == RULE_ID)
            assert finding.mode == "review"
            assert finding.evidence["map_sha256"]

    asyncio.run(exercise())


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_project_authored_parallel_bank_hold_up_matches_cli_and_mcp(tmp_path: Path) -> None:
    source = parallel_bank_netlist()
    policy = DesignLintPolicy(capacitor_hold_up_map=parallel_bank_map(minimum_ms=2001.0))
    root, native = synthetic_design_lint_project(tmp_path, policy)
    install_synthetic_netlist(native, contract_netlist_xml(source))

    async def exercise() -> None:
        async with Client(create_server(root), mode="legacy") as client:
            process = run_design_lint_cli(tmp_path, root, native)
            assert process.returncode in {0, 1}, process.stderr + process.stdout
            cli = DesignLintReport.model_validate_json(process.stdout)
            result = await client.call_tool(
                "inspect_design_lint",
                {
                    "project_id": "controller",
                    "native_summary": native.relative_to(root).as_posix(),
                },
            )
            assert not result.is_error, result.content
            assert result.structured_content is not None
            mcp = DesignLintReport.model_validate_json(json.dumps(result.structured_content))
            assert semantic_design_lint_report(cli) == semantic_design_lint_report(mcp)
            finding = next(item for item in mcp.findings if item.rule_id == RULE_ID)
            assert finding.mode == "review"
            assert finding.evidence["parallel_capacitors"] == ("C2",)

    asyncio.run(exercise())
