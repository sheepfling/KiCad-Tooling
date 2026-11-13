"""CLI and MCP expose the same source-bound track-angle coverage finding."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from mcp import Client

from kicad_tooling.hwrepo.command_evidence_models import CommandEvidence
from kicad_tooling.hwrepo.contracts import parse_model_text, read_model, write_model
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.native_project_validation_models import (
    CheckEvidence,
    ValidationSummary,
)
from kicad_tooling.hwrepo.pcb_track_angle_models import (
    PcbTrackAngleMap,
    PcbTrackAngleRequirement,
)
from tests.mcp_parity_support import parity_design_lint_policy, semantic_design_lint_report
from tests.synthetic_design_lint_project import run_design_lint_cli, synthetic_design_lint_project

RULE_ID = "pcb.track_angle_rule_coverage"
pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.parity_lint,
    pytest.mark.slow,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def _policy() -> DesignLintPolicy:
    return parity_design_lint_policy(
        DesignLintPolicy(
            pcb_track_angle_map=PcbTrackAngleMap(
                basis="Reviewed synthetic signal-integrity requirement",
                requirements=(
                    PcbTrackAngleRequirement(
                        id="clock-output",
                        basis="Approved routing guideline",
                        net="CLOCK_OUT",
                        rule_name="clock-track-angle",
                        minimum_degrees=150,
                    ),
                ),
            )
        )
    )


def _install_source_bound_drc_receipt(root: Path, summary_path: Path) -> None:
    summary = read_model(summary_path, ValidationSummary)
    board = root / "projects/controller/kicad/controller.kicad_pcb"
    drc_path = summary_path.parent / "drc.json"
    command_path = summary_path.parent / "drc.command.json"
    drc_path.write_text(
        json.dumps(
            {
                "$schema": "https://schemas.kicad.org/drc.v1.json",
                "kicad_version": "10.0.5",
                "source": str(board),
                "coordinate_units": "mm",
                "included_severities": ["error", "warning", "exclusion"],
                "ignored_checks": [],
                "violations": [],
            }
        ),
        encoding="utf-8",
    )
    write_model(
        command_path,
        CommandEvidence(
            argv=(
                "kicad-cli",
                "pcb",
                "drc",
                "--format",
                "json",
                "--severity-all",
                "--output",
                str(drc_path),
                str(board),
            ),
            started_utc="synthetic parity fixture",
            returncode=0,
        ),
    )
    write_model(
        summary_path,
        summary.model_copy(
            update={
                "checks": {
                    **summary.checks,
                    "drc": CheckEvidence(status="PASS", returncode=0),
                },
                "artifacts_sha256": {
                    **summary.artifacts_sha256,
                    "drc.json": digest(drc_path),
                    "drc.command.json": digest(command_path),
                },
            }
        ),
    )


def test_track_angle_coverage_finding_matches_cli_and_mcp(tmp_path: Path) -> None:
    rules = (
        '(version 1)\n(rule "clock-track-angle" (severity error) '
        "(condition \"A.NetName == 'CLOCK_OUT'\") "
        "(constraint track_angle (min 149)))\n"
    )
    root, native = synthetic_design_lint_project(
        tmp_path,
        _policy(),
        custom_rules_source=rules,
    )
    _install_source_bound_drc_receipt(root, native)

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
    finding = next(item for item in mcp_report.findings if item.rule_id == RULE_ID)
    assert finding.mode == "review" and finding.disposition == "OPEN"
    assert finding.evidence["net"] == ("CLOCK_OUT",)
    assert finding.evidence["project_sha256"] == (
        mcp_report.source_hashes["projects/controller/kicad/controller.kicad_pro"],
    )
