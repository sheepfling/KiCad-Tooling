"""CLI/MCP parity for source-bound saved PCB DRC exclusion findings."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from mcp import Client

from kicad_tooling.hwrepo.contracts import parse_model_text, read_model, write_model
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    CheckEvidence,
    DesignLintPolicy,
    DesignLintReport,
    ValidationSummary,
)
from kicad_tooling.hwrepo.pcb_drc_project_settings import pcb_drc_exclusions
from tests.mcp_parity_support import (
    parity_design_lint_policy,
    semantic_design_lint_report,
)
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

SETTINGS = Path(__file__).parent / "fixtures/design_lint/pcb-drc-exclusions/fault.kicad_pro"
NATIVE_SETTINGS = (
    Path(__file__).parent / "fixtures/design_lint/pcb-drc-exclusion-native/stale.kicad_pro"
)


def test_saved_drc_exclusions_match_between_cli_and_mcp(tmp_path: Path) -> None:
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
    findings = [item for item in mcp_report.findings if item.rule_id == "pcb.drc_exclusion_present"]
    assert len(findings) == 2
    assert all(item.mode == "review" and item.disposition == "OPEN" for item in findings)
    assert all(
        item.evidence["source_sha256"]
        == (mcp_report.source_hashes["projects/controller/kicad/controller.kicad_pro"],)
        for item in findings
    )
    assert all(item.evidence["kicad_version"] == ("10.0.5",) for item in findings)


def test_saved_drc_exclusion_native_match_status_matches_between_cli_and_mcp(
    tmp_path: Path,
) -> None:
    settings_text = NATIVE_SETTINGS.read_text(encoding="utf-8")
    exclusions = pcb_drc_exclusions(settings_text)
    matched = next(item for item in exclusions if item.marker.endswith("000000000002"))
    fields = matched.marker.split("|")
    root, native = synthetic_design_lint_project(
        tmp_path,
        parity_design_lint_policy(DesignLintPolicy()),
        project_settings_source=settings_text,
    )
    report = {
        "$schema": "https://schemas.kicad.org/drc.v1.json",
        "kicad_version": "10.0.5",
        "source": "controller.kicad_pcb",
        "coordinate_units": "mm",
        "included_severities": ["error", "warning", "exclusion"],
        "violations": [
            {
                "excluded": True,
                "type": fields[0],
                "severity": "error",
                "description": "Synthetic exclusion match.",
                "comment": matched.comment,
                "items": [
                    {
                        "description": "Synthetic board item.",
                        "pos": {"x": 10.0, "y": 0.5},
                        "uuid": item_id,
                    }
                    for item_id in fields[3:]
                ],
            }
        ],
    }
    report_path = native.parent / "drc.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    summary_path = native / "summary.json" if native.is_dir() else native
    summary = read_model(summary_path, ValidationSummary)
    checks = dict(summary.checks)
    checks["drc"] = CheckEvidence(status="FAIL", returncode=5, findings=1)
    write_model(
        summary_path,
        summary.model_copy(
            update={
                "checks": checks,
                "artifacts_sha256": {
                    **summary.artifacts_sha256,
                    "drc.json": digest(report_path),
                },
            }
        ),
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
    findings = [item for item in mcp_report.findings if item.rule_id == "pcb.drc_exclusion_present"]
    assert sorted(item.evidence["native_match_status"][0] for item in findings) == [
        "MATCHED",
        "UNMATCHED",
    ]
