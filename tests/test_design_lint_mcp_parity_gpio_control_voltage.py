"""CLI/MCP parity for the GPIO-to-control-input voltage review rule."""

from __future__ import annotations

import pytest

pytestmark = [
    pytest.mark.parity_lint,
    pytest.mark.slow,
    pytest.mark.template_checkout,
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.power_lint,
]

from mcp import Client

from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    DesignLintReport,
    NetlistContract,
)
from tests.component_peer_power_assignment_support import peer_pin_netlist_xml
from tests.mcp_parity_support import McpParityHarness, run_mcp_parity

RULE_ID = "power.gpio_to_control_input_voltage_review"


def _gpio_control_netlist(output_rail: str, input_rail: str) -> NetlistContract:
    return NetlistContract(
        components={
            "U1": ComponentContract(value="Synthetic GPIO controller", footprint="Synthetic:QFN"),
            "U2": ComponentContract(value="Synthetic control receiver", footprint="Synthetic:QFN"),
        },
        nets={
            "CONTROL_SIGNAL": ("U1.1", "U2.1"),
            output_rail: ("U1.2",),
            input_rail: ("U2.2",),
            "GND": ("U1.3", "U2.3"),
        },
        component_symbols={"U1": "Synthetic:GpioController", "U2": "Synthetic:ControlReceiver"},
        component_pin_numbers={"U1": ("1", "2", "3"), "U2": ("1", "2", "3")},
        pin_functions={
            "U1.1": "GPIO0",
            "U1.2": "VDD",
            "U1.3": "GND",
            "U2.1": "EN",
            "U2.2": "VDD",
            "U2.3": "GND",
        },
        pin_electrical_types={
            "U1.1": "output",
            "U1.2": "power_in",
            "U1.3": "power_in",
            "U2.1": "input",
            "U2.2": "power_in",
            "U2.3": "power_in",
        },
    )


class _GpioControlVoltageParityCases(McpParityHarness):
    async def _case_gpio_control_voltage_fault_and_control_match_between_cli_and_mcp(self) -> None:
        native = self.native_evidence()
        netlist_path = native.parent / "netlist.xml"

        async with Client(create_server(self.root), mode="legacy") as client:
            for case, output_rail, input_rail, expected_findings in (
                ("fault", "+5V", "+3V3", 1),
                ("control", "+3V3", "+5V", 0),
            ):
                with self.subTest(case=case):
                    netlist_path.write_text(
                        peer_pin_netlist_xml(_gpio_control_netlist(output_rail, input_rail)),
                        encoding="utf-8",
                    )
                    self.rehash_native_netlist(native)
                    cli = await self.cli(
                        "kicad_tooling.design_lint",
                        DesignLintReport,
                        "--project",
                        "controller",
                        "--native-summary",
                        str(native),
                        expected_exit=1,
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
                    cli_findings = tuple(item for item in cli.findings if item.rule_id == RULE_ID)
                    mcp_findings = tuple(item for item in mcp.findings if item.rule_id == RULE_ID)

                    self.assertEqual(cli.status, mcp.status)
                    self.assertEqual(cli_findings, mcp_findings)
                    self.assertEqual(len(cli_findings), expected_findings)


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_gpio_control_voltage_fault_and_control_match_between_cli_and_mcp() -> None:
    run_mcp_parity(
        _GpioControlVoltageParityCases,
        "_case_gpio_control_voltage_fault_and_control_match_between_cli_and_mcp",
    )
