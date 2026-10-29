"""CLI/MCP parity for the unanchored same-voltage connector power-input rule."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from mcp import Client

from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    ConnectorInterfaceReview,
    ConnectorInventoryReview,
    DesignLintPolicy,
    DesignLintRuleOverride,
    ProjectManifest,
    ValidationSummary,
)
from tests.component_peer_power_assignment_support import peer_pin_netlist_xml
from tests.connector_footprint_peer_support import peer_netlist
from tests.mcp_parity_support import semantic_design_lint_report
from tests.synthetic_design_lint_project import (
    run_design_lint_cli,
    synthetic_design_lint_project,
)

pytestmark = [
    pytest.mark.parity_lint,
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.power_lint,
]

RULE_ID = "connector.footprint_same_voltage_power_input_unanchored"


def test_unanchored_same_voltage_power_input_matches_cli_and_mcp(tmp_path: Path) -> None:
    policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode="review",
                reason="Synthetic parity case explicitly enables this heuristic.",
            ),
        )
    )
    root, summary_path = synthetic_design_lint_project(tmp_path, policy)
    manifest_path = root / "projects/controller/project.json"
    manifest = read_model(manifest_path, ProjectManifest)
    write_model(
        manifest_path,
        manifest.model_copy(
            update={
                "connector_inventory_review": ConnectorInventoryReview(
                    basis="Synthetic parity fixture reviews both connector symbols."
                ),
                "connector_reviews": tuple(
                    ConnectorInterfaceReview(
                        reference=reference,
                        disposition="not_applicable",
                        basis="Synthetic regression symbols are not board interfaces.",
                    )
                    for reference in ("J1", "J2")
                ),
            }
        ),
    )
    observed = peer_netlist(
        assignments=(
            ("PORT_A", "PORT_B"),
            ("+3V3", "3.3V"),
        ),
        functions=("UART_TX", "BIAS_IN"),
        electrical_types=("output", "power_in"),
    )
    netlist_path = summary_path.parent / "netlist.xml"
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

    process = run_design_lint_cli(tmp_path, root, summary_path)
    assert process.returncode in {0, 1}, process.stderr + process.stdout
    cli_report = DesignLintReport.model_validate_json(process.stdout)
    mcp_report = asyncio.run(inspect_mcp())
    assert semantic_design_lint_report(cli_report) == semantic_design_lint_report(mcp_report)
    findings = tuple(item for item in cli_report.findings if item.rule_id == RULE_ID)
    assert len(findings) == 1
    assert findings[0].evidence["assignments"] == ("J1.2=+3V3", "J2.2=3.3V")
    assert findings[0].evidence["nominal_voltage_v"] == ("3.3",)
