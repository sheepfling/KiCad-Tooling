"""CLI/MCP parity for asymmetric USB-C SBU assignment review."""

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

from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    DesignLintReport,
    NetlistContract,
)
from tests.component_peer_power_assignment_support import peer_pin_netlist_xml
from tests.mcp_parity_support import McpParityHarness, run_mcp_parity

RULE_ID = "bus.usb_c_sbu_unconnected_pin"
SAME_NET_RULE_ID = "bus.usb_c_sbu_same_net"


class _UsbCSbuUnconnectedParityCases(McpParityHarness):
    async def _case_usb_c_sbu_unconnected_cli_mcp_parity(self) -> None:
        native = self.native_evidence()
        observed = NetlistContract(
            components={
                "U1": ComponentContract(
                    value="Synthetic USB-C controller", footprint="Synthetic:QFN"
                )
            },
            nets={"SBU2_BUS": ("U1.2",)},
            component_symbols={"U1": "Synthetic:USB_C_Controller"},
            pin_functions={"U1.1": "SBU1", "U1.2": "SBU2"},
            component_pin_numbers={"U1": ("1", "2")},
        )
        (native.parent / "netlist.xml").write_text(peer_pin_netlist_xml(observed), encoding="utf-8")
        self.rehash_native_netlist(native)

        async with Client(create_server(self.root), mode="legacy") as client:
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
        self.assertEqual(len(cli_findings), 1)
        self.assertEqual(cli_findings[0].subject, "U1.1: SBU1")

    async def _case_usb_c_sbu_same_net_cli_mcp_parity(self) -> None:
        native = self.native_evidence()
        observed = NetlistContract(
            components={
                "U1": ComponentContract(
                    value="Synthetic USB-C controller", footprint="Synthetic:QFN"
                )
            },
            nets={"SBU_SHARED": ("U1.1", "U1.2")},
            component_symbols={"U1": "Synthetic:USB_C_Controller"},
            pin_functions={"U1.1": "SBU1", "U1.2": "SBU2"},
            component_pin_numbers={"U1": ("1", "2")},
        )
        (native.parent / "netlist.xml").write_text(peer_pin_netlist_xml(observed), encoding="utf-8")
        self.rehash_native_netlist(native)

        async with Client(create_server(self.root), mode="legacy") as client:
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
        cli_findings = tuple(item for item in cli.findings if item.rule_id == SAME_NET_RULE_ID)
        mcp_findings = tuple(item for item in mcp.findings if item.rule_id == SAME_NET_RULE_ID)

        self.assertEqual(cli.status, mcp.status)
        self.assertEqual(cli_findings, mcp_findings)
        self.assertEqual(len(cli_findings), 1)
        self.assertEqual(cli_findings[0].subject, "U1: USB-C SBU1/SBU2 pins share SBU_SHARED")


def test_usb_c_sbu_unconnected_cli_mcp_parity() -> None:
    run_mcp_parity(
        _UsbCSbuUnconnectedParityCases,
        "_case_usb_c_sbu_unconnected_cli_mcp_parity",
    )


@pytest.mark.design_lint_rule(rule_id=SAME_NET_RULE_ID)
def test_usb_c_sbu_same_net_cli_mcp_parity() -> None:
    run_mcp_parity(
        _UsbCSbuUnconnectedParityCases,
        "_case_usb_c_sbu_same_net_cli_mcp_parity",
    )
