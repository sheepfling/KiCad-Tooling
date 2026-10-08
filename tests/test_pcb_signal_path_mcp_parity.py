"""Pytest CLI/MCP parity for mapped PCB signal-path policy."""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path

from mcp import Client

from kicad_tooling.hwrepo.contracts import parse_model_text
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    DesignLintPolicy,
    DesignLintReport,
    DesignLintRuleOverride,
)
from tests.synthetic_design_lint_project import (
    run_design_lint_cli,
    synthetic_design_lint_project,
)
from tests.test_pcb_signal_path_coverage import path_map


def test_disabled_signal_path_coverage_matches_cli_and_mcp(tmp_path: Path) -> None:
    requirements = path_map()
    policy = DesignLintPolicy(
        pcb_signal_path_rule_map=requirements,
        rules=(
            DesignLintRuleOverride(
                rule_id="pcb.signal_path_rule_coverage",
                mode="off",
                reason="Synthetic parity fixture disables route review",
            ),
        ),
    )
    root, native = synthetic_design_lint_project(tmp_path, policy)
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
    assert cli_report == mcp_report
    assert mcp_report.pcb_signal_path_rules.status == "DISABLED"
    assert (
        mcp_report.pcb_signal_path_rules.map_sha256
        == hashlib.sha256(requirements.model_dump_json().encode("utf-8")).hexdigest()
    )
