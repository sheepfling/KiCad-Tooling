"""CLI/MCP parity for source-bound custom DRC no-constraint review."""

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
RULE_ID = "pcb.custom_drc_rule_without_constraint"
IMPLEMENTATION_OWNER = (
    "kicad_tooling/hwrepo/pcb_dru_rule_review.py#custom_drc_rule_without_constraint_candidates"
)
FIXTURE = (
    Path(__file__).parent
    / "fixtures/design_lint/pcb-dru-rule-without-constraint/fault-no-constraint.kicad_dru"
)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_unconstrained_custom_rule_review_matches_cli_and_mcp(tmp_path: Path) -> None:
    root, native = synthetic_design_lint_project(
        tmp_path,
        parity_design_lint_policy(DesignLintPolicy()),
        custom_rules_source=FIXTURE.read_text(encoding="utf-8"),
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
    assert mcp_report.rule_catalog is not None
    rule = next(item for item in mcp_report.rule_catalog.rules if item.rule_id == RULE_ID)
    assert rule.implementation_owner == IMPLEMENTATION_OWNER
    finding = next(item for item in mcp_report.findings if item.rule_id == RULE_ID)
    assert finding.mode == "review" and finding.disposition == "OPEN"
    assert finding.evidence["constraint_count"] == ("0",)
    assert finding.evidence["source_sha256"] == (
        mcp_report.source_hashes["projects/controller/kicad/controller.kicad_dru"],
    )
