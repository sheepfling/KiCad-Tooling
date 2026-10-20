"""Design-lint CLI/MCP parity for the combined review report."""

from __future__ import annotations

from xml.etree import ElementTree

import pytest

pytestmark = [
    pytest.mark.parity_lint,
    pytest.mark.interface_lint,
    pytest.mark.slow,
    pytest.mark.template_checkout,
    pytest.mark.design_lint,
]

from mcp import Client

from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import ValidationSummary
from tests.design_lint_mcp_parity_report_support import DesignLintMcpParityReportHarness
from tests.mcp_parity_support import run_mcp_parity


class _DesignLintMcpParityReportCases(DesignLintMcpParityReportHarness):
    async def _case_test_design_lint_parity(self) -> None:
        native, netlist = self.install_comprehensive_lint_report()
        async with Client(create_server(self.root), mode="legacy") as client:
            uncovered = await self.compare_lint_report(client, native, "REVIEW", 1)
            self.assertNotIn(
                "bus.i2c_multiple_pullup_rail_families",
                {item.rule_id for item in uncovered.findings},
            )
            self.assertIn(
                "signal.open_collector_input_without_visible_bias",
                {item.rule_id for item in uncovered.findings},
            )
            self.assertIn(
                "signal.open_emitter_input_without_visible_bias",
                {item.rule_id for item in uncovered.findings},
            )
            vendor_pair_finding = next(
                item
                for item in uncovered.findings
                if item.rule_id == "bus.complementary_pair_assignment"
                and item.subject == "U17: vendor data lane 0 pair"
            )
            self.assertEqual(vendor_pair_finding.evidence["positive_pins"], ("U17.1",))
            self.assertEqual(vendor_pair_finding.evidence["negative_pins"], ("U17.2",))
            self.assertEqual(vendor_pair_finding.evidence["negative_nets"], ())
            self.assertEqual(
                vendor_pair_finding.evidence["alias_symbol"],
                ("Synthetic:VendorDifferentialDevice",),
            )
            source_text = netlist.read_text(encoding="utf-8")
            control_text = source_text
            tree = ElementTree.fromstring(control_text)
            nets = tree.findall("./nets/net")
            five_volt_net = next(net for net in nets if net.get("name") == "+5V")
            three_volt_net = next(net for net in nets if net.get("name") == "+3V3")
            pullup = next(
                node
                for node in three_volt_net.findall("node")
                if node.get("ref") == "R2" and node.get("pin") == "2"
            )
            three_volt_net.remove(pullup)
            five_volt_net.append(pullup)
            source_text = ElementTree.tostring(tree, encoding="unicode")
            self.assertNotEqual(source_text, control_text)
            netlist.write_text(source_text, encoding="utf-8")
            current_summary = read_model(native, ValidationSummary)
            write_model(
                native,
                current_summary.model_copy(
                    update={
                        "artifacts_sha256": {
                            **current_summary.artifacts_sha256,
                            "netlist.xml": digest(netlist),
                        }
                    }
                ),
            )
            mixed_rails = await self.compare_lint_report(client, native, "REVIEW", 1)
            self.assertIn(
                "bus.i2c_multiple_pullup_rail_families",
                {item.rule_id for item in mixed_rails.findings},
            )
            netlist.write_text(control_text, encoding="utf-8")
            restored_summary = read_model(native, ValidationSummary)
            write_model(
                native,
                restored_summary.model_copy(
                    update={
                        "artifacts_sha256": {
                            **restored_summary.artifacts_sha256,
                            "netlist.xml": digest(netlist),
                        }
                    }
                ),
            )
            chain_tree = ElementTree.fromstring(control_text)
            components = chain_tree.find("./components")
            nets = chain_tree.find("./nets")
            assert components is not None and nets is not None
            for reference in ("R4", "R5"):
                component = ElementTree.SubElement(components, "comp", {"ref": reference})
                ElementTree.SubElement(component, "value").text = "10k"
                ElementTree.SubElement(component, "libsource", {"lib": "Device", "part": "R"})
            positive_rail = next(net for net in nets.findall("net") if net.get("name") == "+3V3")
            ElementTree.SubElement(positive_rail, "node", {"ref": "R5", "pin": "2"})
            ElementTree.SubElement(
                nets,
                "net",
                {"name": "MCP_RESET_N"},
            )
            for reference, pin in (("U3", "1"), ("R4", "1")):
                ElementTree.SubElement(nets[-1], "node", {"ref": reference, "pin": pin})
            ElementTree.SubElement(
                nets,
                "net",
                {"name": "MCP_RESET_BIAS_MID"},
            )
            for reference, pin in (("R4", "2"), ("R5", "1")):
                ElementTree.SubElement(nets[-1], "node", {"ref": reference, "pin": pin})
            netlist.write_text(
                ElementTree.tostring(chain_tree, encoding="unicode"), encoding="utf-8"
            )
            chained = read_model(native, ValidationSummary)
            write_model(
                native,
                chained.model_copy(
                    update={
                        "artifacts_sha256": {
                            **chained.artifacts_sha256,
                            "netlist.xml": digest(netlist),
                        }
                    }
                ),
            )
            chain_report = await self.compare_lint_report(client, native, "REVIEW", 1)
            self.assertNotIn(
                "control.connected_control_input_without_visible_bias",
                {item.rule_id for item in chain_report.findings},
            )
            assert uncovered.connector_coverage is not None
            self.assertEqual(uncovered.connector_coverage.status, "UNDECLARED")
            self.assertIn(
                "U7",
                {item.reference for item in uncovered.connector_coverage.entries},
            )
            self.assertNotIn(
                "U8",
                {item.reference for item in uncovered.connector_coverage.entries},
            )
            self.assertEqual(uncovered.schematic_geometry.status, "NOT_REQUESTED")
            self.assertTrue(
                any(
                    item.rule_id == "bus.spi_active_low_chip_select_without_pullup"
                    and item.subject == "SPI_CS_N: active-low SPI chip-select bias"
                    and item.mode == "review"
                    for item in uncovered.findings
                )
            )
            spi_participant = next(
                item
                for item in uncovered.findings
                if item.rule_id == "bus.spi_unmapped_participant"
            )
            self.assertEqual(spi_participant.subject, "U5: SPI roster coverage")
            self.assertEqual(spi_participant.evidence["SCK_pins"], ("U5.2",))
            self.assertEqual(spi_participant.evidence["input_data_pins"], ("U5.3",))
            self.assertEqual(spi_participant.evidence["chip_select_pins"], ("U5.1",))
            self.assertEqual(spi_participant.mode, "review")
            usb_c_port = next(
                item for item in uncovered.findings if item.rule_id == "bus.usb_c_unreviewed_port"
            )
            self.assertEqual(usb_c_port.subject, "J11: USB-C role-map coverage")
            self.assertEqual(usb_c_port.evidence["CC1_pins"], ("J11.4",))
            self.assertEqual(usb_c_port.evidence["CC2_pins"], ("J11.5",))
            self.assertIn("no configured project USB-C port role map", usb_c_port.message)
            self.assertEqual(usb_c_port.mode, "review")
            assert uncovered.rule_catalog is not None
            self.assertGreaterEqual(len(uncovered.rule_catalog.rules), 14)
            self.assertRegex(uncovered.rule_catalog.sha256, r"^[a-f0-9]{64}$")


def test_design_lint_parity() -> None:
    run_mcp_parity(_DesignLintMcpParityReportCases, "_case_test_design_lint_parity")
