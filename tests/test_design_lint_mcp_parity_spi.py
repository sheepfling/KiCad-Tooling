"""Design-lint CLI/MCP parity cases: design lint mcp parity spi."""

from __future__ import annotations

import pytest

pytestmark = [
    pytest.mark.parity_lint,
    pytest.mark.slow,
    pytest.mark.template_checkout,
    pytest.mark.design_lint,
]

from mcp import Client

from kicad_tooling.hwrepo.contracts import (
    read_model,
    write_model,
)
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    DesignLintReport,
    NetlistContract,
    ValidationSummary,
)
from tests.design_lint_fixtures import header_only_spi_uart_netlist
from tests.mcp_parity_support import (
    McpParityHarness,
    run_mcp_parity,
)
from tests.test_electrical_parity import contract_netlist_xml


class _DesignLintMcpParitySpiCases(McpParityHarness):
    async def _case_test_spi_peer_voltage_lint_cli_mcp_parity(self) -> None:
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"
        content = netlist.read_text(encoding="utf-8")
        content = content.replace(
            "</components>",
            """<comp ref="U20"><value>Synthetic SPI controller</value>
<footprint>Package:Controller</footprint><libsource lib="Synthetic" part="Controller"/></comp>
<comp ref="U21"><value>Synthetic SPI peripheral</value>
<footprint>Package:Peripheral</footprint><libsource lib="Synthetic" part="Peripheral"/></comp>
</components><libparts>
<libpart lib="Synthetic" part="Controller"><pins>
<pin num="1" name="MOSI" type="output"/>
<pin num="8" name="VDD" type="power_in"/>
<pin num="9" name="GND" type="power_in"/>
</pins></libpart>
<libpart lib="Synthetic" part="Peripheral"><pins>
<pin num="1" name="MOSI" type="input"/>
<pin num="8" name="VDD" type="power_in"/>
<pin num="9" name="GND" type="power_in"/>
</pins></libpart>
</libparts>""",
            1,
        )
        content = content.replace(
            "<nets/>",
            """<nets>
<net name="SPI_MOSI"><node ref="U20" pin="1"/><node ref="U21" pin="1"/></net>
<net name="+5V"><node ref="U20" pin="8"/></net>
<net name="+3V3"><node ref="U21" pin="8"/></net>
<net name="GND"><node ref="U20" pin="9"/><node ref="U21" pin="9"/></net>
</nets>""",
            1,
        )
        netlist.write_text(content, encoding="utf-8")
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
        self.assertEqual(cli, mcp)
        self.assertEqual(mcp.status, "REVIEW")
        finding = next(
            item for item in mcp.findings if item.rule_id == "bus.spi_peer_voltage_review"
        )
        self.assertEqual(finding.subject, "U20 -> U21: SPI voltage-domain review")
        self.assertEqual(finding.evidence["output_supply_label_value"], ("5 V",))
        self.assertEqual(finding.evidence["input_supply_label_value"], ("3.3 V",))
        self.assertEqual(
            finding.evidence["shared_SPI_pin_assignments"],
            ("SPI_MOSI: U20.1 (MOSI, output) -> U21.1 (MOSI, input)",),
        )
        coverage = next(
            item
            for item in mcp.digital_peer_voltage_coverage
            if item.rule_id == "bus.spi_peer_voltage_review"
        )
        self.assertEqual(
            (
                coverage.status,
                coverage.recognized_endpoint_count,
                coverage.assigned_endpoint_count,
                coverage.direct_peer_link_count,
                coverage.voltage_comparison_count,
                coverage.different_voltage_link_count,
                coverage.candidate_group_count,
            ),
            ("EVALUATED", 2, 2, 1, 1, 1, 1),
        )

    async def _case_test_header_only_spi_uart_voltage_boundary_cli_mcp_parity(self) -> None:
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"
        header_netlist: NetlistContract = header_only_spi_uart_netlist()
        netlist.write_text(contract_netlist_xml(header_netlist), encoding="utf-8")
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
        self.assertEqual(cli, mcp)
        coverage = {item.rule_id: item for item in mcp.digital_peer_voltage_coverage}
        for rule_id in ("bus.spi_peer_voltage_review", "bus.serial_peer_voltage_review"):
            with self.subTest(rule_id=rule_id):
                item = coverage[rule_id]
                self.assertEqual(
                    (
                        item.status,
                        item.recognized_endpoint_count,
                        item.assigned_endpoint_count,
                        item.direct_peer_link_count,
                        item.voltage_comparison_count,
                        item.candidate_group_count,
                    ),
                    ("NO_SUPPORTED_ENDPOINTS", 0, 0, 0, 0, 0),
                )
        self.assertFalse(
            {
                "bus.spi_peer_voltage_review",
                "bus.serial_peer_voltage_review",
            }
            & {item.rule_id for item in mcp.findings}
        )


def test_spi_peer_voltage_lint_cli_mcp_parity() -> None:
    run_mcp_parity(_DesignLintMcpParitySpiCases, "_case_test_spi_peer_voltage_lint_cli_mcp_parity")


def test_header_only_spi_uart_voltage_boundary_cli_mcp_parity() -> None:
    run_mcp_parity(
        _DesignLintMcpParitySpiCases,
        "_case_test_header_only_spi_uart_voltage_boundary_cli_mcp_parity",
    )
