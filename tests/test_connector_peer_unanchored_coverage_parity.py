"""CLI/MCP parity for unanchored partial-open connector alias coverage."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from mcp import Client

from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import DesignLintPolicy, DesignLintReport, ValidationSummary
from tests.mcp_parity_support import semantic_design_lint_report
from tests.pcb_drc_parity_support import install_source_bound_drc_receipt
from tests.synthetic_design_lint_project import run_design_lint_cli, synthetic_design_lint_project

RULE_ID = "connector.footprint_peer_unanchored_scope_coverage_missing"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.parity_lint,
    pytest.mark.slow,
]


def test_unanchored_partial_open_connector_coverage_matches_cli_and_mcp(
    tmp_path: Path,
) -> None:
    root, native = synthetic_design_lint_project(tmp_path, DesignLintPolicy())
    install_source_bound_drc_receipt(root, native)
    netlist = native.parent / "netlist.xml"
    summary = read_model(native, ValidationSummary)
    fixture_root = Path(__file__).parent / "fixtures/design_lint/connector-peer-unanchored-scope"

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

    def run_case(fixture_name: str) -> tuple[DesignLintReport, DesignLintReport]:
        netlist.write_text(
            (fixture_root / fixture_name).read_text(encoding="utf-8"), encoding="utf-8"
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
        process = run_design_lint_cli(tmp_path, root, native)
        assert process.returncode in {0, 1}, process.stderr + process.stdout
        return DesignLintReport.model_validate_json(process.stdout), asyncio.run(inspect_mcp())

    fault_cli, fault_mcp = run_case("partial-open-netlist.xml")
    control_cli, control_mcp = run_case("partial-open-anchor-control-netlist.xml")
    split_fault_cli, split_fault_mcp = run_case("partial-open-divergent-netlist.xml")
    split_control_cli, split_control_mcp = run_case(
        "partial-open-divergent-anchor-control-netlist.xml"
    )
    fault_cli_findings = tuple(item for item in fault_cli.findings if item.rule_id == RULE_ID)
    fault_mcp_findings = tuple(item for item in fault_mcp.findings if item.rule_id == RULE_ID)
    control_cli_findings = tuple(item for item in control_cli.findings if item.rule_id == RULE_ID)
    control_mcp_findings = tuple(item for item in control_mcp.findings if item.rule_id == RULE_ID)
    split_fault_cli_findings = tuple(
        item for item in split_fault_cli.findings if item.rule_id == RULE_ID
    )
    split_fault_mcp_findings = tuple(
        item for item in split_fault_mcp.findings if item.rule_id == RULE_ID
    )
    split_control_cli_findings = tuple(
        item for item in split_control_cli.findings if item.rule_id == RULE_ID
    )
    split_control_mcp_findings = tuple(
        item for item in split_control_mcp.findings if item.rule_id == RULE_ID
    )

    assert semantic_design_lint_report(fault_cli) == semantic_design_lint_report(fault_mcp)
    assert fault_cli_findings == fault_mcp_findings
    assert len(fault_cli_findings) == 1
    assert fault_cli_findings[0].evidence["unanchored_partial_open_pin_numbers"] == ("1",)
    assert semantic_design_lint_report(control_cli) == semantic_design_lint_report(control_mcp)
    assert control_cli_findings == control_mcp_findings == ()
    assert semantic_design_lint_report(split_fault_cli) == semantic_design_lint_report(
        split_fault_mcp
    )
    assert split_fault_cli_findings == split_fault_mcp_findings
    assert len(split_fault_cli_findings) == 1
    assert split_fault_cli_findings[0].evidence["references"] == ("J1", "J2", "J3")
    assert split_fault_cli_findings[0].evidence["unanchored_partial_open_pin_numbers"] == ("1",)
    assert semantic_design_lint_report(split_control_cli) == semantic_design_lint_report(
        split_control_mcp
    )
    assert split_control_cli_findings == split_control_mcp_findings == ()
