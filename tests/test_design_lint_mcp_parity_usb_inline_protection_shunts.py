"""CLI/MCP parity for combined USB inline paths and protection shunts."""

from __future__ import annotations

import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from mcp import Client

from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    ComponentIdentity,
    ConnectorInventoryReview,
    DesignLintPolicy,
    DesignLintReport,
    ProjectManifest,
    ProjectTestContract,
)
from tests.mcp_parity_support import McpParityHarness, run_mcp_parity
from tests.usb_inline_protection_shunt_support import inline_protection_shunt_map
from tests.usb_protection_shunt_support import series_protection_shunt_map

pytestmark = [
    pytest.mark.parity_lint,
    pytest.mark.slow,
    pytest.mark.template_checkout,
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
]


class _UsbInlineProtectionShuntParityCases(McpParityHarness):
    async def _case_test_combined_inline_path_and_shunt_parity(self) -> None:
        """Compare a valid combined map and a wrong-side tap through CLI and MCP."""
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"
        fixture = (
            Path(__file__).parent
            / "fixtures/design_lint/usb-data-path-native/inline-protection-shunt-control.netlist.xml"
        )
        manifest_path = self.island / "project.json"
        manifest = read_model(manifest_path, ProjectManifest)
        write_model(
            manifest_path,
            manifest.model_copy(
                update={
                    "component_identity": ComponentIdentity(required=False, part_ids=()),
                    "interfaces": (),
                    "connector_reviews": (),
                    "connector_inventory_review": ConnectorInventoryReview(
                        basis="Synthetic parity fixture reviewed its USB connector inventory"
                    ),
                }
            ),
        )
        contract_path = self.island / "tests/contract.json"
        contract = read_model(contract_path, ProjectTestContract)
        write_model(
            contract_path,
            contract.model_copy(
                update={
                    "design_lint": DesignLintPolicy(usb_data_path_map=inline_protection_shunt_map())
                }
            ),
        )

        def write_netlist(*, wrong_dminus_side: bool) -> None:
            shutil.copyfile(fixture, netlist)
            if wrong_dminus_side:
                tree = ET.parse(netlist)
                nets = tree.getroot().find("./nets")
                assert nets is not None
                phy = next(
                    item for item in nets.findall("net") if item.get("name") == "/USB_DM_PHY"
                )
                shunt_pin = next(
                    item
                    for item in phy.findall("node")
                    if item.get("ref") == "U6" and item.get("pin") == "3"
                )
                phy.remove(shunt_pin)
                port = next(
                    item for item in nets.findall("net") if item.get("name") == "/USB_DM_PORT"
                )
                port.append(shunt_pin)
                tree.write(netlist, encoding="utf-8", xml_declaration=True)
            self.rehash_native_netlist(native)

        async with Client(create_server(self.root), mode="legacy") as client:

            async def compare(*, wrong_dminus_side: bool) -> DesignLintReport:
                write_netlist(wrong_dminus_side=wrong_dminus_side)
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

            control = await compare(wrong_dminus_side=False)
            self.assertFalse(
                any(item.rule_id == "bus.usb_data_path_mismatch" for item in control.findings),
                control.findings,
            )
            self.assertEqual(control.usb_peer_reference_coverage.supported_data_path_count, 1)
            fault = await compare(wrong_dminus_side=True)
            findings = tuple(
                item for item in fault.findings if item.rule_id == "bus.usb_data_path_mismatch"
            )
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0].evidence["line"], ("protection_shunt",))
            self.assertTrue(
                any(
                    "U6.3 is on USB_DM_PORT; expected USB_DM_PHY" in issue
                    for issue in findings[0].evidence["issues"]
                ),
                findings[0].evidence,
            )
            self.assertEqual(fault.usb_peer_reference_coverage.supported_data_path_count, 0)

    async def _case_test_series_path_shunt_cli_mcp_parity(self) -> None:
        """Compare series-resistor/shunt split, common, and wrong-side maps."""
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"
        fixture = (
            Path(__file__).parent
            / "fixtures/design_lint/usb-data-path-native/series-protection-shunt-control.netlist.xml"
        )
        manifest_path = self.island / "project.json"
        manifest = read_model(manifest_path, ProjectManifest)
        write_model(
            manifest_path,
            manifest.model_copy(
                update={
                    "component_identity": ComponentIdentity(required=False, part_ids=()),
                    "interfaces": (),
                    "connector_reviews": (),
                    "connector_inventory_review": ConnectorInventoryReview(
                        basis="Synthetic parity fixture reviewed its USB connector inventory"
                    ),
                }
            ),
        )
        contract_path = self.island / "tests/contract.json"
        contract = read_model(contract_path, ProjectTestContract)

        def write_netlist(*, common_reference: bool, wrong_dplus_side: bool = False) -> None:
            shutil.copyfile(fixture, netlist)
            tree = ET.parse(netlist)
            nets = tree.getroot().find("./nets")
            assert nets is not None
            for net in nets.findall("net"):
                original = (net.get("name") or "").lstrip("/")
                if original in {"USB_D+", "USB_D-"}:
                    net.set("name", "USB_DP" if original == "USB_D+" else "USB_DM")

            def find_net(name: str) -> ET.Element:
                return next(
                    item
                    for item in nets.findall("net")
                    if (item.get("name") or "").lstrip("/") == name
                )

            if common_reference:
                reference_nodes = []
                for name in ("USB_GND", "PHY_GND"):
                    reference = find_net(name)
                    reference_nodes.extend(reference.findall("node"))
                    nets.remove(reference)
                common = ET.SubElement(nets, "net", {"name": "GND"})
                common.extend(reference_nodes)
            if wrong_dplus_side:
                connector_side = find_net("USB_DP")
                tap = next(
                    item
                    for item in connector_side.findall("node")
                    if item.get("ref") == "U6" and item.get("pin") == "1"
                )
                connector_side.remove(tap)
                find_net("USB_DP_PHY").append(tap)
            tree.write(netlist, encoding="utf-8", xml_declaration=True)
            self.rehash_native_netlist(native)

        async with Client(create_server(self.root), mode="legacy") as client:

            async def compare(
                *, common_reference: bool, wrong_dplus_side: bool = False
            ) -> DesignLintReport:
                write_netlist(
                    common_reference=common_reference,
                    wrong_dplus_side=wrong_dplus_side,
                )
                contract_map = series_protection_shunt_map(
                    reference_net="GND" if common_reference else "USB_GND",
                    phy_symbol="Synthetic:TUSB2036",
                )
                write_model(
                    contract_path,
                    contract.model_copy(
                        update={"design_lint": DesignLintPolicy(usb_data_path_map=contract_map)}
                    ),
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
                return mcp

            split = await compare(common_reference=False)
            self.assertEqual(
                tuple(
                    item.rule_id
                    for item in split.findings
                    if item.rule_id
                    in {"bus.usb_peer_reference_review", "bus.usb_data_path_mismatch"}
                ),
                ("bus.usb_peer_reference_review",),
            )
            self.assertEqual(split.usb_peer_reference_coverage.supported_data_path_count, 1)
            review = next(
                item for item in split.findings if item.rule_id == "bus.usb_peer_reference_review"
            )
            self.assertEqual(
                review.evidence["USB_D+_series_resistor"],
                ("R1 (Device:R, 27R; R1.1=USB_DP, R1.2=USB_DP_PHY)",),
            )
            self.assertEqual(
                review.evidence["USB_mapped_protection_shunts"],
                ("U6 (Synthetic:UsbProtectionArray; Synthetic:DFN-6)",),
            )
            common = await compare(common_reference=True)
            self.assertFalse(
                any(
                    item.rule_id in {"bus.usb_peer_reference_review", "bus.usb_data_path_mismatch"}
                    for item in common.findings
                ),
                common.findings,
            )
            fault = await compare(common_reference=False, wrong_dplus_side=True)
            faults = tuple(
                item for item in fault.findings if item.rule_id == "bus.usb_data_path_mismatch"
            )
            self.assertEqual(len(faults), 1)
            self.assertTrue(
                any(
                    "U6.1 is on USB_DP_PHY; expected USB_DP" in issue
                    for issue in faults[0].evidence["issues"]
                ),
                faults[0].evidence,
            )
            self.assertFalse(
                any(item.rule_id == "bus.usb_peer_reference_review" for item in fault.findings)
            )
            self.assertEqual(fault.usb_peer_reference_coverage.supported_data_path_count, 0)


def test_combined_inline_path_and_shunt_parity() -> None:
    run_mcp_parity(
        _UsbInlineProtectionShuntParityCases,
        "_case_test_combined_inline_path_and_shunt_parity",
    )


def test_series_path_shunt_cli_mcp_parity() -> None:
    run_mcp_parity(
        _UsbInlineProtectionShuntParityCases,
        "_case_test_series_path_shunt_cli_mcp_parity",
    )
