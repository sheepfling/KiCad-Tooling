"""CLI/MCP parity for unconnected named component supply and return pins."""

from __future__ import annotations

import pytest

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.component_lint,
    pytest.mark.power_lint,
    pytest.mark.evidence_lint,
    pytest.mark.parity_lint,
    pytest.mark.slow,
    pytest.mark.template_checkout,
]

from mcp import Client

from kicad_tooling.hwrepo.contracts import parse_model_text, read_model, write_model
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    DesignLintPolicy,
    DesignLintReport,
    DesignLintRuleOverride,
    ProjectTestContract,
    ValidationSummary,
)
from tests.mcp_parity_support import McpParityHarness, run_mcp_parity


class _UnconnectedNamedComponentPinsParityCases(McpParityHarness):
    async def _case_test_named_supply_return_cli_mcp_parity(self) -> None:
        """Named supply and return open pins match across CLI and MCP surfaces."""
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"
        summary = read_model(native, ValidationSummary)
        contract_path = self.island / "tests/contract.json"
        contract = read_model(contract_path, ProjectTestContract)
        policy = contract.design_lint or DesignLintPolicy()
        write_model(
            contract_path,
            contract.model_copy(
                update={
                    "design_lint": policy.model_copy(
                        update={
                            "rules": (
                                *policy.rules,
                                DesignLintRuleOverride(
                                    rule_id="power.ic_rail_without_fitted_capacitor",
                                    mode="off",
                                    reason=(
                                        "Synthetic named-pin parity case isolates the open-pin "
                                        "review and has no decoupling-capacitor inventory"
                                    ),
                                ),
                            )
                        }
                    )
                }
            ),
        )

        def write_netlist(connected: bool) -> None:
            named_nets = (
                '<net name="SUPPLY_TEST"><node ref="U1" pin="1"/></net>'
                '<net name="RETURN_TEST"><node ref="U1" pin="2"/></net>'
                if connected
                else ""
            )
            netlist.write_text(
                "<export><components>"
                '<comp ref="U1"><value>Synthetic logic</value>'
                "<footprint>Synthetic:Logic</footprint>"
                '<libsource lib="Synthetic" part="NamedPowerLogic"/>'
                "</comp></components><libparts>"
                '<libpart lib="Synthetic" part="NamedPowerLogic"><pins>'
                '<pin num="1" name="VDD" type="power_in"/>'
                '<pin num="2" name="GND" type="power_in"/>'
                '<pin num="3" name="IN" type="input"/>'
                "</pins></libpart></libparts><nets>"
                '<net name="SIGNAL"><node ref="U1" pin="3"/></net>'
                f"{named_nets}</nets></export>",
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

            write_netlist(connected=False)
            fault = await compare()
            expected_rules = {
                "component.unconnected_supply_pin",
                "component.unconnected_return_pin",
            }
            self.assertEqual(fault.status, "REVIEW", fault.issues)
            self.assertEqual({item.rule_id for item in fault.findings}, expected_rules)
            findings = {item.rule_id: item for item in fault.findings}
            self.assertEqual(
                findings["component.unconnected_supply_pin"].evidence,
                {"U1.1": ()},
            )
            self.assertEqual(
                findings["component.unconnected_return_pin"].evidence,
                {"U1.2": ()},
            )

            write_netlist(connected=True)
            control = await compare()
            self.assertEqual(
                control.status,
                "PASS",
                tuple((item.rule_id, item.subject, item.evidence) for item in control.findings),
            )
            self.assertFalse(expected_rules & {item.rule_id for item in control.findings})


def test_named_supply_return_pins_cli_mcp_parity() -> None:
    run_mcp_parity(
        _UnconnectedNamedComponentPinsParityCases,
        "_case_test_named_supply_return_cli_mcp_parity",
    )
