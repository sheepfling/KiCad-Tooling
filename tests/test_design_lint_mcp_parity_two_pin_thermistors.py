"""CLI/MCP parity for the exact same-net two-pin thermistor review."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from mcp import Client

from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import DesignLintPolicy, DesignLintReport, ValidationSummary
from tests.mcp_parity_support import semantic_design_lint_report
from tests.synthetic_design_lint_project import run_design_lint_cli, synthetic_design_lint_project

RULE_ID = "component.two_pin_passive_same_net"
pytestmark = [
    pytest.mark.component_lint,
    pytest.mark.design_lint,
    pytest.mark.parity_lint,
    pytest.mark.slow,
]


def _thermistor_netlist(*, symbol: str, same_net: bool) -> str:
    symbol_name = symbol.partition(":")[2]
    value = "10k PTC" if "_PTC" in symbol_name else "10k NTC"
    nets = (
        '<net name="SHARED"><node ref="TH1" pin="1"/><node ref="TH1" pin="2"/></net>'
        if same_net
        else '<net name="SENSE_A"><node ref="TH1" pin="1"/></net>'
        '<net name="SENSE_B"><node ref="TH1" pin="2"/></net>'
    )
    return (
        "<export><components>"
        f'<comp ref="TH1"><value>{value}</value>'
        "<footprint>Synthetic:Thermistor</footprint>"
        f'<libsource lib="Device" part="{symbol_name}"/></comp>'
        f'</components><libparts><libpart lib="Device" part="{symbol_name}"><pins>'
        '<pin num="1" name="1" type="passive"/>'
        '<pin num="2" name="2" type="passive"/>'
        f"</pins></libpart></libparts><nets>{nets}</nets></export>"
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
@pytest.mark.parametrize("symbol", ("Device:Thermistor_NTC", "Device:Thermistor_PTC"))
def test_same_net_thermistor_lint_cli_mcp_parity(tmp_path: Path, symbol: str) -> None:
    root, summary_path = synthetic_design_lint_project(tmp_path, DesignLintPolicy())
    netlist = summary_path.parent / "netlist.xml"

    async def compare_fault_and_control() -> tuple[DesignLintReport, DesignLintReport]:
        async with Client(create_server(root), mode="legacy") as client:
            reports: list[DesignLintReport] = []
            for same_net in (True, False):
                netlist.write_text(
                    _thermistor_netlist(symbol=symbol, same_net=same_net),
                    encoding="utf-8",
                )
                summary = read_model(summary_path, ValidationSummary)
                write_model(
                    summary_path,
                    summary.model_copy(
                        update={
                            "artifacts_sha256": {
                                **summary.artifacts_sha256,
                                "netlist.xml": digest(netlist),
                            }
                        }
                    ),
                )

                process = run_design_lint_cli(tmp_path, root, summary_path)
                assert process.returncode in {0, 1}, process.stderr + process.stdout
                cli = DesignLintReport.model_validate_json(process.stdout)
                result = await client.call_tool(
                    "inspect_design_lint",
                    {
                        "project_id": "controller",
                        "native_summary": summary_path.relative_to(root).as_posix(),
                    },
                )
                assert not result.is_error, result.content
                assert result.structured_content is not None
                mcp = DesignLintReport.model_validate_json(json.dumps(result.structured_content))
                assert semantic_design_lint_report(cli) == semantic_design_lint_report(mcp)

                findings = [item for item in mcp.findings if item.rule_id == RULE_ID]
                assert len(findings) == int(same_net)
                if findings:
                    assert findings[0].evidence["symbol"] == (symbol,)
                    assert findings[0].evidence["pin_assignments"] == (
                        "TH1.1 -> SHARED",
                        "TH1.2 -> SHARED",
                    )
                reports.append(mcp)
            return reports[0], reports[1]

    fault, control = asyncio.run(compare_fault_and_control())
    assert RULE_ID in {item.rule_id for item in fault.findings}
    assert RULE_ID not in {item.rule_id for item in control.findings}
