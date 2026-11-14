"""CLI/MCP parity for generic power contacts open on connector peers."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from mcp import Client

from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import DesignLintPolicy, DesignLintRuleOverride, ValidationSummary
from tests.mcp_parity_support import parity_design_lint_policy, semantic_design_lint_report
from tests.pcb_drc_parity_support import install_source_bound_drc_receipt
from tests.synthetic_design_lint_project import (
    install_synthetic_netlist,
    run_design_lint_cli,
    synthetic_design_lint_project,
)

pytestmark = [
    pytest.mark.parity_lint,
    pytest.mark.slow,
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.power_lint,
    pytest.mark.interface_lint,
]

RULE_ID = "connector.footprint_peer_generic_power_pin_all_open"


def _netlist_xml(*, power_assigned: bool) -> str:
    components = "".join(
        f'<comp ref="{reference}"><value>Synthetic peer connector</value>'
        f"<footprint>Synthetic:Connector_2x1</footprint>"
        f'<libsource lib="Synthetic" part="PowerPort{suffix}"/></comp>'
        for reference, suffix in (("J1", "A"), ("J2", "B"))
    )
    parts = "".join(
        f'<libpart lib="Synthetic" part="PowerPort{suffix}"><pins>'
        '<pin num="1" name="Pin_1" type="passive"/>'
        '<pin num="2" name="Pin_2" type="power_in"/>'
        "</pins></libpart>"
        for suffix in ("A", "B")
    )
    power_nodes = (
        '<net name="SYNTHETIC_VBUS"><node ref="J1" pin="2"/><node ref="J2" pin="2"/></net>'
        if power_assigned
        else ""
    )
    return (
        "<export><components>"
        + components
        + "</components><libparts>"
        + parts
        + '</libparts><nets><net name="SYNTHETIC_RETURN">'
        '<node ref="J1" pin="1"/><node ref="J2" pin="1"/></net>' + power_nodes + "</nets></export>"
    )


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_generic_power_contact_cli_mcp_fault_and_control_parity(tmp_path: Path) -> None:
    policy = parity_design_lint_policy(
        DesignLintPolicy(
            rules=(
                DesignLintRuleOverride(
                    rule_id=RULE_ID,
                    mode="review",
                    reason="Synthetic project opts into generic connector power-pin review.",
                ),
            )
        )
    )
    root, native = synthetic_design_lint_project(tmp_path, policy)
    install_source_bound_drc_receipt(root, native)
    summary = read_model(native, ValidationSummary)
    netlist_path = native.parent / "netlist.xml"

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

    for power_assigned, expected_count in ((False, 1), (True, 0)):
        install_synthetic_netlist(native, _netlist_xml(power_assigned=power_assigned))
        netlist_hash = digest(netlist_path)
        summary = summary.model_copy(
            update={
                "artifacts_sha256": {
                    **summary.artifacts_sha256,
                    "netlist.xml": netlist_hash,
                }
            }
        )
        write_model(native, summary)
        process = run_design_lint_cli(tmp_path, root, native)
        assert process.returncode in {0, 1}, process.stderr + process.stdout
        cli = DesignLintReport.model_validate_json(process.stdout)
        mcp = asyncio.run(inspect_mcp())
        assert semantic_design_lint_report(cli) == semantic_design_lint_report(mcp)
        findings = tuple(item for item in cli.findings if item.rule_id == RULE_ID)
        assert len(findings) == expected_count, cli.issues
        if findings:
            assert findings[0].evidence["pin_electrical_type"] == ("power_in",)
            assert findings[0].evidence["common_anchor_pin_numbers"] == ("1",)
