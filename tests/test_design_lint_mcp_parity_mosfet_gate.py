"""Synthetic CLI/MCP parity for the MOSFET gate peer heuristic."""

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
from tests.synthetic_design_lint_project import run_design_lint_cli, synthetic_design_lint_project

RULE_ID = "component.mosfet_gate_without_peer"
pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.component_lint,
    pytest.mark.parity_lint,
    pytest.mark.slow,
]


def _write_gate_netlist(path: Path, *, driven: bool) -> None:
    driver_component = (
        '<comp ref="U1"><value>Synthetic output</value>'
        '<libsource lib="Synthetic" part="Driver_OUT"/></comp>'
        if driven
        else ""
    )
    driver_pin = '<pin num="1" name="OUT" type="output"/>' if driven else ""
    driver_node = '<node ref="U1" pin="1"/>' if driven else ""
    path.write_text(
        "<export><components>"
        '<comp ref="Q1"><value>Synthetic NMOS</value>'
        '<libsource lib="Transistor_FET" part="Q_NMOS_GDS"/></comp>'
        f"{driver_component}</components><libparts>"
        '<libpart lib="Transistor_FET" part="Q_NMOS_GDS"><pins>'
        '<pin num="1" name="D" type="passive"/>'
        '<pin num="2" name="G" type="passive"/>'
        '<pin num="3" name="S" type="passive"/>'
        "</pins></libpart>"
        f'<libpart lib="Synthetic" part="Driver_OUT"><pins>{driver_pin}</pins></libpart>'
        "</libparts><nets>"
        '<net name="DRAIN"><node ref="Q1" pin="1"/></net>'
        '<net name="GATE"><node ref="Q1" pin="2"/>'
        f"{driver_node}</net>"
        '<net name="SOURCE"><node ref="Q1" pin="3"/></net>'
        "</nets></export>",
        encoding="utf-8",
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_mosfet_gate_connectivity_cli_mcp_parity(tmp_path: Path) -> None:
    root, summary_path = synthetic_design_lint_project(tmp_path, DesignLintPolicy())
    netlist_path = summary_path.parent / "netlist.xml"

    async def compare(*, driven: bool) -> DesignLintReport:
        _write_gate_netlist(netlist_path, driven=driven)
        summary = read_model(summary_path, ValidationSummary)
        write_model(
            summary_path,
            summary.model_copy(
                update={
                    "artifacts_sha256": {
                        **summary.artifacts_sha256,
                        "netlist.xml": digest(netlist_path),
                    }
                }
            ),
        )
        process = run_design_lint_cli(tmp_path, root, summary_path)
        assert process.returncode in {0, 1}, process.stderr + process.stdout
        cli_report = DesignLintReport.model_validate_json(process.stdout)
        async with Client(create_server(root), mode="legacy") as client:
            result = await client.call_tool(
                "inspect_design_lint",
                {
                    "project_id": "controller",
                    "native_summary": summary_path.relative_to(root).as_posix(),
                },
            )
        assert not result.is_error, result.content
        assert result.structured_content is not None
        mcp_report = DesignLintReport.model_validate_json(json.dumps(result.structured_content))
        assert cli_report == mcp_report
        return mcp_report

    async def run_cases() -> tuple[DesignLintReport, DesignLintReport]:
        return await compare(driven=False), await compare(driven=True)

    fault, control = asyncio.run(run_cases())

    fault_findings = tuple(item for item in fault.findings if item.rule_id == RULE_ID)
    assert len(fault_findings) == 1
    assert fault_findings[0].mode == "review"
    assert fault_findings[0].disposition == "OPEN"
    assert RULE_ID not in {item.rule_id for item in control.findings}
