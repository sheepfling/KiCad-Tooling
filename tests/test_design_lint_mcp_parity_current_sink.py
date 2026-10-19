"""CLI/MCP parity for explicitly mapped multi-channel current-sink LED paths."""

from __future__ import annotations

from pathlib import Path

import pytest
from mcp import Client

from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    ComponentIdentity,
    ConnectorInventoryReview,
    DesignLintPolicy,
    DesignLintReport,
    ProjectManifest,
    ProjectTestContract,
    ValidationSummary,
)
from tests.design_lint_fixtures.current_sink_led import current_sink_path_map
from tests.mcp_parity_support import McpParityHarness, run_mcp_parity

LED_RULE_ID = "component.led_directly_driven_from_output"
POWER_PATH_RULE_ID = "power.mapped_series_path_mismatch"

pytestmark = [
    pytest.mark.parity_lint,
    pytest.mark.slow,
    pytest.mark.template_checkout,
    pytest.mark.design_lint,
    pytest.mark.component_lint,
    pytest.mark.power_lint,
]


class _CurrentSinkPathParityCases(McpParityHarness):
    async def _case_multichannel_path_parity(self) -> None:
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"
        fixture = (
            Path(__file__).parent / "fixtures/design_lint/current-sink-two-channel.netlist.xml"
        )
        netlist.write_bytes(fixture.read_bytes())
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

        manifest_path = self.island / "project.json"
        manifest = read_model(manifest_path, ProjectManifest)
        write_model(
            manifest_path,
            manifest.model_copy(
                update={
                    "component_identity": ComponentIdentity(required=False, part_ids=()),
                    "interfaces": (),
                    "connector_reviews": (),
                    "connector_inventory_review": ConnectorInventoryReview(
                        basis="Synthetic parity source has no connector instances"
                    ),
                }
            ),
        )
        contract_path = self.island / "tests/contract.json"

        async with Client(create_server(self.root), mode="legacy") as client:

            async def compare(*, two_paths: bool, fault: bool) -> DesignLintReport:
                contract = read_model(contract_path, ProjectTestContract)
                write_model(
                    contract_path,
                    contract.model_copy(
                        update={
                            "design_lint": DesignLintPolicy(
                                power_path_map=current_sink_path_map(two_channels=two_paths)
                            )
                        }
                    ),
                )
                cli = await self.cli(
                    "kicad_tooling.design_lint",
                    DesignLintReport,
                    "--project",
                    "controller",
                    "--native-summary",
                    str(native),
                    expected_exit=1 if fault else 0,
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
                return mcp

            partial = await compare(two_paths=False, fault=True)
            self.assertEqual(partial.status, "REVIEW", partial.issues)
            self.assertEqual(
                [item.subject for item in partial.findings if item.rule_id == LED_RULE_ID],
                ["D2: LED directly shares an output net and a rail"],
            )
            self.assertNotIn(POWER_PATH_RULE_ID, {item.rule_id for item in partial.findings})

            complete = await compare(two_paths=True, fault=False)
            self.assertEqual(complete.status, "PASS", complete.issues)
            self.assertNotIn(LED_RULE_ID, {item.rule_id for item in complete.findings})
            self.assertNotIn(POWER_PATH_RULE_ID, {item.rule_id for item in complete.findings})


@pytest.mark.component_lint
@pytest.mark.design_lint_rule(rule_id=LED_RULE_ID)
@pytest.mark.design_lint_rule(rule_id=POWER_PATH_RULE_ID)
def test_multichannel_current_sink_path_parity() -> None:
    run_mcp_parity(_CurrentSinkPathParityCases, "_case_multichannel_path_parity")
