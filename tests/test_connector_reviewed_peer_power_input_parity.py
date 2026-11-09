"""CLI/MCP parity for reviewed heterogeneous connector power-input splits."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from mcp import Client

from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    ConnectorInventoryReview,
    DesignLintPolicy,
    DesignLintReport,
    DesignLintRuleOverride,
    ProjectManifest,
)
from tests.component_peer_power_assignment_support import peer_pin_netlist_xml
from tests.design_lint_fixtures.connector_reviewed_peer_power_input import (
    power_input_netlist,
    power_input_project_documents,
)
from tests.mcp_parity_support import semantic_design_lint_report
from tests.synthetic_design_lint_project import (
    install_synthetic_netlist,
    run_design_lint_cli,
    synthetic_design_lint_project,
)

pytestmark = [
    pytest.mark.parity_lint,
    pytest.mark.slow,
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.power_lint,
]

RULE_ID = "connector.reviewed_peer_power_input_split"
PASSIVE_OPEN_RULE_ID = "connector.reviewed_peer_passive_power_input_open"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.design_lint_rule(rule_id=PASSIVE_OPEN_RULE_ID)
def test_reviewed_peer_power_input_split_matches_between_cli_and_mcp(tmp_path: Path) -> None:
    policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode="review",
                reason="Synthetic parity case explicitly enables this heuristic.",
            ),
            DesignLintRuleOverride(
                rule_id=PASSIVE_OPEN_RULE_ID,
                mode="review",
                reason="Synthetic parity case explicitly enables this heuristic.",
            ),
        )
    )
    root, summary_path = synthetic_design_lint_project(tmp_path, policy)
    manifest_path = root / "projects/controller/project.json"
    manifest = read_model(manifest_path, ProjectManifest)
    cases = (
        (power_input_netlist(), (None, None), True, False),
        (
            power_input_netlist(electrical_type="passive"),
            (None, None),
            True,
            False,
        ),
        (
            power_input_netlist(
                electrical_type="passive", power_assignments=("COMMON_5V", "COMMON_5V")
            ),
            (None, None),
            False,
            False,
        ),
        (
            power_input_netlist(electrical_type="passive", power_assignments=("USB_5V", None)),
            (None, None),
            False,
            True,
        ),
        (
            power_input_netlist(electrical_type="passive", power_assignments=("USB_5V", None)),
            (None, "intentionally open"),
            False,
            False,
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

    for observed, open_reasons, expected_split, expected_passive_open in cases:
        interface_catalog, project_interfaces, connector_reviews = power_input_project_documents(
            unconnected_pin_reasons=open_reasons
        )
        write_model(root / "catalog/interfaces.json", interface_catalog)
        write_model(
            manifest_path,
            manifest.model_copy(
                update={
                    "interfaces": project_interfaces,
                    "connector_reviews": connector_reviews,
                    "connector_inventory_review": ConnectorInventoryReview(
                        basis="Synthetic parity fixture inventories both unlike connector peers."
                    ),
                }
            ),
        )
        install_synthetic_netlist(summary_path, peer_pin_netlist_xml(observed))

        process = run_design_lint_cli(tmp_path, root, summary_path)
        assert process.returncode in {0, 1}, process.stderr + process.stdout
        cli_report = DesignLintReport.model_validate_json(process.stdout)
        mcp_report = asyncio.run(inspect_mcp())
        assert semantic_design_lint_report(cli_report) == semantic_design_lint_report(mcp_report)
        split_findings = tuple(item for item in cli_report.findings if item.rule_id == RULE_ID)
        passive_open_findings = tuple(
            item for item in cli_report.findings if item.rule_id == PASSIVE_OPEN_RULE_ID
        )
        assert bool(split_findings) is expected_split
        assert bool(passive_open_findings) is expected_passive_open
        if split_findings:
            assert split_findings[0].evidence["assignments"] == (
                "J1.1=USB_5V",
                "J2.1=SERIAL_5V",
            )
        if passive_open_findings:
            assert passive_open_findings[0].evidence["assignments"] == (
                "J1.1=USB_5V",
                "J2.1=<unassigned>",
            )
