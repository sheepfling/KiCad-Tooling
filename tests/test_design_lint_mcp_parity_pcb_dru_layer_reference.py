"""CLI and MCP share custom DRC layer-reference review evidence."""

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

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.evidence_lint,
    pytest.mark.parity_lint,
    pytest.mark.slow,
]
RULE_ID = "pcb.custom_drc_layer_reference"
IMPLEMENTATION_OWNER = (
    "kicad_tooling/hwrepo/pcb_dru_layer_review.py#custom_drc_layer_reference_candidates"
)
FIXTURE = (
    Path(__file__).parent
    / "fixtures/design_lint/pcb-dru-layer-reference/fault-display-alias.kicad_dru"
)
BOARD_FIXTURE = (
    Path(__file__).parents[1]
    / "kicad_tooling/hwrepo/fixtures/pcb-dru-rule-compilation-probe.kicad_pcb"
)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_custom_drc_layer_review_matches_cli_and_mcp(tmp_path: Path) -> None:
    root, native = synthetic_design_lint_project(
        tmp_path,
        parity_design_lint_policy(DesignLintPolicy()),
        custom_rules_source=FIXTURE.read_text(encoding="utf-8"),
        board_source=BOARD_FIXTURE.read_text(encoding="utf-8"),
    )
    process = run_design_lint_cli(tmp_path, root, native)
    assert process.returncode == 1, process.stderr + process.stdout
    cli_report = parse_model_text(process.stdout, DesignLintReport)

    async def inspect_mcp() -> DesignLintReport:
        async with Client(create_server(root), mode="legacy") as client:
            result = await client.call_tool(
                "inspect_design_lint",
                {"project_id": "controller", "native_summary": native.relative_to(root).as_posix()},
            )
            assert not result.is_error, result.content
            assert result.structured_content is not None
            return DesignLintReport.model_validate_json(json.dumps(result.structured_content))

    mcp_report = asyncio.run(inspect_mcp())
    assert semantic_design_lint_report(cli_report) == semantic_design_lint_report(mcp_report)
    assert mcp_report.status == "REVIEW", mcp_report.issues
    assert mcp_report.rule_catalog is not None
    catalog_rule = next(rule for rule in mcp_report.rule_catalog.rules if rule.rule_id == RULE_ID)
    assert catalog_rule.implementation_owner == IMPLEMENTATION_OWNER
    findings = tuple(item for item in mcp_report.findings if item.rule_id == RULE_ID)
    assert len(findings) == 3
    assert all(item.mode == "review" and item.disposition == "OPEN" for item in findings)
    assert all(
        item.evidence["source_sha256"]
        == (mcp_report.source_hashes["projects/controller/kicad/controller.kicad_dru"],)
        for item in findings
    )
    assert all(
        item.evidence["board_sha256"]
        == (mcp_report.source_hashes["projects/controller/kicad/controller.kicad_pcb"],)
        for item in findings
    )
