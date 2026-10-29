"""The CLI and MCP reconcile the same saved source-bound lint report."""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from pathlib import Path

import pytest
from mcp import Client

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.evidence_lint,
    pytest.mark.parity_lint,
    pytest.mark.slow,
]

from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.design_lint_reconciliation_models import (
    DesignLintReconciliationReport,
)
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import DesignLintPolicy, ValidationSummary
from tests.mcp_parity_support import parity_design_lint_policy
from tests.synthetic_design_lint_project import run_design_lint_cli, synthetic_design_lint_project

_NETLIST_FIXTURE = (
    Path(__file__).resolve().parent / "fixtures/design_lint/connectivity-snapshot/netlist.xml"
)


def _refresh_netlist_artifact(root: Path, summary_path: Path, content: str) -> None:
    netlist_path = root / "build/native/controller/netlist.xml"
    netlist_path.write_text(content, encoding="utf-8")
    summary = read_model(summary_path, ValidationSummary)
    artifact_hashes = dict(summary.artifacts_sha256)
    artifact_hashes["netlist.xml"] = digest(netlist_path)
    write_model(summary_path, summary.model_copy(update={"artifacts_sha256": artifact_hashes}))


@pytest.mark.parametrize(
    ("metadata_change", "blocked_baseline"),
    ((True, False), (False, False), (False, True)),
    ids=("pin-metadata", "digest-only", "blocked-baseline"),
)
def test_design_lint_reconciliation_cli_mcp_parity(
    tmp_path: Path, metadata_change: bool, blocked_baseline: bool
) -> None:
    root, native = synthetic_design_lint_project(
        tmp_path,
        parity_design_lint_policy(DesignLintPolicy()),
    )
    baseline_netlist = _NETLIST_FIXTURE.read_text(encoding="utf-8")
    _refresh_netlist_artifact(root, native, baseline_netlist)

    baseline_process = run_design_lint_cli(tmp_path, root, native)
    assert baseline_process.returncode in (0, 1), baseline_process.stderr
    baseline = DesignLintReport.model_validate_json(baseline_process.stdout)
    if blocked_baseline:
        baseline = baseline.model_copy(update={"status": "BLOCKED"})
    assert baseline.connectivity_snapshot is not None
    assert baseline.connectivity_snapshot.pin_metadata_coverage == "COMPLETE"
    baseline_path = root / "lint-baseline.json"
    baseline_path.write_text(baseline.model_dump_json(), encoding="utf-8")

    changed_netlist = (
        baseline_netlist.replace(
            '<pin num="4" name="GND" type="passive" />',
            '<pin num="4" name="RETURN" type="passive" />',
            1,
        )
        if metadata_change
        else baseline_netlist + "\n"
    )
    assert changed_netlist != baseline_netlist
    _refresh_netlist_artifact(root, native, changed_netlist)
    cli_process = subprocess.run(
        (
            sys.executable,
            "-I",
            "-B",
            "-m",
            "kicad_tooling.design_lint",
            "--root",
            str(root),
            "--project",
            "controller",
            "--native-summary",
            str(native),
            "--baseline-report",
            baseline_path.name,
            "--format",
            "json",
        ),
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
        timeout=60,
    )
    cli = DesignLintReconciliationReport.model_validate_json(cli_process.stdout)
    assert cli_process.returncode == 1

    async def reconcile_with_mcp() -> DesignLintReconciliationReport:
        async with Client(create_server(root), mode="legacy") as client:
            result = await client.call_tool(
                "reconcile_design_lint",
                {
                    "project_id": "controller",
                    "native_summary": native.relative_to(root).as_posix(),
                    "baseline_report_json": baseline.model_dump_json(),
                },
            )
        assert not result.is_error, result.content
        assert result.structured_content is not None
        return DesignLintReconciliationReport.model_validate_json(
            json.dumps(result.structured_content)
        )

    mcp = asyncio.run(reconcile_with_mcp())
    assert cli == mcp
    if blocked_baseline:
        assert cli.status == "BLOCKED"
        assert cli.transitions == ()
        assert sorted(item.fingerprint for item in cli.baseline_findings) == sorted(
            item.fingerprint for item in baseline.findings
        )
        assert cli.issue is not None and "Baseline design-lint report is BLOCKED" in cli.issue
        return
    assert cli.status == "REVIEW", cli.model_dump_json(indent=2)
    assert cli.pin_metadata_comparison == "COMPLETE"
    assert cli.connectivity_comparison == "COMPLETE"
    assert cli.connectivity_changes == ()
    assert tuple((item.pin, item.fields_changed) for item in cli.pin_metadata_changes) == (
        (("J1.4", ("function",)),) if metadata_change else ()
    )
    assert "Native netlist digest changed" in cli.context_changes
