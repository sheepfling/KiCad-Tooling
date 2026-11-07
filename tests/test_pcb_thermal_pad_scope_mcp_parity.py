"""Verify exposed-pad scope candidates match through CLI and MCP."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from mcp import Client

from kicad_tooling.hwrepo.contracts import parse_model_text
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import DesignLintPolicy, DesignLintReport
from tests.mcp_parity_support import semantic_design_lint_report
from tests.synthetic_design_lint_project import (
    install_synthetic_netlist,
    run_design_lint_cli,
    synthetic_design_lint_project,
)

RULE_ID = "pcb.explicit_thermal_pad_scope_unreviewed"
pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.parity_lint,
    pytest.mark.slow,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def _install_netlist(summary_path: Path) -> None:
    install_synthetic_netlist(
        summary_path,
        "<export><components>"
        '<comp ref="U1"><value>Synthetic device</value><footprint>Synthetic:QFN</footprint>'
        '<libsource lib="Synthetic" part="ThermalPadPart"/></comp>'
        '<comp ref="U2"><value>DNP device</value><footprint>Synthetic:QFN</footprint>'
        '<property name="dnp" value="true"/><libsource lib="Synthetic" part="ThermalPadPart"/></comp>'
        "</components><libparts>"
        '<libpart lib="Synthetic" part="ThermalPadPart"><pins>'
        '<pin num="8" name="THERMAL_ALERT" type="passive"/>'
        '<pin num="9" name="EP" type="passive"/>'
        "</pins></libpart></libparts><nets/></export>",
    )


def test_explicit_thermal_pad_scope_matches_cli_and_mcp(tmp_path: Path) -> None:
    root, native = synthetic_design_lint_project(tmp_path, DesignLintPolicy())
    _install_netlist(native)
    process = run_design_lint_cli(tmp_path, root, native)
    assert process.returncode == 1, process.stderr + process.stdout
    cli = parse_model_text(process.stdout, DesignLintReport)

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

    mcp = asyncio.run(inspect_mcp())
    assert semantic_design_lint_report(cli) == semantic_design_lint_report(mcp)
    assert cli.netlist_sha256 == mcp.netlist_sha256 == digest(native.parent / "netlist.xml")
    cli_findings = tuple(item for item in cli.findings if item.rule_id == RULE_ID)
    mcp_findings = tuple(item for item in mcp.findings if item.rule_id == RULE_ID)
    assert cli_findings == mcp_findings
    assert len(cli_findings) == 1
    assert cli_findings[0].evidence["pin"] == ("U1.9",)
