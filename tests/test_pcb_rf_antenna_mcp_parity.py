"""Pytest CLI/MCP parity for the project-mapped RF antenna coverage service."""

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
    PcbRfModuleAntennaMap,
)
from tests.synthetic_design_lint_project import (
    run_design_lint_cli,
    synthetic_design_lint_project,
)
from tests.test_pcb_rf_antenna import requirement


def test_disabled_rf_antenna_coverage_matches_cli_and_mcp(tmp_path: Path) -> None:
    rf_map = PcbRfModuleAntennaMap(
        basis="Synthetic RF module coverage disabled for parity control",
        requirements=(requirement(),),
    )
    policy = DesignLintPolicy(
        pcb_rf_module_antenna_map=rf_map,
        rules=(
            DesignLintRuleOverride(
                rule_id="pcb.rf_module_antenna_keepout_coverage",
                mode="off",
                reason="Synthetic parity fixture disables RF antenna review",
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
    assert mcp_report.pcb_rf_module_antenna_coverage.status == "DISABLED"
    assert (
        mcp_report.pcb_rf_module_antenna_coverage.map_sha256
        == hashlib.sha256(rf_map.model_dump_json().encode("utf-8")).hexdigest()
    )
