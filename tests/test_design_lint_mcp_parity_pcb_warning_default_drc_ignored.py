"""CLI/MCP parity for ignored Warning-default PCB DRC checks."""

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
from tests.synthetic_design_lint_project import (
    run_design_lint_cli,
    synthetic_design_lint_project,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.parity_lint,
    pytest.mark.slow,
]

SETTINGS = (
    Path(__file__).parent / "fixtures/design_lint/pcb-warning-default-drc-ignored/fault.kicad_pro"
)
RULE_ID = "pcb.warning_default_drc_check_ignored"


def test_warning_default_drc_findings_match_between_cli_and_mcp(tmp_path: Path) -> None:
    root, native = synthetic_design_lint_project(
        tmp_path,
        parity_design_lint_policy(DesignLintPolicy()),
        project_settings_source=SETTINGS.read_text(encoding="utf-8"),
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
    findings = tuple(item for item in mcp_report.findings if item.rule_id == RULE_ID)
    assert tuple(item.evidence["check_id"][0] for item in findings) == (
        "connection_width",
        "copper_sliver",
        "duplicate_footprints",
        "extra_footprint",
        "hole_to_hole",
        "holes_co_located",
        "isolated_copper",
        "lib_footprint_issues",
        "lib_footprint_mismatch",
        "mirrored_text_on_front_layer",
        "missing_footprint",
        "missing_tuning_profile",
        "net_conflict",
        "nonmirrored_text_on_back_layer",
        "padstack",
        "schematic_fields_parity",
        "schematic_parity",
        "silk_edge_clearance",
        "silk_over_copper",
        "silk_overlap",
        "text_height",
        "text_thickness",
        "track_dangling",
        "via_dangling",
    )
    assert all(item.mode == "review" and item.disposition == "OPEN" for item in findings)
