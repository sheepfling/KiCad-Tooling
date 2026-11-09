"""CLI/MCP parity for the authored regulator-passive topology rule."""

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
from tests.test_regulator_feedback import regulator_netlist
from tests.test_regulator_passive_pin_roles import RULE_ID as PIN_ROLE_RULE_ID
from tests.test_regulator_required_passives import RULE_ID, topology_map
from tests.test_regulator_support_pin_roles import RULE_ID as SUPPORT_PIN_ROLE_RULE_ID
from tests.test_regulator_support_pin_roles import support_map, support_netlist

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.power_lint,
    pytest.mark.parity_lint,
    pytest.mark.slow,
]


def _assert_cli_mcp_parity(
    tmp_path: Path,
    source,
    expected_rule_id: str,
    *,
    support_roles: bool = False,
) -> None:
    policy = DesignLintPolicy(
        regulator_passive_topology_map=None if support_roles else topology_map(),
        regulator_support_pin_role_map=support_map() if support_roles else None,
    )
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
            if expected_rule_id == RULE_ID:
                finding = next(item for item in mcp.findings if item.rule_id == RULE_ID)
                assert finding.mode == "review"
                assert "not verified by this check" in finding.message
            else:
                finding = next(item for item in mcp.findings if item.rule_id == expected_rule_id)
                assert finding.mode == "review"

    asyncio.run(exercise())


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_authored_regulator_passive_rule_matches_cli_and_mcp(tmp_path: Path) -> None:
    _assert_cli_mcp_parity(tmp_path, regulator_netlist(), RULE_ID)


@pytest.mark.design_lint_rule(rule_id=PIN_ROLE_RULE_ID)
def test_authored_regulator_pin_role_rule_matches_cli_and_mcp(tmp_path: Path) -> None:
    _assert_cli_mcp_parity(
        tmp_path,
        regulator_netlist(fault="wrong-feedback-function", with_compensation_capacitor=True),
        PIN_ROLE_RULE_ID,
    )


@pytest.mark.design_lint_rule(rule_id=SUPPORT_PIN_ROLE_RULE_ID)
def test_authored_active_regulator_support_pin_roles_match_cli_and_mcp(tmp_path: Path) -> None:
    _assert_cli_mcp_parity(
        tmp_path,
        support_netlist(fault="wrong-optocoupler-function"),
        SUPPORT_PIN_ROLE_RULE_ID,
        support_roles=True,
    )
