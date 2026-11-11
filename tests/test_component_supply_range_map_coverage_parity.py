"""CLI and MCP share IC supply-range map coverage findings."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from mcp import Client

from kicad_tooling.hwrepo.design_lint_finding_models import DesignLintRuleOverride
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import DesignLintReport
from tests.design_lint_fixtures.component_supply_voltage_ranges import (
    supply_range_map,
    supply_range_map_coverage_netlist,
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

RULE_ID = "power.component_supply_range_map_coverage"


def test_component_supply_range_map_coverage_review_matches_between_cli_and_mcp(
    tmp_path: Path,
) -> None:
    policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode="review",
                reason="The synthetic regression explicitly checks missing map coverage",
            ),
        ),
        component_supply_voltage_range_map=supply_range_map(),
    )
    root, native = synthetic_design_lint_project(tmp_path, parity_design_lint_policy(policy))
    install_synthetic_netlist(native, contract_netlist_xml(supply_range_map_coverage_netlist()))
    process = run_design_lint_cli(tmp_path, root, native)
    assert process.returncode in {0, 1}, process.stderr + process.stdout
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
    assert cli.status == mcp.status == "REVIEW"
    cli_findings = tuple(item for item in cli.findings if item.rule_id == RULE_ID)
    mcp_findings = tuple(item for item in mcp.findings if item.rule_id == RULE_ID)
    assert len(cli_findings) == len(mcp_findings) == 1
    assert cli_findings[0].evidence["component"] == ("U3",)
    assert cli_findings[0].evidence["native_power_input_pins"] == ("U3.1", "U3.2")
