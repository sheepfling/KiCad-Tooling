"""CLI/MCP parity for bounded USB peer-reference lint."""

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
    DesignLintPolicy,
    DesignLintReport,
    ProjectTestContract,
    ValidationSummary,
)
from tests.mcp_parity_support import McpParityHarness, run_mcp_parity
from tests.usb_peer_reference_support import PATH_RULE_ID, RULE_ID
from tests.usb_peer_superspeed_support import superspeed_reference_map


class _DesignLintMcpParityUsbReferenceCases(McpParityHarness):
    async def _case_test_usb_peer_reference_lint_cli_mcp_parity(self) -> None:
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"

        def write_netlist(*, split_reference: bool) -> None:
            if split_reference:
                reference_nets = (
                    '<net name="USB_GND"><node ref="J1" pin="4"/></net>'
                    '<net name="BOARD_GND"><node ref="U1" pin="3"/></net>'
                )
            else:
                reference_nets = (
                    '<net name="BOARD_GND"><node ref="J1" pin="4"/><node ref="U1" pin="3"/></net>'
                )
            netlist.write_text(
                "<export><components>"
                '<comp ref="J1"><value>Synthetic USB connector</value>'
                "<footprint>Synthetic:USB-A</footprint>"
                '<libsource lib="Connector" part="USB_A"/></comp>'
                '<comp ref="U1"><value>Synthetic USB PHY</value>'
                "<footprint>Synthetic:QFN</footprint>"
                '<libsource lib="Synthetic" part="UsbPhy"/></comp>'
                "</components><libparts>"
                '<libpart lib="Connector" part="USB_A"><pins>'
                '<pin num="1" name="D+" type="passive"/>'
                '<pin num="2" name="D-" type="passive"/>'
                '<pin num="4" name="GND" type="passive"/>'
                "</pins></libpart>"
                '<libpart lib="Synthetic" part="UsbPhy"><pins>'
                '<pin num="1" name="USB_DP" type="input"/>'
                '<pin num="2" name="USB_DM" type="input"/>'
                '<pin num="3" name="VSS" type="unspecified"/>'
                "</pins></libpart></libparts><nets>"
                '<net name="USB_DP"><node ref="J1" pin="1"/>'
                '<node ref="U1" pin="1"/></net>'
                '<net name="USB_DM"><node ref="J1" pin="2"/>'
                '<node ref="U1" pin="2"/></net>'
                f"{reference_nets}</nets></export>",
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

        def write_multiport_netlist(*, split_references: bool) -> None:
            if split_references:
                reference_nets = (
                    '<net name="USB1_GND"><node ref="J1" pin="3"/></net>'
                    '<net name="USB2_GND"><node ref="J2" pin="3"/></net>'
                    '<net name="PHY_GND"><node ref="U1" pin="3"/>'
                    '<node ref="U1" pin="6"/></net>'
                )
            else:
                reference_nets = (
                    '<net name="BOARD_GND"><node ref="J1" pin="3"/>'
                    '<node ref="J2" pin="3"/><node ref="U1" pin="3"/>'
                    '<node ref="U1" pin="6"/></net>'
                )
            netlist.write_text(
                "<export><components>"
                '<comp ref="J1"><value>Synthetic USB-A port 1</value>'
                "<footprint>Synthetic:USB-A</footprint>"
                '<libsource lib="Connector" part="USB_A"/></comp>'
                '<comp ref="J2"><value>Synthetic USB-A port 2</value>'
                "<footprint>Synthetic:USB-A</footprint>"
                '<libsource lib="Connector" part="USB_A"/></comp>'
                '<comp ref="U1"><value>Synthetic dual-port USB hub</value>'
                "<footprint>Synthetic:QFN</footprint>"
                '<libsource lib="Synthetic" part="UsbHub"/></comp>'
                "</components><libparts>"
                '<libpart lib="Connector" part="USB_A"><pins>'
                '<pin num="1" name="D+" type="passive"/>'
                '<pin num="2" name="D-" type="passive"/>'
                '<pin num="3" name="GND" type="passive"/>'
                '<pin num="4" name="VBUS" type="passive"/>'
                "</pins></libpart>"
                '<libpart lib="Synthetic" part="UsbHub"><pins>'
                '<pin num="1" name="DP1" type="input"/>'
                '<pin num="2" name="DM1" type="input"/>'
                '<pin num="3" name="GND" type="power_in"/>'
                '<pin num="4" name="DP2" type="input"/>'
                '<pin num="5" name="DM2" type="input"/>'
                '<pin num="6" name="AGND" type="power_in"/>'
                '<pin num="7" name="VDD" type="power_in"/>'
                "</pins></libpart></libparts><nets>"
                '<net name="USB1_DP"><node ref="J1" pin="1"/>'
                '<node ref="U1" pin="1"/></net>'
                '<net name="USB1_DM"><node ref="J1" pin="2"/>'
                '<node ref="U1" pin="2"/></net>'
                '<net name="USB2_DP"><node ref="J2" pin="1"/>'
                '<node ref="U1" pin="4"/></net>'
                '<net name="USB2_DM"><node ref="J2" pin="2"/>'
                '<node ref="U1" pin="5"/></net>'
                f"{reference_nets}"
                '<net name="+5V"><node ref="J1" pin="4"/>'
                '<node ref="J2" pin="4"/></net>'
                '<net name="+3V3"><node ref="U1" pin="7"/></net>'
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

        def write_superspeed_netlist(*, split_reference: bool, full_duplex: bool = False) -> None:
            if split_reference:
                reference_nets = (
                    '<net name="USB_GND"><node ref="J1" pin="3"/></net>'
                    '<net name="PHY_GND"><node ref="U1" pin="3"/></net>'
                )
            else:
                reference_nets = (
                    '<net name="BOARD_GND"><node ref="J1" pin="3"/><node ref="U1" pin="3"/></net>'
                )
            netlist.write_text(
                "<export><components>"
                '<comp ref="J1"><value>Synthetic USB connector</value>'
                "<footprint>Synthetic:USB-A</footprint>"
                '<libsource lib="Connector" part="USB_A"/></comp>'
                '<comp ref="U1"><value>Synthetic USB PHY</value>'
                "<footprint>Synthetic:QFN</footprint>"
                '<libsource lib="Synthetic" part="UsbPhy"/></comp>'
                "</components><libparts>"
                '<libpart lib="Connector" part="USB_A"><pins>'
                '<pin num="1" name="StdA_SSTX+" type="passive"/>'
                '<pin num="2" name="StdA_SSTX-" type="passive"/>'
                '<pin num="3" name="GND" type="passive"/>'
                '<pin num="4" name="VBUS" type="passive"/>'
                '<pin num="5" name="StdA_SSRX+" type="passive"/>'
                '<pin num="6" name="StdA_SSRX-" type="passive"/>'
                "</pins></libpart>"
                '<libpart lib="Synthetic" part="UsbPhy"><pins>'
                '<pin num="1" name="SSRX+" type="bidirectional"/>'
                '<pin num="2" name="SSRX-" type="bidirectional"/>'
                '<pin num="3" name="AGND" type="power_in"/>'
                '<pin num="4" name="VDD" type="power_in"/>'
                '<pin num="5" name="SSTX+" type="bidirectional"/>'
                '<pin num="6" name="SSTX-" type="bidirectional"/>'
                "</pins></libpart></libparts><nets>"
                '<net name="SS_LANE_A"><node ref="J1" pin="1"/>'
                '<node ref="U1" pin="1"/></net>'
                '<net name="SS_LANE_B"><node ref="J1" pin="2"/>'
                '<node ref="U1" pin="2"/></net>'
                + (
                    '<net name="SS_LANE_C"><node ref="J1" pin="5"/>'
                    '<node ref="U1" pin="5"/></net>'
                    '<net name="SS_LANE_D"><node ref="J1" pin="6"/>'
                    '<node ref="U1" pin="6"/></net>'
                    if full_duplex
                    else ""
                )
                + f"{reference_nets}"
                '<net name="+5V"><node ref="J1" pin="4"/></net>'
                '<net name="+3V3"><node ref="U1" pin="4"/></net>'
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

        async with Client(create_server(self.root), mode="legacy") as client:

            async def compare(*, fault: bool) -> DesignLintReport:
                write_netlist(split_reference=fault)
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

            fault = await compare(fault=True)
            findings = [
                item for item in fault.findings if item.rule_id == "bus.usb_peer_reference_review"
            ]
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0].subject, "J1 / U1: USB reference-domain review")
            self.assertEqual(findings[0].evidence["connector_reference_net"], ("USB_GND",))
            self.assertEqual(findings[0].evidence["phy_reference_net"], ("BOARD_GND",))
            fault_coverage = fault.usb_peer_reference_coverage
            self.assertIsNotNone(fault_coverage)
            assert fault_coverage is not None
            self.assertEqual(fault_coverage.status, "EVALUATED")
            self.assertEqual(fault_coverage.separate_reference_path_count, 1)
            self.assertEqual(fault_coverage.candidate_group_count, 1)
            self.assertEqual(len(fault_coverage.path_entries), 1)
            self.assertEqual(
                fault_coverage.path_entries[0].reference_disposition,
                "SEPARATE_REFERENCE_REVIEW",
            )
            self.assertEqual(
                fault_coverage.path_entries[0].data_path.positive.connector_pins,
                ("J1.1",),
            )

            control = await compare(fault=False)
            self.assertNotIn(
                "bus.usb_peer_reference_review",
                {item.rule_id for item in control.findings},
            )
            control_coverage = control.usb_peer_reference_coverage
            self.assertIsNotNone(control_coverage)
            assert control_coverage is not None
            self.assertEqual(control_coverage.common_reference_path_count, 1)
            self.assertEqual(control_coverage.separate_reference_path_count, 0)
            self.assertEqual(control_coverage.candidate_group_count, 0)
            self.assertEqual(
                tuple(item.reference_disposition for item in control_coverage.path_entries),
                ("COMMON_REFERENCE",),
            )

            for split_references, expected_count in ((True, 2), (False, 0)):
                write_multiport_netlist(split_references=split_references)
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
                findings = tuple(
                    item for item in mcp.findings if item.rule_id == "bus.usb_peer_reference_review"
                )
                self.assertEqual(len(findings), expected_count)
                coverage = mcp.usb_peer_reference_coverage
                self.assertIsNotNone(coverage)
                assert coverage is not None
                self.assertEqual(coverage.supported_data_path_count, 2)
                self.assertEqual(coverage.candidate_group_count, expected_count)
                self.assertEqual(
                    coverage.separate_reference_path_count,
                    expected_count,
                )
                self.assertEqual(
                    coverage.common_reference_path_count,
                    2 - expected_count,
                )
                self.assertEqual(
                    tuple(
                        (
                            item.connector_reference,
                            item.phy_reference,
                            item.data_path.port_group,
                            item.reference_disposition,
                        )
                        for item in coverage.path_entries
                    ),
                    (
                        (
                            "J1",
                            "U1",
                            "1",
                            "SEPARATE_REFERENCE_REVIEW" if split_references else "COMMON_REFERENCE",
                        ),
                        (
                            "J2",
                            "U1",
                            "2",
                            "SEPARATE_REFERENCE_REVIEW" if split_references else "COMMON_REFERENCE",
                        ),
                    ),
                )
                if split_references:
                    self.assertEqual(
                        tuple(item.evidence["USB_port_group"] for item in findings),
                        (("1",), ("2",)),
                    )

            for split_reference in (True, False):
                write_superspeed_netlist(split_reference=split_reference)
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
                findings = tuple(
                    item for item in mcp.findings if item.rule_id == "bus.usb_peer_reference_review"
                )
                coverage = mcp.usb_peer_reference_coverage
                self.assertIsNotNone(coverage)
                assert coverage is not None
                if split_reference:
                    self.assertEqual(len(findings), 1)
                    self.assertEqual(
                        findings[0].subject,
                        "J1 / U1: USB SuperSpeed reference-domain review",
                    )
                    self.assertEqual(coverage.separate_reference_path_count, 1)
                    self.assertEqual(coverage.candidate_group_count, 1)
                    self.assertEqual(
                        coverage.path_entries[0].data_path.connector_signal_family,
                        "USB SuperSpeed TX",
                    )
                    self.assertEqual(
                        coverage.path_entries[0].data_path.phy_signal_family,
                        "USB SuperSpeed RX",
                    )
                else:
                    self.assertEqual(findings, ())
                    self.assertEqual(coverage.common_reference_path_count, 1)
                    self.assertEqual(coverage.candidate_group_count, 0)

            contract_path = self.island / "tests/contract.json"
            contract = read_model(contract_path, ProjectTestContract)
            policy = contract.design_lint or DesignLintPolicy()
            path_map = superspeed_reference_map(
                full_duplex=True,
                connector_reference_net="USB_GND",
                phy_reference_net="PHY_GND",
            )
            write_model(
                contract_path,
                contract.model_copy(
                    update={
                        "design_lint": policy.model_copy(update={"usb_data_path_map": path_map})
                    }
                ),
            )
            for split_reference in (True, False):
                write_superspeed_netlist(
                    split_reference=split_reference,
                    full_duplex=True,
                )
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
                observed_rule_ids = {item.rule_id for item in mcp.findings}
                if split_reference:
                    self.assertNotIn(RULE_ID, observed_rule_ids)
                    self.assertNotIn(PATH_RULE_ID, observed_rule_ids)
                    self.assertEqual(
                        mcp.usb_peer_reference_coverage.mapped_separate_reference_path_count,
                        2,
                    )
                else:
                    self.assertNotIn(RULE_ID, observed_rule_ids)
                    self.assertEqual(
                        sum(item.rule_id == PATH_RULE_ID for item in mcp.findings),
                        2,
                    )


def test_usb_peer_reference_lint_cli_mcp_parity() -> None:
    run_mcp_parity(
        _DesignLintMcpParityUsbReferenceCases,
        "_case_test_usb_peer_reference_lint_cli_mcp_parity",
    )
