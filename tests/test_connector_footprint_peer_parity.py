"""CLI/MCP parity for configurable footprint-alias connector peer review."""

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
    ComponentContract,
    ConnectorInterfaceReview,
    ConnectorInventoryReview,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
    ProjectManifest,
    ValidationSummary,
)
from tests.component_peer_power_assignment_support import peer_pin_netlist_xml
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
]

RULE_ID = "connector.footprint_peer_pin_assignment_divergence"
OPEN_RULE_ID = "connector.footprint_peer_pin_open_outlier"


def _observed(
    *,
    fault: bool,
    open_peer: bool = False,
    functions: tuple[str, str] = ("Pin_1", "Pin_2"),
) -> NetlistContract:
    components = {
        reference: ComponentContract(
            value="Synthetic two-contact connector",
            footprint="Synthetic:Connector_2x1",
        )
        for reference in ("J1", "J2")
    }
    return NetlistContract(
        components=components,
        nets={
            "SYNTHETIC_GROUND": ("J1.1", "J2.1"),
            "SYNTHETIC_SIGNAL_A": ("J1.2",),
            **({"SYNTHETIC_SIGNAL_B": ("J2.2",)} if fault and not open_peer else {}),
            **({"SYNTHETIC_SIGNAL_A": ("J1.2", "J2.2")} if not fault and not open_peer else {}),
        },
        component_symbols={
            "J1": "Synthetic:GenericPort",
            "J2": "Synthetic:GenericPortAlias",
        },
        component_pin_numbers={"J1": ("1", "2"), "J2": ("1", "2")},
        pin_functions={
            "J1.1": functions[0],
            "J1.2": functions[1],
            "J2.1": functions[0],
            "J2.2": functions[1],
        },
        pin_electrical_types={
            "J1.1": "passive",
            "J1.2": "passive",
            "J2.1": "passive",
            "J2.2": "passive",
        },
    )


def test_footprint_alias_review_matches_cli_and_mcp(tmp_path: Path) -> None:
    off_rules = tuple(
        DesignLintRuleOverride(rule_id=rule_id, mode="off", reason=reason)
        for rule_id, reason in (
            ("pcb.schematic_component_inventory", "Synthetic fixture has no PCB snapshot."),
            ("pcb.schematic_pcb_dnp_mismatch", "Synthetic fixture has no PCB snapshot."),
            ("pcb.schematic_pcb_value_mismatch", "Synthetic fixture has no PCB snapshot."),
            ("pcb.schematic_pcb_pad_net_mismatch", "Synthetic fixture has no PCB snapshot."),
            ("protection.unreviewed_interface_pin", "Synthetic fixture isolates peer review."),
        )
    )
    policy = DesignLintPolicy(
        rules=(
            *off_rules,
            DesignLintRuleOverride(
                rule_id=RULE_ID,
                mode="review",
                reason="Synthetic parity fixture explicitly opts in to this heuristic.",
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
    netlist_path = summary_path.parent / "netlist.xml"
    summary = read_model(summary_path, ValidationSummary)

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

    for fault, open_peer, functions, rule_id, expected_status, expected_findings in (
        (True, False, ("Pin_1", "Pin_2"), RULE_ID, "REVIEW", 1),
        (False, False, ("Pin_1", "Pin_2"), RULE_ID, "PASS", 0),
        (False, True, ("Pin_1", "Pin_2"), OPEN_RULE_ID, "REVIEW", 1),
        (False, False, ("Pin_1", "Pin_2"), OPEN_RULE_ID, "PASS", 0),
        (True, False, ("1", "7"), RULE_ID, "REVIEW", 1),
        (False, False, ("1", "7"), RULE_ID, "PASS", 0),
        (False, True, ("1", "7"), OPEN_RULE_ID, "REVIEW", 1),
    ):
        observed = _observed(fault=fault, open_peer=open_peer, functions=functions)
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
        assert cli_report.status == expected_status, cli_report.issues
        findings = tuple(item for item in cli_report.findings if item.rule_id == rule_id)
        assert len(findings) == expected_findings
        coverage = cli_report.connector_peer_pin_coverage
        assert coverage is not None
        alias = coverage.footprint_alias_coverage
        assert alias.netlist_sha256 == digest(netlist_path)
        if rule_id == RULE_ID:
            assert alias.divergence_finding_count == expected_findings
        else:
            assert alias.open_outlier_finding_count == expected_findings
