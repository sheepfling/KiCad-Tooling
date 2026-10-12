"""CLI and MCP parity for generic component peer assignment review."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from mcp import Client

from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    DesignLintPolicy,
    DesignLintReport,
    DesignLintRuleOverride,
    ValidationSummary,
)
from tests.component_peer_pin_support import peer_component_pin_netlist
from tests.component_peer_power_assignment_support import peer_pin_netlist_xml
from tests.mcp_parity_support import semantic_design_lint_report
from tests.synthetic_design_lint_project import run_design_lint_cli, synthetic_design_lint_project

RULE_ID = "component.generic_peer_pin_assignment_outlier"
pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.component_lint,
    pytest.mark.parity_lint,
    pytest.mark.slow,
]


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_generic_peer_assignment_outlier_matches_between_cli_and_mcp(tmp_path: Path) -> None:
    policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode="review",
                reason="Synthetic parity fixture enables generic peer assignment review",
            ),
        )
    )
    root, _ = synthetic_design_lint_project(tmp_path, policy)
    summary_path = root / "build/native/controller/summary.json"
    netlist_path = summary_path.parent / "netlist.xml"

    async def inspect_mcp() -> tuple[DesignLintReport, DesignLintReport]:
        async with Client(create_server(root), mode="legacy") as client:
            reports: list[DesignLintReport] = []
            for assignments, expected_finding in (
                (("DATA_A", "DATA_A", "DATA_B"), True),
                (("DATA_A", "DATA_A", "DATA_A"), False),
            ):
                observed = peer_component_pin_netlist(
                    references=("U1", "U2", "U3"),
                    pin_nets=assignments,
                    default_symbol="Synthetic:GenericPeer",
                    pin_electrical_types=("passive", "passive", "passive"),
                    pin_function="Pin_2",
                )
                netlist_path.write_text(peer_pin_netlist_xml(observed), encoding="utf-8")
                summary = read_model(summary_path, ValidationSummary)
                write_model(
                    summary_path,
                    summary.model_copy(
                        update={
                            "artifacts_sha256": {
                                **summary.artifacts_sha256,
                                "netlist.xml": digest(netlist_path),
                            }
                        }
                    ),
                )

                process = run_design_lint_cli(tmp_path, root, summary_path)
                assert process.returncode in {0, 1}, process.stderr + process.stdout
                cli_report = DesignLintReport.model_validate_json(process.stdout)
                result = await client.call_tool(
                    "inspect_design_lint",
                    {
                        "project_id": "controller",
                        "native_summary": summary_path.relative_to(root).as_posix(),
                    },
                )
                assert not result.is_error, result.content
                assert result.structured_content is not None
                mcp_report = DesignLintReport.model_validate_json(
                    json.dumps(result.structured_content)
                )
                assert semantic_design_lint_report(cli_report) == semantic_design_lint_report(
                    mcp_report
                )
                findings = [item for item in mcp_report.findings if item.rule_id == RULE_ID]
                assert len(findings) == int(expected_finding)
                if findings:
                    assert findings[0].evidence["majority_net"] == ("DATA_A",)
                    assert findings[0].evidence["outlier_pins"] == ("U3.2",)
                reports.append(mcp_report)
            return reports[0], reports[1]

    fault, control = asyncio.run(inspect_mcp())
    assert (
        next(
            item for item in fault.component_peer_pin_coverage if item.rule_id == RULE_ID
        ).finding_count
        == 1
    )
    assert (
        next(
            item for item in control.component_peer_pin_coverage if item.rule_id == RULE_ID
        ).finding_count
        == 0
    )
