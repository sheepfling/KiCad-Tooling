"""CLI and MCP parity for mapped oscillator output paths."""

from __future__ import annotations

import pytest

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.component_lint,
    pytest.mark.parity_lint,
    pytest.mark.slow,
    pytest.mark.template_checkout,
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
from tests.mcp_parity_support import McpParityHarness, run_mcp_parity
from tests.test_oscillator_output_paths import oscillator_output_path_map


class _OscillatorOutputPathParityCases(McpParityHarness):
    async def _case_test_oscillator_output_path_matches_cli_and_mcp(self) -> None:
        """Compare the same native-netlist value fault and control on both surfaces."""
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"

        def write_netlist(resistor_value: str) -> None:
            netlist.write_text(
                "<export><components>"
                '<comp ref="X1"><value>Synthetic clock module</value>'
                "<footprint>Synthetic:ClockModule_4</footprint>"
                '<libsource lib="Synthetic" part="ClockModule"/></comp>'
                f'<comp ref="R1"><value>{resistor_value}</value>'
                "<footprint>Synthetic:R_0603</footprint>"
                '<libsource lib="Device" part="R"/></comp>'
                '<comp ref="U2"><value>Synthetic receiver A</value>'
                "<footprint>Synthetic:SOIC8</footprint>"
                '<libsource lib="Synthetic" part="ReceiverA"/></comp>'
                '<comp ref="U3"><value>Synthetic receiver B</value>'
                "<footprint>Synthetic:QFN16</footprint>"
                '<libsource lib="Synthetic" part="ReceiverB"/></comp>'
                "</components><libparts>"
                '<libpart lib="Synthetic" part="ClockModule"><pins>'
                '<pin num="1" name="CLK_OUT" type="output"/>'
                '<pin num="2" name="VDD" type="power_in"/>'
                "</pins></libpart>"
                '<libpart lib="Device" part="R"><pins>'
                '<pin num="1" name="1" type="passive"/>'
                '<pin num="2" name="2" type="passive"/>'
                "</pins></libpart>"
                '<libpart lib="Synthetic" part="ReceiverA"><pins>'
                '<pin num="2" name="CLK" type="input"/>'
                "</pins></libpart>"
                '<libpart lib="Synthetic" part="ReceiverB"><pins>'
                '<pin num="3" name="CLK" type="input"/>'
                "</pins></libpart></libparts><nets>"
                '<net name="CLK_SOURCE"><node ref="X1" pin="1"/>'
                '<node ref="R1" pin="1"/></net>'
                '<net name="CLK_LOAD"><node ref="R1" pin="2"/>'
                '<node ref="U2" pin="2"/><node ref="U3" pin="3"/></net>'
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
                        basis="Synthetic oscillator output path parity fixture"
                    ),
                }
            ),
        )
        contract_path = self.island / "tests/contract.json"
        contract = read_model(contract_path, ProjectTestContract)
        write_model(
            contract_path,
            contract.model_copy(
                update={
                    "design_lint": DesignLintPolicy(
                        oscillator_output_path_map=oscillator_output_path_map()
                    )
                }
            ),
        )

        async with Client(create_server(self.root), mode="legacy") as client:

            async def compare(value: str, expected_exit: int) -> DesignLintReport:
                write_netlist(value)
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
                return mcp

            control = await compare("33R", 1)
            self.assertEqual(control.status, "REVIEW", control.issues)
            self.assertNotIn(
                "oscillator.output_load_path_mismatch",
                {item.rule_id for item in control.findings},
            )

            fault = await compare("1k", 1)
            self.assertEqual(fault.status, "REVIEW", fault.issues)
            finding = next(
                item
                for item in fault.findings
                if item.rule_id == "oscillator.output_load_path_mismatch"
            )
            self.assertTrue(
                any(
                    "nominal resistance is 1000 ohms" in issue
                    for issue in finding.evidence["issues"]
                )
            )


def test_oscillator_output_path_matches_cli_and_mcp() -> None:
    run_mcp_parity(
        _OscillatorOutputPathParityCases,
        "_case_test_oscillator_output_path_matches_cli_and_mcp",
    )
