"""CLI/MCP parity for duplicate PCB pad numbers with different net assignments."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from mcp import Client

from kicad_tooling.hwrepo.contracts import parse_model_text
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import DesignLintPolicy, DesignLintReport
from tests.design_lint_fixtures.pcb_component_inventory import netlist
from tests.electrical_parity_support import contract_netlist_xml
from tests.mcp_parity_support import parity_design_lint_policy, semantic_design_lint_report
from tests.synthetic_design_lint_project import (
    install_synthetic_netlist,
    run_design_lint_cli,
    synthetic_design_lint_project,
)

RULE_ID = "pcb.duplicate_pad_net_conflict"
FAULT = (
    Path(__file__).parent / "fixtures/design_lint/pcb-duplicate-pad-net-conflict/fault.kicad_pcb"
)
pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.parity_lint,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def test_duplicate_pad_net_conflict_matches_between_cli_and_mcp(tmp_path: Path) -> None:
    root, native = synthetic_design_lint_project(
        tmp_path,
        parity_design_lint_policy(DesignLintPolicy()),
        board_source=FAULT.read_text(encoding="utf-8"),
    )
    observed = netlist(
        components={"J1": "Synthetic:TwoPadConnector"},
        nets={"SIGNAL": ("J1.1",)},
        component_pin_numbers={"J1": ("1",)},
    ).model_copy(update={"component_symbols": {"J1": "Synthetic:TwoPadConnector"}})
    install_synthetic_netlist(native, contract_netlist_xml(observed))

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
    findings = [item for item in mcp_report.findings if item.rule_id == RULE_ID]
    assert len(findings) == 1
    assert findings[0].evidence["pad_number"] == ("1",)
    assert findings[0].evidence["pad_assignments"] == (
        "pad 1, line 17: 1:SIGNAL",
        "pad 2, line 18: 2:RETURN",
    )
