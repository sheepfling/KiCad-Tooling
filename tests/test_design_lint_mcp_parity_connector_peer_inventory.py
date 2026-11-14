"""CLI/MCP parity for exact-part connector peer inventory review."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from mcp import Client

import tests.test_connector_footprint_peer_pin_inventory_consistency as _inventory
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import DesignLintPolicy, DesignLintRuleOverride
from tests.component_peer_power_assignment_support import peer_pin_netlist_xml
from tests.mcp_parity_support import parity_design_lint_policy, semantic_design_lint_report
from tests.pcb_drc_parity_support import install_source_bound_drc_receipt
from tests.synthetic_design_lint_project import (
    install_synthetic_netlist,
    run_design_lint_cli,
    synthetic_design_lint_project,
)

RULE_ID = "connector.footprint_peer_pin_inventory_disagreement"
pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.interface_lint,
    pytest.mark.parity_lint,
    pytest.mark.slow,
]


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_connector_peer_inventory_review_matches_between_cli_and_mcp(tmp_path: Path) -> None:
    policy = parity_design_lint_policy(
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="review",
                    reason="Synthetic parity case explicitly selects inventory review.",
                ),
            )
        )
    )
    root, summary_path = synthetic_design_lint_project(tmp_path, policy)
    install_source_bound_drc_receipt(root, summary_path)

    async def inspect_mcp() -> DesignLintReport:
        async with Client(create_server(root), mode="legacy") as client:
            result = await client.call_tool(
                "inspect_design_lint",
                {
                    "project_id": "controller",
                    "native_summary": summary_path.relative_to(root).as_posix(),
                },
            )
            assert not result.is_error, result.content
            assert result.structured_content is not None
            return DesignLintReport.model_validate_json(json.dumps(result.structured_content))

    cases = (
        ("fault", _inventory._source(), 1),
        ("matching-control", _inventory._source(extra_numbers=()), 0),
        ("generic-control", _inventory._source(extra_function="Pin_3"), 0),
    )
    for name, observed, expected_count in cases:
        install_synthetic_netlist(summary_path, peer_pin_netlist_xml(observed))
        process = run_design_lint_cli(tmp_path, root, summary_path)
        assert process.returncode in {0, 1}, process.stderr + process.stdout
        cli_report = DesignLintReport.model_validate_json(process.stdout)
        mcp_report = asyncio.run(inspect_mcp())
        cli_findings = tuple(item for item in cli_report.findings if item.rule_id == RULE_ID)
        mcp_findings = tuple(item for item in mcp_report.findings if item.rule_id == RULE_ID)

        assert semantic_design_lint_report(cli_report) == semantic_design_lint_report(mcp_report), (
            name
        )
        assert cli_findings == mcp_findings, name
        assert len(cli_findings) == expected_count, name
