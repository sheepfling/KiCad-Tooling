"""CLI and MCP parity for Ethernet PHY RX output-sharing evidence."""

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
from kicad_tooling.hwrepo.models import DesignLintReport
from tests.component_peer_power_assignment_support import peer_pin_netlist_xml
from tests.design_lint_fixtures.ethernet_crs_output_sharing import (
    ethernet_mii_crs_output_netlist,
)
from tests.design_lint_fixtures.ethernet_rx_clock_output_sharing import (
    ethernet_rx_clock_output_netlist,
)
from tests.design_lint_fixtures.ethernet_rx_output_sharing import ethernet_rx_output_netlist
from tests.design_lint_fixtures.ethernet_rx_status_output_sharing import (
    ethernet_rx_status_output_netlist,
)
from tests.design_lint_fixtures.ethernet_tx_clock_output_sharing import (
    ethernet_mii_tx_clock_output_netlist,
)
from tests.mcp_parity_support import McpParityHarness, run_mcp_parity

RULE_ID = "bus.ethernet_rx_outputs_share_net"
CLOCK_RULE_ID = "bus.ethernet_rx_clock_outputs_share_net"
STATUS_RULE_ID = "bus.ethernet_rx_status_outputs_share_net"
CRS_DV_RULE_ID = "bus.ethernet_crs_dv_outputs_share_net"
CRS_RULE_ID = "bus.ethernet_crs_outputs_share_net"
TX_CLOCK_RULE_ID = "bus.ethernet_tx_clock_outputs_share_net"


class _EthernetRxOutputSharingParity(McpParityHarness):
    async def _case_ethernet_rx_output_sharing_cli_mcp_parity(self) -> None:
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"
        netlist.write_text(peer_pin_netlist_xml(ethernet_rx_output_netlist()), encoding="utf-8")
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

        assert cli == mcp
        findings = tuple(item for item in cli.findings if item.rule_id == RULE_ID)
        assert len(findings) == 1
        assert findings[0].subject == (
            "U1, U2: Ethernet PHY receive-data outputs share ETH_RXD_SHARED"
        )
        assert findings[0].evidence["pins"] == ("U1.1", "U2.1")

    async def _case_ethernet_rx_clock_output_sharing_cli_mcp_parity(self) -> None:
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"
        netlist.write_text(
            peer_pin_netlist_xml(ethernet_rx_clock_output_netlist()), encoding="utf-8"
        )
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

        assert cli == mcp
        findings = tuple(item for item in cli.findings if item.rule_id == CLOCK_RULE_ID)
        assert len(findings) == 1
        assert findings[0].subject == (
            "U1, U2: Ethernet PHY receive-clock outputs share MII_RX_CLK_SHARED"
        )
        assert findings[0].evidence["pins"] == ("U1.1", "U2.1")

    async def _case_ethernet_rx_status_output_sharing_cli_mcp_parity(self) -> None:
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"
        netlist.write_text(
            peer_pin_netlist_xml(ethernet_rx_status_output_netlist()), encoding="utf-8"
        )
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

        assert cli == mcp
        findings = tuple(item for item in cli.findings if item.rule_id == STATUS_RULE_ID)
        assert len(findings) == 1
        assert findings[0].subject == (
            "U1, U2: Ethernet PHY receive-status outputs share MII_RX_DV_SHARED"
        )
        assert findings[0].evidence["pins"] == ("U1.1", "U2.1")

    async def _case_ethernet_crs_dv_output_sharing_cli_mcp_parity(self) -> None:
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"
        netlist.write_text(
            peer_pin_netlist_xml(
                ethernet_rx_status_output_netlist(
                    status_functions=("CRS_DV", "CRS_DV"),
                    status_net_name="RMII_CRS_DV_SHARED",
                )
            ),
            encoding="utf-8",
        )
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

        assert cli == mcp
        findings = tuple(item for item in cli.findings if item.rule_id == CRS_DV_RULE_ID)
        assert len(findings) == 1
        assert findings[0].subject == (
            "U1, U2: Ethernet PHY CRS_DV outputs share RMII_CRS_DV_SHARED"
        )
        assert findings[0].evidence["pins"] == ("U1.1", "U2.1")

    async def _case_ethernet_crs_output_sharing_cli_mcp_parity(self) -> None:
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"
        netlist.write_text(
            peer_pin_netlist_xml(ethernet_mii_crs_output_netlist()),
            encoding="utf-8",
        )
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

        assert cli == mcp
        findings = tuple(item for item in cli.findings if item.rule_id == CRS_RULE_ID)
        assert len(findings) == 1
        assert findings[0].subject == ("U1, U2: Ethernet PHY CRS outputs share MII_CRS_SHARED")
        assert findings[0].evidence["pins"] == ("U1.1", "U2.1")

    async def _case_ethernet_tx_clock_output_sharing_cli_mcp_parity(self) -> None:
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"
        netlist.write_text(
            peer_pin_netlist_xml(ethernet_mii_tx_clock_output_netlist()),
            encoding="utf-8",
        )
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

        assert cli == mcp
        findings = tuple(item for item in cli.findings if item.rule_id == TX_CLOCK_RULE_ID)
        assert len(findings) == 1
        assert findings[0].subject == (
            "U1, U2: Ethernet PHY TX_CLK outputs share MII_TX_CLK_SHARED"
        )
        assert findings[0].evidence["pins"] == ("U1.1", "U2.1")


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_ethernet_rx_output_sharing_cli_mcp_parity() -> None:
    run_mcp_parity(
        _EthernetRxOutputSharingParity,
        "_case_ethernet_rx_output_sharing_cli_mcp_parity",
    )


@pytest.mark.design_lint_rule(rule_id=CLOCK_RULE_ID)
def test_ethernet_rx_clock_output_sharing_cli_mcp_parity() -> None:
    run_mcp_parity(
        _EthernetRxOutputSharingParity,
        "_case_ethernet_rx_clock_output_sharing_cli_mcp_parity",
    )


@pytest.mark.design_lint_rule(rule_id=STATUS_RULE_ID)
def test_ethernet_rx_status_output_sharing_cli_mcp_parity() -> None:
    run_mcp_parity(
        _EthernetRxOutputSharingParity,
        "_case_ethernet_rx_status_output_sharing_cli_mcp_parity",
    )


@pytest.mark.design_lint_rule(rule_id=CRS_DV_RULE_ID)
def test_ethernet_crs_dv_output_sharing_cli_mcp_parity() -> None:
    run_mcp_parity(
        _EthernetRxOutputSharingParity,
        "_case_ethernet_crs_dv_output_sharing_cli_mcp_parity",
    )


@pytest.mark.design_lint_rule(rule_id=CRS_RULE_ID)
def test_ethernet_crs_output_sharing_cli_mcp_parity() -> None:
    run_mcp_parity(
        _EthernetRxOutputSharingParity,
        "_case_ethernet_crs_output_sharing_cli_mcp_parity",
    )


@pytest.mark.design_lint_rule(rule_id=TX_CLOCK_RULE_ID)
def test_ethernet_tx_clock_output_sharing_cli_mcp_parity() -> None:
    run_mcp_parity(
        _EthernetRxOutputSharingParity,
        "_case_ethernet_tx_clock_output_sharing_cli_mcp_parity",
    )
