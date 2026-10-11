"""CLI and MCP parity for generic open power-output review findings."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from mcp import Client

pytestmark = [
    pytest.mark.parity_lint,
    pytest.mark.slow,
    pytest.mark.design_lint,
    pytest.mark.component_lint,
    pytest.mark.power_lint,
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
from tests.mcp_parity_support import semantic_design_lint_report
from tests.synthetic_design_lint_project import (
    run_design_lint_cli,
    synthetic_design_lint_project,
)


def test_generic_power_output_review_cli_mcp_parity(tmp_path: Path) -> None:
    policy = DesignLintPolicy(
        rules=(
            DesignLintRuleOverride(
                rule_id="pcb.schematic_component_inventory",
                mode="off",
                reason="Synthetic parity fixture isolates the power-output heuristic",
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
                    basis="Synthetic power-output parity case contains no external connector"
                )
            }
        ),
    )
    netlist = native.parent / "netlist.xml"
    summary = read_model(native, ValidationSummary)

    def write_netlist(connected: bool) -> None:
        output = '<net name="POWER_OUTPUT_TEST"><node ref="U1" pin="1"/></net>' if connected else ""
        netlist.write_text(
            "<export><components>"
            '<comp ref="U1"><value>Synthetic component</value>'
            "<footprint>Synthetic:Component</footprint>"
            '<libsource lib="Synthetic" part="GenericPowerOutputComponent"/>'
            "</comp></components><libparts>"
            '<libpart lib="Synthetic" part="GenericPowerOutputComponent"><pins>'
            '<pin num="1" name="1" type="power_out"/>'
            '<pin num="2" name="2" type="passive"/>'
            "</pins></libpart></libparts><nets>"
            '<net name="SIGNAL"><node ref="U1" pin="2"/></net>'
            f"{output}</nets></export>",
            encoding="utf-8",
        )
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

    for connected, expected_status, expected_rule_ids in (
        (False, "REVIEW", {"component.unconnected_power_output"}),
        (True, "PASS", set()),
    ):
        write_netlist(connected)
        process = run_design_lint_cli(tmp_path, root, native)
        assert process.returncode in {0, 1}, process.stderr + process.stdout
        cli = parse_model_text(process.stdout, DesignLintReport)
        mcp = asyncio.run(inspect_mcp())

        assert semantic_design_lint_report(cli) == semantic_design_lint_report(mcp)
        assert cli.status == expected_status, (cli.issues, [item.rule_id for item in cli.findings])
        assert {item.rule_id for item in cli.findings} == expected_rule_ids
