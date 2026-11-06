"""CLI/MCP parity for USB SuperSpeed IC pin and net-label review."""

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

from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.mcp_server import create_server
from tests.mcp_parity_support import McpParityHarness, run_mcp_parity

RULE_ID = "bus.usb_c_superspeed_lane_label_mismatch"


class _UsbIcLaneLabelParityCases(McpParityHarness):
    async def _case_test_usb_ic_lane_label_cli_mcp_parity(self) -> None:
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"
        pin_names = ("TX1_P", "TX1_N", "RX1_P", "RX1_N")

        def write_netlist(*, mismatch: bool) -> None:
            net_names = (
                ("USBC0_RX1_P", "USBC0_TX1_N", "USBC0_RX1_P", "USBC0_RX1_N")
                if mismatch
                else ("USBC0_TX1_P", "USBC0_TX1_N", "USBC0_RX1_P", "USBC0_RX1_N")
            )
            pins = "".join(
                f'<pin num="{index}" name="{name}" type="bidirectional"/>'
                for index, name in enumerate(pin_names, 1)
            )
            nodes_by_net: dict[str, list[str]] = {}
            for index, name in enumerate(net_names, 1):
                nodes_by_net.setdefault(name, []).append(f'<node ref="U1" pin="{index}"/>')
            nets = "".join(
                f'<net name="{name}">{"".join(nodes)}</net>'
                for name, nodes in sorted(nodes_by_net.items())
            )
            netlist.write_text(
                "<export><components>"
                '<comp ref="U1"><value>Synthetic USB SuperSpeed mux</value>'
                "<footprint>Synthetic:QFN</footprint>"
                '<libsource lib="Synthetic" part="UsbMux"/></comp>'
                "</components><libparts>"
                '<libpart lib="Synthetic" part="UsbMux"><pins>'
                f"{pins}</pins></libpart></libparts><nets>{nets}</nets></export>",
                encoding="utf-8",
            )
            self.rehash_native_netlist(native)

        async with Client(create_server(self.root), mode="legacy") as client:

            async def compare(*, mismatch: bool) -> DesignLintReport:
                write_netlist(mismatch=mismatch)
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
                self.assertEqual(cli, mcp)
                return mcp

            fault = await compare(mismatch=True)
            findings = tuple(item for item in fault.findings if item.rule_id == RULE_ID)
            self.assertEqual(len(findings), 1)
            self.assertEqual(
                findings[0].subject,
                "U1.1: TX1_P on USBC0_RX1_P",
            )
            control = await compare(mismatch=False)
            self.assertNotIn(RULE_ID, {item.rule_id for item in control.findings})


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_usb_ic_lane_label_cli_mcp_parity() -> None:
    run_mcp_parity(
        _UsbIcLaneLabelParityCases,
        "_case_test_usb_ic_lane_label_cli_mcp_parity",
    )
