"""CLI/MCP parity for source-bound RS-485 peer reference review."""

from __future__ import annotations

import pytest

pytestmark = [
    pytest.mark.parity_lint,
    pytest.mark.slow,
    pytest.mark.template_checkout,
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
]

from mcp import Client

from kicad_tooling.hwrepo.analysis_state_models import AnalysisPending
from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    DesignLintReport,
    ElectricalAnalysisContract,
    ProjectTestContract,
)
from tests.component_peer_power_assignment_support import peer_pin_netlist_xml
from tests.mcp_parity_support import McpParityHarness, run_mcp_parity
from tests.rs485_peer_reference_support import rs485_peer_reference_fixture


class _Rs485PeerReferenceParityCases(McpParityHarness):
    async def _case_rs485_peer_reference_cli_mcp_parity(self) -> None:
        native = self.native_evidence()
        netlist_path = native.parent / "netlist.xml"
        contract_path = self.island / "tests/contract.json"
        project_contract = read_model(contract_path, ProjectTestContract)
        electrical_relative = "tests/rs485-electrical.json"
        electrical_path = self.island / electrical_relative
        write_model(
            contract_path,
            project_contract.model_copy(update={"electrical": electrical_relative}),
        )

        async with Client(create_server(self.root), mode="legacy") as client:
            for reference_nets, expected_count in (
                ({"U1": "GND_A", "U2": "GND_B", "U3": "GND_A"}, 1),
                ({"U1": "GND", "U2": "GND", "U3": "GND"}, 0),
            ):
                analysis, _, observed = rs485_peer_reference_fixture(reference_nets=reference_nets)
                write_model(
                    electrical_path,
                    ElectricalAnalysisContract(
                        project_id="controller",
                        ngspice_version="not run by synthetic parity fixture",
                        grounding=AnalysisPending(
                            reason="Synthetic parity fixture isolates RS-485 peer references."
                        ),
                        rs485=analysis,
                        power=AnalysisPending(
                            reason="Synthetic parity fixture does not exercise power budgets."
                        ),
                        high_frequency=AnalysisPending(
                            reason="Synthetic parity fixture does not exercise high-frequency analysis."
                        ),
                    ),
                )
                netlist_path.write_text(peer_pin_netlist_xml(observed), encoding="utf-8")
                self.rehash_native_netlist(native)
                cli = await self.cli(
                    "kicad_tooling.design_lint",
                    DesignLintReport,
                    "--project",
                    "controller",
                    "--native-summary",
                    str(native),
                    expected_exit=1 if expected_count else 0,
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
                cli_findings = tuple(
                    item
                    for item in cli.findings
                    if item.rule_id == "bus.rs485_peer_reference_review"
                )
                mcp_findings = tuple(
                    item
                    for item in mcp.findings
                    if item.rule_id == "bus.rs485_peer_reference_review"
                )
                self.assertEqual(cli.status, mcp.status)
                self.assertEqual(cli_findings, mcp_findings)
                self.assertEqual(
                    cli.rs485_peer_reference_coverage,
                    mcp.rs485_peer_reference_coverage,
                )
                self.assertEqual(len(mcp_findings), expected_count)
                self.assertEqual(
                    mcp.rs485_peer_reference_coverage.candidate_group_count,
                    expected_count,
                )
                self.assertEqual(
                    mcp.rs485_peer_reference_coverage.authored_map_source_sha256,
                    digest(electrical_path),
                )


def test_rs485_peer_reference_cli_mcp_parity() -> None:
    run_mcp_parity(
        _Rs485PeerReferenceParityCases,
        "_case_rs485_peer_reference_cli_mcp_parity",
    )
