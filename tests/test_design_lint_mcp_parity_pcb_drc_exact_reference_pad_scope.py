"""CLI/MCP parity for exact custom DRC footprint-reference-and-pad selectors."""

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
from tests.pcb_drc_parity_support import install_source_bound_drc_receipt
from tests.synthetic_design_lint_project import (
    run_design_lint_cli,
    synthetic_design_lint_project,
)

RULE_ID = "pcb.drc_exact_reference_pad_scope_unmatched"
FIXTURE_DIR = Path(__file__).parent / "fixtures/design_lint/pcb-drc-exact-reference-pad-scope"
BOARD = (
    Path(__file__).parent / "fixtures/design_lint/pcb-mechanical-edge-clearance/control.kicad_pcb"
)
PROJECT = (
    Path(__file__).parent / "fixtures/design_lint/pcb-mechanical-edge-clearance/board.kicad_pro"
)
pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.parity_lint,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


@pytest.mark.parametrize(
    ("rules_name", "board_pad", "expected_pad"),
    (("absent-pad", "1", "9"), ("present", "1", None), ("pad-uppercase", "A1", None)),
)
def test_unmatched_exact_reference_pad_scope_matches_between_cli_and_mcp(
    tmp_path: Path,
    rules_name: str,
    board_pad: str,
    expected_pad: str | None,
) -> None:
    board_source = BOARD.read_text(encoding="utf-8").replace(
        '(pad "1" smd', f'(pad "{board_pad}" smd'
    )
    root, native = synthetic_design_lint_project(
        tmp_path,
        parity_design_lint_policy(DesignLintPolicy()),
        kicad_version="10.0.5",
        custom_rules_source=(FIXTURE_DIR / f"{rules_name}.kicad_dru").read_text(encoding="utf-8"),
        project_settings_source=PROJECT.read_text(encoding="utf-8"),
        board_source=board_source,
    )
    install_source_bound_drc_receipt(root, native)
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
    assert len(findings) == (1 if expected_pad is not None else 0)
    if expected_pad is not None:
        assert findings[0].evidence["pad_number_selectors"] == (expected_pad,)
