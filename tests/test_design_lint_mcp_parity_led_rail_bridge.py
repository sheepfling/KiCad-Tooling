"""CLI/MCP parity for direct LED supply/return bridge review."""

from __future__ import annotations

import pytest

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.component_lint,
    pytest.mark.evidence_lint,
    pytest.mark.parity_lint,
    pytest.mark.slow,
    pytest.mark.template_checkout,
]

from mcp import Client

from kicad_tooling.hwrepo.contracts import parse_model_text, read_model, write_model
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import DesignLintReport, ValidationSummary
from tests.mcp_parity_support import McpParityHarness, run_mcp_parity


class _LedRailBridgeParityCases(McpParityHarness):
    async def _case_test_led_rail_bridge_cli_mcp_parity(self) -> None:
        """A direct LED rail bridge has equal evidence through CLI and MCP."""
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"
        summary = read_model(native, ValidationSummary)

        def write_netlist(series_resistor: bool) -> None:
            resistor_component = (
                '<comp ref="R1"><value>1k</value><libsource lib="Device" part="R"/></comp>'
                if series_resistor
                else ""
            )
            resistor_libpart = (
                '<libpart lib="Device" part="R"><pins>'
                '<pin num="1" name="~" type="passive"/>'
                '<pin num="2" name="~" type="passive"/>'
                "</pins></libpart>"
                if series_resistor
                else ""
            )
            rail_nets = (
                '<net name="+3V3"><node ref="R1" pin="1"/></net>'
                '<net name="LED_ANODE"><node ref="R1" pin="2"/>'
                '<node ref="D1" pin="1"/></net>'
                if series_resistor
                else '<net name="+3V3"><node ref="D1" pin="1"/></net>'
            )
            netlist.write_text(
                "<export><components>"
                '<comp ref="D1"><value>LED</value>'
                '<libsource lib="Device" part="LED"/></comp>'
                f"{resistor_component}</components><libparts>"
                '<libpart lib="Device" part="LED"><pins>'
                '<pin num="1" name="A" type="passive"/>'
                '<pin num="2" name="K" type="passive"/>'
                f"</pins></libpart>{resistor_libpart}</libparts><nets>"
                f'{rail_nets}<net name="GND"><node ref="D1" pin="2"/></net>'
                "</nets></export>",
                encoding="utf-8",
            )
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

            async def compare() -> DesignLintReport:
                process = await self.cli_process(
                    "kicad_tooling.design_lint",
                    "--project",
                    "controller",
                    "--native-summary",
                    str(native),
                )
                cli = parse_model_text(process.stdout, DesignLintReport)
                self.assertEqual(process.returncode, 1 if cli.status != "PASS" else 0)
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

            write_netlist(series_resistor=False)
            fault = await compare()
            rule_id = "component.led_directly_across_supply_and_return"
            finding = next(item for item in fault.findings if item.rule_id == rule_id)
            self.assertEqual(finding.evidence["led_pins"], ("D1.1", "D1.2"))
            self.assertEqual(finding.evidence["positive_net"], ("+3V3",))
            self.assertEqual(finding.evidence["return_net"], ("GND",))

            write_netlist(series_resistor=True)
            control = await compare()
            self.assertNotIn(rule_id, {item.rule_id for item in control.findings})


def test_led_rail_bridge_cli_mcp_parity() -> None:
    run_mcp_parity(_LedRailBridgeParityCases, "_case_test_led_rail_bridge_cli_mcp_parity")
