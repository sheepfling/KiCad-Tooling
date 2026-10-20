"""CLI and MCP parity for named passive connector divergence review."""

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
from tests.connector_footprint_peer_support import named_passive_contact_divergence_netlist
from tests.mcp_parity_support import semantic_design_lint_report
from tests.synthetic_design_lint_project import (
    run_design_lint_cli,
    synthetic_design_lint_project,
)

pytestmark = [
    pytest.mark.parity_lint,
    pytest.mark.slow,
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.interface_lint,
]

RULE_ID = "connector.footprint_named_passive_assignment_divergence"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_named_passive_divergence_matches_cli_and_mcp(tmp_path: Path) -> None:
    overrides = (
        ("pcb.schematic_component_inventory", "Synthetic input has no PCB snapshot."),
        ("pcb.schematic_pcb_dnp_mismatch", "Synthetic input has no PCB snapshot."),
        ("pcb.schematic_pcb_value_mismatch", "Synthetic input has no PCB snapshot."),
        ("pcb.schematic_pcb_pad_net_mismatch", "Synthetic input has no PCB snapshot."),
        ("protection.unreviewed_interface_pin", "Synthetic fixture isolates peer review."),
    )
    policy = DesignLintPolicy(
        rules=(
            *(
                DesignLintRuleOverride(rule_id=rule_id, mode="off", reason=reason)
                for rule_id, reason in overrides
            ),
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode="review",
                reason="Synthetic parity fixture opts in to passive-contact divergence review.",
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
                    basis="Synthetic fixture reviews both connector symbols."
                ),
                "connector_reviews": tuple(
                    ConnectorInterfaceReview(
                        reference=reference,
                        disposition="not_applicable",
                        basis="Synthetic symbols are not board interfaces.",
                    )
                    for reference in ("J1", "J2")
                ),
            }
        ),
    )
    summary = read_model(summary_path, ValidationSummary)
    netlist_path = summary_path.parent / "netlist.xml"
    cases = (
        (named_passive_contact_divergence_netlist(), "REVIEW", 1),
        (
            named_passive_contact_divergence_netlist(target_assignments=("AUX", "AUX")),
            "PASS",
            0,
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

    for observed, expected_status, expected_findings in cases:
        netlist_path.write_text(peer_pin_netlist_xml(observed), encoding="utf-8")
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
        mcp_report = asyncio.run(inspect_mcp())

        assert semantic_design_lint_report(cli_report) == semantic_design_lint_report(mcp_report)
        assert cli_report.status == expected_status
        assert sum(item.rule_id == RULE_ID for item in cli_report.findings) == expected_findings
        coverage = cli_report.connector_peer_pin_coverage
        assert coverage is not None
        assert coverage.footprint_alias_coverage.named_passive_divergence_finding_count == (
            expected_findings
        )
