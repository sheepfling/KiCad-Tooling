"""CLI and MCP share source-bound custom DRC substitution review."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from mcp import Client

from kicad_tooling.hwrepo.contracts import parse_model_text
from kicad_tooling.hwrepo.design_lint_reconciliation_models import (
    DesignLintReconciliationReport,
)
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
FIXTURE = (
    Path(__file__).parent / "fixtures/design_lint/pcb-dru-text-variable/variable-severity.kicad_dru"
)
RULE_ID = "pcb.custom_drc_text_variable_review"
IMPLEMENTATION_OWNER = (
    "kicad_tooling/hwrepo/pcb_dru_rule_review.py#text_variable_custom_drc_rule_candidates"
)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_custom_drc_substitution_review_matches_cli_and_mcp(tmp_path: Path) -> None:
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
    assert mcp_report.status == "REVIEW", mcp_report.issues
    assert mcp_report.rule_catalog is not None
    catalog_rule = next(rule for rule in mcp_report.rule_catalog.rules if rule.rule_id == RULE_ID)
    assert catalog_rule.implementation_owner == IMPLEMENTATION_OWNER
    finding = next(item for item in mcp_report.findings if item.rule_id == RULE_ID)
    assert finding.mode == "review" and finding.disposition == "OPEN"
    assert finding.evidence["source_sha256"] == (
        mcp_report.source_hashes["projects/controller/kicad/controller.kicad_dru"],
    )
    assert finding.evidence["project_sha256"] == (
        mcp_report.source_hashes["projects/controller/kicad/controller.kicad_pro"],
    )
    assert finding.evidence["board_sha256"] == (
        mcp_report.source_hashes["projects/controller/kicad/controller.kicad_pcb"],
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_custom_drc_substitution_transition_matches_cli_and_mcp(tmp_path: Path) -> None:
    """Keep source-file changes and their review transition identical across surfaces."""
    quiet_rules = '(version 1)\n(rule "SyntheticSeverity" (constraint edge_clearance (min 1mm)))\n'
    policy = parity_design_lint_policy(DesignLintPolicy())
    baseline_root, baseline_native = synthetic_design_lint_project(
        tmp_path / "baseline",
        policy,
        custom_rules_source=quiet_rules,
    )
    baseline_process = run_design_lint_cli(tmp_path, baseline_root, baseline_native)
    assert baseline_process.returncode in {0, 1}, baseline_process.stderr + baseline_process.stdout
    baseline = parse_model_text(baseline_process.stdout, DesignLintReport)
    assert not any(item.rule_id == RULE_ID for item in baseline.findings)

    current_root, current_native = synthetic_design_lint_project(
        tmp_path / "current",
        policy,
        custom_rules_source=FIXTURE.read_text(encoding="utf-8"),
    )
    baseline_path = current_root / "lint-baseline.json"
    baseline_path.write_text(baseline.model_dump_json(), encoding="utf-8")
    cli_process = run_design_lint_cli(
        tmp_path,
        current_root,
        current_native,
        baseline_report=Path(baseline_path.name),
    )
    assert cli_process.returncode == 1, cli_process.stderr + cli_process.stdout
    cli_report = DesignLintReconciliationReport.model_validate_json(cli_process.stdout)

    async def reconcile_mcp() -> DesignLintReconciliationReport:
        async with Client(create_server(current_root), mode="legacy") as client:
            result = await client.call_tool(
                "reconcile_design_lint",
                {
                    "project_id": "controller",
                    "native_summary": current_native.relative_to(current_root).as_posix(),
                    "baseline_report_json": baseline.model_dump_json(),
                },
            )
        assert not result.is_error, result.content
        assert result.structured_content is not None
        return DesignLintReconciliationReport.model_validate_json(
            json.dumps(result.structured_content)
        )

    mcp_report = asyncio.run(reconcile_mcp())
    assert cli_report == mcp_report
    assert cli_report.status == "REVIEW"
    assert cli_report.baseline_status == baseline.status
    assert cli_report.current_status == "REVIEW"
    (transition,) = tuple(
        item
        for item in cli_report.transitions
        if item.current is not None and item.current.rule_id == RULE_ID
    )
    assert transition.kind == "NEW"
    assert transition.baseline is None
    assert transition.current is not None
    assert transition.current.mode == "review"
    assert transition.current.disposition == "OPEN"
    assert transition.current.evidence["variable_names"] == ("MODE",)
    assert transition.current.evidence["source_sha256"] == (
        cli_report.current_source_hashes["projects/controller/kicad/controller.kicad_dru"],
    )
