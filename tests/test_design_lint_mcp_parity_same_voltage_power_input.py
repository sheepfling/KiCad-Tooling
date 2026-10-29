"""CLI/MCP parity for the same-voltage split supply-input review."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from mcp import Client

from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import DesignLintReport
from tests.design_lint_fixtures.same_voltage_power_inputs import (
    same_voltage_power_input_netlist,
    same_voltage_power_input_review_policy,
)
from tests.electrical_parity_support import contract_netlist_xml
from tests.mcp_parity_support import parity_design_lint_policy, semantic_design_lint_report
from tests.synthetic_design_lint_project import (
    install_synthetic_netlist,
    run_design_lint_cli,
    synthetic_design_lint_project,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.component_lint,
    pytest.mark.power_lint,
    pytest.mark.parity_lint,
    pytest.mark.slow,
]


def test_same_voltage_power_input_review_matches_between_cli_and_mcp(tmp_path: Path) -> None:
    root, native = synthetic_design_lint_project(
        tmp_path, parity_design_lint_policy(same_voltage_power_input_review_policy())
    )
    install_synthetic_netlist(native, contract_netlist_xml(same_voltage_power_input_netlist()))

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
            assert "component.same_voltage_power_inputs_split" in {
                item.rule_id for item in mcp.findings
            }

    asyncio.run(exercise())
