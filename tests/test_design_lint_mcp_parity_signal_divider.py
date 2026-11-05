"""CLI/MCP parity for project-mapped signal-divider coverage."""

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
from tests.design_lint_fixtures.signal_divider import signal_divider_map
from tests.mcp_parity_support import McpParityHarness, run_mcp_parity


class _SignalDividerParityCases(McpParityHarness):
    async def _case_test_signal_divider_map_parity(self) -> None:
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"

        def write_netlist(*, top_value: str) -> None:
            netlist.write_text(
                "<export><components>"
                '<comp ref="U1"><value>SYNTH-ANALOG</value>'
                "<footprint>Synthetic:SOIC-8</footprint>"
                '<libsource lib="Synthetic" part="AnalogMonitor"/></comp>'
                f'<comp ref="R1"><value>{top_value}</value>'
                "<footprint>Synthetic:0603</footprint>"
                '<libsource lib="Device" part="R"/></comp>'
                '<comp ref="R2"><value>33k</value>'
                "<footprint>Synthetic:0603</footprint>"
                '<libsource lib="Device" part="R"/></comp>'
                "</components><libparts>"
                '<libpart lib="Synthetic" part="AnalogMonitor"><pins>'
                '<pin num="1" name="VREF_OUT" type="output"/>'
                '<pin num="2" name="ADC_IN" type="input"/>'
                "</pins></libpart>"
                '<libpart lib="Device" part="R"><pins>'
                '<pin num="1" name="1" type="passive"/>'
                '<pin num="2" name="2" type="passive"/>'
                "</pins></libpart></libparts><nets>"
                '<net name="SENSOR_OUT"><node ref="U1" pin="1"/>'
                '<node ref="R1" pin="1"/></net>'
                '<net name="ADC_IN"><node ref="U1" pin="2"/>'
                '<node ref="R1" pin="2"/><node ref="R2" pin="1"/></net>'
                '<net name="GND"><node ref="R2" pin="2"/></net>'
                "</nets></export>",
                encoding="utf-8",
            )
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
                        basis="Synthetic parity fixture has no external connector interfaces"
                    ),
                }
            ),
        )
        contract_path = self.island / "tests/contract.json"
        contract = read_model(contract_path, ProjectTestContract)
        policy = DesignLintPolicy(
            signal_divider_map=signal_divider_map(tolerance_percents=(1.0, 2.0))
        )
        write_model(contract_path, contract.model_copy(update={"design_lint": policy}))

        async with Client(create_server(self.root), mode="legacy") as client:

            async def compare(expected_status: str, exit_code: int) -> DesignLintReport:
                cli = await self.cli(
                    "kicad_tooling.design_lint",
                    DesignLintReport,
                    "--project",
                    "controller",
                    "--native-summary",
                    str(native),
                    expected_exit=exit_code,
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
                self.assertEqual(mcp.status, expected_status, mcp.issues)
                return mcp

            write_netlist(top_value="220k")
            control = await compare("PASS", 0)
            control_coverage = control.signal_divider_coverage
            self.assertEqual(control_coverage.status, "COMPLETE")
            self.assertEqual(control_coverage.netlist_sha256, digest(netlist))
            self.assertEqual(control_coverage.entries[0].status, "COMPLETE")
            self.assertEqual(
                control_coverage.entries[0].maximum_tolerance_percent,
                {"R1": 1.0, "R2": 2.0},
            )
            self.assertIsNotNone(
                control_coverage.entries[0].calculated_tolerance_input_minimum_v
            )

            write_netlist(top_value="180k")
            mismatch = await compare("REVIEW", 1)
            entry = mismatch.signal_divider_coverage.entries[0]
            self.assertEqual(entry.status, "OUT_OF_RANGE")
            self.assertEqual(entry.nominal_resistance_ohms["R1"], 180000.0)
            finding = next(
                item for item in mismatch.findings if item.rule_id.endswith("range_mismatch")
            )
            self.assertIn("formula", finding.evidence)


def test_signal_divider_map_cli_mcp_parity() -> None:
    run_mcp_parity(_SignalDividerParityCases, "_case_test_signal_divider_map_parity")
