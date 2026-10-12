"""CLI and MCP parity for named power-pin net-role review findings."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from mcp import Client

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.power_lint,
    pytest.mark.component_lint,
    pytest.mark.parity_lint,
    pytest.mark.slow,
]

from kicad_tooling.hwrepo.contracts import parse_model_text, read_model, write_model
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    ConnectorInventoryReview,
    DesignLintPolicy,
    DesignLintReport,
    DesignLintRuleOverride,
    ProjectManifest,
    ValidationSummary,
)
from tests.design_lint_fixtures.power_pin_net_roles import positive_supply_on_return_netlist
from tests.electrical_parity_support import contract_netlist_xml
from tests.mcp_parity_support import semantic_design_lint_report
from tests.synthetic_design_lint_project import (
    run_design_lint_cli,
    synthetic_design_lint_project,
)


def test_named_power_pin_net_role_review_cli_mcp_parity(tmp_path: Path) -> None:
    policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id="power.ic_rail_without_fitted_capacitor",
                mode="off",
                reason="Synthetic parity case isolates a pin-role conflict",
            ),
            DesignLintRuleOverride(
                rule_id="pcb.schematic_component_inventory",
                mode="off",
                reason="Synthetic parity fixture has no physical board inventory",
            ),
        )
    )
    root, native = synthetic_design_lint_project(tmp_path, policy)
    manifest_path = root / "projects/controller/project.json"
    manifest = read_model(manifest_path, ProjectManifest)
    write_model(
        manifest_path,
        manifest.model_copy(
            update={
                "connector_inventory_review": ConnectorInventoryReview(
                    basis="Synthetic parity case contains no external connector"
                )
            }
        ),
    )
    netlist = native.parent / "netlist.xml"
    summary = read_model(native, ValidationSummary)
    netlist.write_text(contract_netlist_xml(positive_supply_on_return_netlist()), encoding="utf-8")
    write_model(
        native,
        summary.model_copy(
            update={
                "artifacts_sha256": {
                    **summary.artifacts_sha256,
                    "netlist.xml": digest(netlist),
                }
            }
        ),
    )

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
    assert cli.status == mcp.status == "REVIEW"
    findings = [
        item for item in cli.findings if item.rule_id == "power.pin_function_net_role_conflict"
    ]
    assert len(findings) == 1
    assert findings[0].subject == "U1.1: VDD pin assigned to GND"
