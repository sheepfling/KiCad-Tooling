"""CLI/MCP parity for the source-bound embedded-symbol integrity review."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from mcp import Client

from kicad_tooling.hwrepo.contracts import parse_model_text
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import DesignLintPolicy, DesignLintReport
from tests.mcp_parity_support import parity_design_lint_policy, semantic_design_lint_report
from tests.synthetic_design_lint_project import run_design_lint_cli, synthetic_design_lint_project

RULE_ID = "schematic.missing_embedded_symbol_definition"
FAULT = (
    Path(__file__).parent
    / "fixtures/design_lint/missing-embedded-symbol-definition/fault.kicad_sch"
)
pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.schematic_lint,
    pytest.mark.parity_lint,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def test_missing_embedded_symbol_review_matches_between_cli_and_mcp(tmp_path: Path) -> None:
    root, native = synthetic_design_lint_project(
        tmp_path,
        parity_design_lint_policy(DesignLintPolicy()),
        schematic_source=FAULT.read_bytes(),
    )
    process = run_design_lint_cli(tmp_path, root, native)
    assert process.returncode == 1, process.stderr + process.stdout
    cli_report = parse_model_text(process.stdout, DesignLintReport)

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

    mcp_report = asyncio.run(inspect_mcp())

    assert semantic_design_lint_report(cli_report) == semantic_design_lint_report(mcp_report)
    assert mcp_report.status == "REVIEW", mcp_report.issues
    findings = [item for item in mcp_report.findings if item.rule_id == RULE_ID]
    assert len(findings) == 1
    assert findings[0].subject.endswith(":J1")
    assert findings[0].evidence["library_id"] == ("Connector:USB_A",)
