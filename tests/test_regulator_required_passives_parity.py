"""CLI/MCP parity for the authored regulator-passive topology rule."""

from __future__ import annotations

import os

import pytest

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.power_lint,
    pytest.mark.parity_lint,
    pytest.mark.slow,
    pytest.mark.template_checkout,
    pytest.mark.skipif(
        not os.environ.get("KICAD_TEMPLATE_ROOT"),
        reason="CLI/MCP parity needs the separate public template checkout",
    ),
]

from mcp import Client

from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import DesignLintPolicy, DesignLintReport, ProjectTestContract
from tests.mcp_parity_support import McpParityHarness, run_mcp_parity
from tests.test_regulator_required_passives import RULE_ID, topology_map


class _RegulatorPassiveParityCases(McpParityHarness):
    async def _case_test_authored_regulator_passive_rule_matches_cli_and_mcp(self) -> None:
        native = self.native_evidence()
        contract_path = self.island / "tests/contract.json"
        contract = read_model(contract_path, ProjectTestContract)
        policy = (contract.design_lint or DesignLintPolicy()).model_copy(
            update={"regulator_passive_topology_map": topology_map()}
        )
        write_model(contract_path, contract.model_copy(update={"design_lint": policy}))

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
        finding = next(item for item in mcp.findings if item.rule_id == RULE_ID)
        self.assertEqual(finding.mode, "review")
        self.assertIn("not verified by this check", finding.message)


def test_authored_regulator_passive_rule_matches_cli_and_mcp() -> None:
    run_mcp_parity(
        _RegulatorPassiveParityCases,
        "_case_test_authored_regulator_passive_rule_matches_cli_and_mcp",
    )
