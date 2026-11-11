"""CLI/MCP parity for unverified schematic ERC catalog review."""

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

RULE_ID = "schematic.erc_catalog_unverified"
SETTINGS = (
    Path(__file__).parent / "fixtures/design_lint/schematic-erc-global-severity/unknown.kicad_pro"
)
pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.schematic_lint,
    pytest.mark.evidence_lint,
    pytest.mark.parity_lint,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def test_unverified_erc_catalog_review_matches_between_cli_and_mcp(tmp_path: Path) -> None:
    root, native = synthetic_design_lint_project(
        tmp_path,
        parity_design_lint_policy(DesignLintPolicy()),
        project_settings_source=SETTINGS.read_text(encoding="utf-8"),
        kicad_version="10.0.3",
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
    findings = [item for item in mcp_report.findings if item.rule_id == RULE_ID]
    assert len(findings) == 1
    finding = findings[0]
    assert finding.mode == "review" and finding.disposition == "OPEN"
    assert finding.evidence["kicad_version"] == ("10.0.3",)
    assert finding.evidence["erc_rule_key"] == (
        "future_rule",
        "pin_not_conected",
        "pin_not_connected",
        "vendor_future_key",
    )
    assert finding.evidence["source_sha256"] == (
        mcp_report.source_hashes["projects/controller/kicad/controller.kicad_pro"],
    )
