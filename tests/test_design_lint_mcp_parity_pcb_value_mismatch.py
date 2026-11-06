"""CLI/MCP route for source-bound schematic-to-PCB value findings."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from mcp import Client

from kicad_tooling.hwrepo.contracts import parse_model_text, write_model
from kicad_tooling.hwrepo.design_lint_policy_models import DesignLintPolicy
from kicad_tooling.hwrepo.design_lint_reconciliation_models import (
    DesignLintReconciliationReport,
)
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.pcb_return_path_capture import expected_probe_sha256
from tests.design_lint_fixtures.pcb_component_inventory import snapshot
from tests.mcp_parity_support import semantic_design_lint_report
from tests.source_bound_pcb_parity_support import (
    PROJECT_SETTINGS,
    install_synthetic_native_pcb_capture,
    replace_authoritative_board_source,
    run_design_lint_cli_in_process,
)
from tests.synthetic_design_lint_project import synthetic_design_lint_project

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.evidence_lint,
    pytest.mark.parity_lint,
    pytest.mark.slow,
]

PROJECT_ID = "controller"
RULE_ID = "pcb.schematic_pcb_value_mismatch"
IMPLEMENTATION_OWNER = "kicad_tooling/hwrepo/pcb_component_values.py#compare_schematic_pcb_values"
FOOTPRINT = "Synthetic:R"


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_value_mismatch_capture_and_reconciliation_match_cli_and_mcp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    baseline_root, baseline_summary = synthetic_design_lint_project(
        tmp_path / "baseline",
        DesignLintPolicy(),
        project_settings_source=PROJECT_SETTINGS,
    )
    current_root, current_summary = synthetic_design_lint_project(
        tmp_path / "current",
        DesignLintPolicy(),
        project_settings_source=PROJECT_SETTINGS,
    )
    baseline_board_sha256 = replace_authoritative_board_source(
        baseline_root,
        baseline_summary,
        "synthetic PCB source; R1 value=1k\n",
    )
    current_board_sha256 = replace_authoritative_board_source(
        current_root,
        current_summary,
        "synthetic PCB source; R1 value=1K\n",
    )
    install_synthetic_native_pcb_capture(
        monkeypatch,
        {
            baseline_board_sha256: snapshot(
                "R1",
                schema_version="13",
                footprint_by_reference={"R1": FOOTPRINT},
                value_by_reference={"R1": "1k"},
            ),
            current_board_sha256: snapshot(
                "R1",
                schema_version="13",
                footprint_by_reference={"R1": FOOTPRINT},
                value_by_reference={"R1": "1K"},
            ),
        },
    )

    baseline_returncode, baseline_output = run_design_lint_cli_in_process(
        baseline_root,
        baseline_summary,
        baseline_report=None,
        monkeypatch=monkeypatch,
        capsys=capsys,
    )
    assert baseline_returncode in {0, 1}
    baseline = parse_model_text(baseline_output, DesignLintReport)
    assert not any(item.rule_id == RULE_ID for item in baseline.findings)

    current_returncode, current_output = run_design_lint_cli_in_process(
        current_root,
        current_summary,
        baseline_report=None,
        monkeypatch=monkeypatch,
        capsys=capsys,
    )
    assert current_returncode == 1
    cli_inspection = parse_model_text(current_output, DesignLintReport)

    async def inspect_current_with_mcp() -> DesignLintReport:
        async with Client(create_server(current_root), mode="legacy") as client:
            result = await client.call_tool(
                "inspect_design_lint",
                {
                    "project_id": PROJECT_ID,
                    "native_summary": current_summary.relative_to(current_root).as_posix(),
                },
            )
        assert not result.is_error, result.content
        assert result.structured_content is not None
        return DesignLintReport.model_validate_json(json.dumps(result.structured_content))

    mcp_inspection = asyncio.run(inspect_current_with_mcp())
    assert semantic_design_lint_report(cli_inspection) == semantic_design_lint_report(
        mcp_inspection
    )
    assert mcp_inspection.rule_catalog is not None
    rule = next(item for item in mcp_inspection.rule_catalog.rules if item.rule_id == RULE_ID)
    assert rule.implementation_owner == IMPLEMENTATION_OWNER
    finding = next(item for item in mcp_inspection.findings if item.rule_id == RULE_ID)
    assert finding.mode == "review" and finding.disposition == "OPEN"
    board_source_path = "projects/controller/kicad/controller.kicad_pcb"
    assert finding.evidence["board_path"] == (board_source_path,)
    assert finding.evidence["board_sha256"] == (mcp_inspection.source_hashes[board_source_path],)
    assert finding.evidence["netlist_sha256"] == (mcp_inspection.netlist_sha256,)
    assert finding.evidence["snapshot_schema"] == ("13",)
    assert finding.evidence["kicad_version"] == ("10.0.5",)
    assert finding.evidence["image"] == ("registry.invalid/kicad:10.0.5@sha256:" + "a" * 64,)
    assert finding.evidence["probe_sha256"] == (expected_probe_sha256(),)
    assert finding.evidence["schematic_value"] == ("1k",)
    assert finding.evidence["board_value"] == ("1K",)

    snapshot_path = current_root / "build/design-lint/pcb-geometry-000000000000/snapshot.json"
    assert finding.evidence["snapshot_sha256"] == (digest(snapshot_path),)

    baseline_path = current_root / "lint-baseline.json"
    write_model(baseline_path, baseline)
    reconcile_returncode, reconcile_output = run_design_lint_cli_in_process(
        current_root,
        current_summary,
        baseline_report=baseline_path,
        monkeypatch=monkeypatch,
        capsys=capsys,
    )
    assert reconcile_returncode == 1
    cli_reconciliation = DesignLintReconciliationReport.model_validate_json(reconcile_output)

    async def reconcile_current_with_mcp() -> DesignLintReconciliationReport:
        async with Client(create_server(current_root), mode="legacy") as client:
            result = await client.call_tool(
                "reconcile_design_lint",
                {
                    "project_id": PROJECT_ID,
                    "native_summary": current_summary.relative_to(current_root).as_posix(),
                    "baseline_report_json": baseline.model_dump_json(),
                },
            )
        assert not result.is_error, result.content
        assert result.structured_content is not None
        return DesignLintReconciliationReport.model_validate_json(
            json.dumps(result.structured_content)
        )

    mcp_reconciliation = asyncio.run(reconcile_current_with_mcp())
    assert cli_reconciliation == mcp_reconciliation
    assert cli_reconciliation.baseline_status == baseline.status
    assert cli_reconciliation.current_status == "REVIEW"
    (transition,) = tuple(
        item
        for item in cli_reconciliation.transitions
        if item.current is not None and item.current.rule_id == RULE_ID
    )
    assert transition.kind == "NEW"
    assert transition.baseline is None
    assert transition.current is not None
    assert transition.current.mode == "review"
    assert transition.current.disposition == "OPEN"
    assert transition.current.evidence["board_sha256"] == (
        cli_reconciliation.current_source_hashes[board_source_path],
    )
