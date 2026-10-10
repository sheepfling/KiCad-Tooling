"""Design-lint CLI/MCP parity cases: design lint mcp parity peer pins."""

from __future__ import annotations

import pytest

pytestmark = [
    pytest.mark.parity_lint,
    pytest.mark.slow,
    pytest.mark.template_checkout,
    pytest.mark.design_lint,
]

import asyncio
import json
from pathlib import Path

from mcp import Client

from kicad_tooling.hwrepo.contracts import (
    parse_model_text,
    read_model,
    write_model,
)
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    DesignLintReport,
    ValidationSummary,
)
from tests import test_parts_workflow as native_fixture
from tests.mcp_parity_support import (
    McpParityHarness,
    parity_cli_process,
    parity_native_evidence,
    parity_workspace,
    run_mcp_parity,
)


class _DesignLintMcpParityPeerPinsCases(McpParityHarness):
    async def _case_test_peer_component_power_pin_lint_cli_mcp_parity(self) -> None:
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"

        def render_netlist(*, split_domains: bool) -> str:
            supply_nodes = (
                '<net name="+3V3"><node ref="U1" pin="1"/><node ref="C1" pin="1"/></net>'
                '<net name="+5V"><node ref="U2" pin="1"/><node ref="C2" pin="1"/></net>'
                if split_domains
                else '<net name="+3V3"><node ref="U1" pin="1"/><node ref="U2" pin="1"/>'
                '<node ref="C1" pin="1"/><node ref="C2" pin="1"/></net>'
            )
            return_nodes = (
                '<net name="GND"><node ref="U1" pin="2"/><node ref="C1" pin="2"/></net>'
                '<net name="AGND"><node ref="U2" pin="2"/><node ref="C2" pin="2"/></net>'
                if split_domains
                else '<net name="GND"><node ref="U1" pin="2"/><node ref="U2" pin="2"/>'
                '<node ref="C1" pin="2"/><node ref="C2" pin="2"/></net>'
            )
            return (
                "<export><components>"
                '<comp ref="U1"><value>Synthetic peer</value>'
                "<footprint>Package:Controller</footprint>"
                '<libsource lib="Synthetic" part="PowerPeer"/></comp>'
                '<comp ref="U2"><value>Synthetic peer</value>'
                "<footprint>Package:Controller</footprint>"
                '<libsource lib="Synthetic" part="PowerPeer"/></comp>'
                '<comp ref="C1"><value>100n</value><libsource lib="Device" part="C"/></comp>'
                '<comp ref="C2"><value>100n</value><libsource lib="Device" part="C"/></comp>'
                '</components><libparts><libpart lib="Synthetic" part="PowerPeer"><pins>'
                '<pin num="1" name="VDD" type="power_in"/>'
                '<pin num="2" name="GND" type="power_in"/>'
                '</pins></libpart><libpart lib="Device" part="C"><pins>'
                '<pin num="1" name="1" type="passive"/>'
                '<pin num="2" name="2" type="passive"/>'
                "</pins></libpart></libparts><nets>"
                f"{supply_nodes}{return_nodes}</nets></export>"
            )

        def write_source_bound_netlist(*, split_domains: bool) -> None:
            netlist.write_text(render_netlist(split_domains=split_domains), encoding="utf-8")
            summary = read_model(native, ValidationSummary)
            write_model(
                native,
                summary.model_copy(
                    update={
                        "artifacts_sha256": {
                            **summary.artifacts_sha256,
                            "netlist.xml": digest(netlist),
                        }
                    }
                ),
            )

        async with Client(create_server(self.root), mode="legacy") as client:
            for split_domains, expected_status, expected_exit in (
                (True, "REVIEW", 1),
                (False, "PASS", 0),
            ):
                with self.subTest(split_domains=split_domains):
                    write_source_bound_netlist(split_domains=split_domains)
                    cli = await self.cli(
                        "kicad_tooling.design_lint",
                        DesignLintReport,
                        "--project",
                        "controller",
                        "--native-summary",
                        str(native),
                        expected_exit=expected_exit,
                    )
                    mcp = await self.call(
                        client,
                        "inspect_design_lint",
                        DesignLintReport,
                        {
                            "project_id": "controller",
                            "native_summary": native.relative_to(self.root).as_posix(),
                        },
                    )
                    self.assertEqual(cli, mcp)
                    self.assertEqual(mcp.status, expected_status)
                    peer_findings = [
                        item
                        for item in mcp.findings
                        if item.rule_id == "component.peer_power_pin_assignment_divergence"
                    ]
                    self.assertEqual(len(peer_findings), 2 if split_domains else 0)


@pytest.mark.template_checkout
@pytest.mark.parametrize(
    ("electrical_type", "pin_function", "rule_id"),
    (
        ("power_out", "OUT", "component.peer_power_output_unconnected"),
        ("output", "OUT", "component.peer_signal_output_unconnected"),
        ("input", "IN", "component.peer_signal_input_unconnected"),
        ("bidirectional", "DATA_IO", "component.peer_bidirectional_pin_unconnected"),
    ),
)
def test_peer_component_pin_unconnected_lint_cli_mcp_parity(
    tmp_path: Path, electrical_type: str, pin_function: str, rule_id: str
) -> None:
    root, island, _ = parity_workspace(tmp_path)
    native = parity_native_evidence(root, island)
    netlist = native.parent / "netlist.xml"

    def write_netlist(*, fault: bool) -> None:
        signal_name = {
            "input": "INPUT",
            "bidirectional": "DATA_IO",
            "power_out": "VOUT",
            "output": "VOUT",
        }[electrical_type]
        output_nets = (
            f'<net name="{signal_name}"><node ref="U10" pin="2"/></net>'
            if fault
            else f'<net name="{signal_name}_A"><node ref="U10" pin="2"/></net>'
            f'<net name="{signal_name}_B"><node ref="U11" pin="2"/></net>'
        )
        text = native_fixture.NETLIST.replace(
            "</components><nets/>",
            '<comp ref="U10"><value>Synthetic output peer</value>'
            '<libsource lib="Synthetic" part="PowerOutputPeer"/></comp>'
            '<comp ref="U11"><value>Synthetic output peer</value>'
            '<libsource lib="Synthetic" part="PowerOutputPeer"/></comp>'
            '</components><libparts><libpart lib="Synthetic" '
            'part="PowerOutputPeer"><pins>'
            '<pin num="1" name="IO" type="passive"/>'
            f'<pin num="2" name="{pin_function}" type="{electrical_type}"/>'
            "</pins></libpart></libparts><nets>"
            '<net name="DATA"><node ref="U10" pin="1"/>'
            '<node ref="U11" pin="1"/></net>'
            f"{output_nets}</nets>",
        )
        netlist.write_text(text, encoding="utf-8")
        summary = read_model(native, ValidationSummary)
        write_model(
            native,
            summary.model_copy(
                update={
                    "artifacts_sha256": {
                        **summary.artifacts_sha256,
                        "netlist.xml": digest(netlist),
                    }
                }
            ),
        )

    async def exercise() -> None:
        async with Client(create_server(root), mode="legacy") as client:
            for fault in (True, False):
                write_netlist(fault=fault)
                expected_exit = 1 if fault else 0
                process = await parity_cli_process(
                    tmp_path,
                    root,
                    "kicad_tooling.design_lint",
                    "--project",
                    "controller",
                    "--native-summary",
                    str(native),
                )
                assert process.returncode == expected_exit, process.stderr + process.stdout
                cli_report = parse_model_text(process.stdout, DesignLintReport)

                result = await client.call_tool(
                    "inspect_design_lint",
                    {
                        "project_id": "controller",
                        "native_summary": native.relative_to(root).as_posix(),
                    },
                )
                assert not result.is_error, result.content
                assert result.structured_content is not None
                mcp_report = DesignLintReport.model_validate_json(
                    json.dumps(result.structured_content)
                )

                assert cli_report == mcp_report
                assert mcp_report.status == ("REVIEW" if fault else "PASS")
                findings = tuple(item for item in mcp_report.findings if item.rule_id == rule_id)
                coverage = next(
                    item
                    for item in mcp_report.component_peer_pin_coverage
                    if item.rule_id == rule_id
                )
                assert coverage.status == "EVALUATED"
                assert coverage.netlist_sha256 == mcp_report.netlist_sha256
                assert coverage.candidate_group_count == int(fault)
                assert coverage.finding_count == len(findings) == int(fault)
                assert coverage.suppressed_candidate_count == 0
                if fault:
                    assert len(findings) == 1
                    assert findings[0].evidence["unassigned_pins"] == ("U11.2",)
                else:
                    assert findings == ()

    asyncio.run(exercise())


def test_peer_component_power_pin_lint_cli_mcp_parity() -> None:
    run_mcp_parity(
        _DesignLintMcpParityPeerPinsCases, "_case_test_peer_component_power_pin_lint_cli_mcp_parity"
    )
