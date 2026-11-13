"""CLI/MCP parity for netclass patterns with no current board-net match."""

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

RULE_ID = "pcb.drc_netclass_pattern_unmatched"
FIXTURE_DIR = Path(__file__).parent / "fixtures/design_lint/pcb-drc-duplicate-net-settings"
BOARD_FIXTURE = FIXTURE_DIR / "board.kicad_pcb"
pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.parity_lint,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


@pytest.mark.parametrize(
    ("settings_name", "expected_pattern"),
    (
        ("fault-unmatched.kicad_pro", "GHOST"),
        ("fault-case-mismatch.kicad_pro", "n1"),
        ("control-literal.kicad_pro", None),
        ("control-wildcard.kicad_pro", None),
        ("control-regex.kicad_pro", None),
    ),
)
def test_netclass_pattern_review_matches_between_cli_and_mcp(
    tmp_path: Path,
    settings_name: str,
    expected_pattern: str | None,
) -> None:
    root, native = synthetic_design_lint_project(
        tmp_path,
        parity_design_lint_policy(DesignLintPolicy()),
        kicad_version="10.0.8",
        image="registry.invalid/kicad:10.0.8@sha256:" + "b" * 64,
        project_settings_source=(FIXTURE_DIR / settings_name).read_text(encoding="utf-8"),
        board_source=BOARD_FIXTURE.read_text(encoding="utf-8"),
    )
    process = run_design_lint_cli(tmp_path, root, native)
    assert process.returncode in {0, 1}, process.stderr + process.stdout
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
    assert len(findings) == (1 if expected_pattern is not None else 0)
    if expected_pattern is not None:
        assert findings[0].subject.endswith("#net_settings/netclass_patterns/0")
        assert findings[0].evidence["pattern"] == (expected_pattern,)
