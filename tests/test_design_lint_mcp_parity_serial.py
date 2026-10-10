"""Design-lint CLI/MCP parity cases: design lint mcp parity serial."""

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
    ValidationSummary,
)
from tests.mcp_parity_support import (
    McpParityHarness,
    run_mcp_parity,
)


class _DesignLintMcpParitySerialCases(McpParityHarness):
    async def _case_test_serial_peer_voltage_lint_cli_mcp_parity(self) -> None:
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"
        content = netlist.read_text(encoding="utf-8")
        content = content.replace(
            "</components>",
            """<comp ref="U20"><value>Synthetic UART transmitter</value>
<footprint>Package:UART-TX</footprint><libsource lib="Synthetic" part="UartTX"/></comp>
<comp ref="U21"><value>Synthetic UART receiver</value>
<footprint>Package:UART-RX</footprint><libsource lib="Synthetic" part="UartRX"/></comp>
</components><libparts>
<libpart lib="Synthetic" part="UartTX"><pins>
<pin num="1" name="UART1_TX" type="output"/>
<pin num="8" name="VDD" type="power_in"/>
<pin num="9" name="GND" type="power_in"/>
</pins></libpart>
<libpart lib="Synthetic" part="UartRX"><pins>
<pin num="1" name="UART1_RX" type="input"/>
<pin num="8" name="VDD" type="power_in"/>
<pin num="9" name="GND" type="power_in"/>
</pins></libpart>
</libparts>""",
            1,
        )
        content = content.replace(
            "<nets/>",
            """<nets>
<net name="UART_TX"><node ref="U20" pin="1"/><node ref="U21" pin="1"/></net>
<net name="+5V"><node ref="U20" pin="8"/></net>
<net name="+3V3"><node ref="U21" pin="8"/></net>
<net name="GND_A"><node ref="U20" pin="9"/></net>
<net name="GND_B"><node ref="U21" pin="9"/></net>
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
            item for item in mcp.findings if item.rule_id == "bus.serial_peer_voltage_review"
        )
        self.assertEqual(finding.subject, "U20 -> U21: serial voltage-domain review")
        self.assertEqual(finding.evidence["output_supply_label_value"], ("5 V",))
        self.assertEqual(finding.evidence["input_supply_label_value"], ("3.3 V",))
        self.assertEqual(
            finding.evidence["shared_serial_pin_assignments"],
            ("UART_TX: U20.1 (UART1_TX, output) -> U21.1 (UART1_RX, input)",),
        )
        coverage = next(
            item
            for item in mcp.digital_peer_voltage_coverage
            if item.rule_id == "bus.serial_peer_voltage_review"
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
        reference_finding = next(
            item for item in mcp.findings if item.rule_id == "bus.serial_peer_reference_review"
        )
        self.assertEqual(reference_finding.subject, "U20 / U21: serial reference-domain review")
        self.assertEqual(reference_finding.mode, "review")
        self.assertEqual(reference_finding.evidence["first_reference_net"], ("GND_A",))
        self.assertEqual(reference_finding.evidence["second_reference_net"], ("GND_B",))
        self.assertEqual(
            reference_finding.evidence["shared_serial_pin_assignments"],
            ("UART_TX: U20.1 (UART1_TX, output) -> U21.1 (UART1_RX, input)",),
        )

    async def _case_test_serial_connector_reference_lint_cli_mcp_parity(self) -> None:
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"
        netlist.write_text(
            """<export>
  <components>
    <comp ref="J1"><value>Synthetic UART header</value>
      <footprint>Package:UART-HEADER</footprint><libsource lib="Synthetic" part="UartHeader"/></comp>
    <comp ref="U20"><value>Synthetic UART controller</value>
      <footprint>Package:UART-CONTROLLER</footprint><libsource lib="Synthetic" part="UartController"/></comp>
  </components>
  <libparts>
    <libpart lib="Synthetic" part="UartHeader"><pins>
      <pin num="1" name="UART1_RX" type="input"/>
      <pin num="2" name="UART1_TX" type="output"/>
      <pin num="8" name="VDD" type="passive"/>
      <pin num="9" name="GND" type="passive"/>
    </pins></libpart>
    <libpart lib="Synthetic" part="UartController"><pins>
      <pin num="1" name="UART1_TX" type="output"/>
      <pin num="2" name="UART1_RX" type="input"/>
      <pin num="8" name="VDD" type="power_in"/>
      <pin num="9" name="GND" type="power_in"/>
    </pins></libpart>
  </libparts>
  <nets>
    <net name="UART_TX"><node ref="U20" pin="1"/><node ref="J1" pin="1"/></net>
    <net name="UART_RX"><node ref="U20" pin="2"/><node ref="J1" pin="2"/></net>
    <net name="+3V3"><node ref="U20" pin="8"/><node ref="J1" pin="8"/></net>
    <net name="GND_A"><node ref="U20" pin="9"/></net>
    <net name="GND_B"><node ref="J1" pin="9"/></net>
  </nets>
</export>
""",
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
            item for item in mcp.findings if item.rule_id == "bus.serial_peer_reference_review"
        )
        self.assertEqual(finding.subject, "J1 / U20: serial reference-domain review")
        self.assertEqual(finding.evidence["first_reference_net"], ("GND_B",))
        self.assertEqual(finding.evidence["second_reference_net"], ("GND_A",))
        self.assertEqual(
            finding.evidence["shared_serial_pin_assignments"],
            (
                "UART_RX: J1.2 (UART1_TX, output) -> U20.2 (UART1_RX, input)",
                "UART_TX: U20.1 (UART1_TX, output) -> J1.1 (UART1_RX, input)",
            ),
        )
        coverage = mcp.serial_peer_reference_coverage
        self.assertIsNotNone(coverage)
        assert coverage is not None
        self.assertEqual(
            tuple(
                (
                    item.discovery_basis,
                    item.first_reference,
                    item.second_reference,
                    item.signal_group,
                    item.signal_pins,
                    item.disposition,
                )
                for item in coverage.link_entries or ()
            ),
            (
                (
                    "native_function",
                    "J1",
                    "U20",
                    "UART_RX",
                    ("J1.2", "U20.2"),
                    "SEPARATE_REFERENCE_REVIEW",
                ),
                (
                    "native_function",
                    "U20",
                    "J1",
                    "UART_TX",
                    ("U20.1", "J1.1"),
                    "SEPARATE_REFERENCE_REVIEW",
                ),
            ),
        )


def test_serial_peer_voltage_lint_cli_mcp_parity() -> None:
    run_mcp_parity(
        _DesignLintMcpParitySerialCases, "_case_test_serial_peer_voltage_lint_cli_mcp_parity"
    )


def test_serial_connector_reference_lint_cli_mcp_parity() -> None:
    run_mcp_parity(
        _DesignLintMcpParitySerialCases, "_case_test_serial_connector_reference_lint_cli_mcp_parity"
    )
