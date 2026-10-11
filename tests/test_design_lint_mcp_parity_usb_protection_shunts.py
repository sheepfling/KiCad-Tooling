"""CLI/MCP parity for exact-mapped multi-pin USB protection shunts."""

from __future__ import annotations

import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.parity_lint,
    pytest.mark.slow,
    pytest.mark.template_checkout,
]

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
from tests.mcp_parity_support import McpParityHarness, parse_model_text, run_mcp_parity
from tests.usb_protection_shunt_support import protection_shunt_map


class _UsbProtectionShuntParity(McpParityHarness):
    async def _case_test_usb_protection_shunt_review_parity(self) -> None:
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"
        fixture = (
            Path(__file__).parent
            / "fixtures/design_lint/usb-data-path-native/inline-protection-control.netlist.xml"
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
        path_map = protection_shunt_map()
        write_model(
            contract_path,
            contract.model_copy(
                update={"design_lint": DesignLintPolicy(usb_data_path_map=path_map)}
            ),
        )

        def write_netlist(*, common_reference: bool, wrong_shunt_pin: bool = False) -> None:
            shutil.copyfile(fixture, netlist)
            tree = ET.parse(netlist)
            root = tree.getroot()
            for component in root.findall("./components/comp"):
                if component.get("ref") != "U2":
                    continue
                component.set("ref", "U6")
                component.find("value").text = "Synthetic protection array"
                component.find("footprint").text = "Synthetic:DFN-6"
                component.find("libsource").set("part", "UsbProtectionArray")
            for part in root.findall("./libparts/libpart"):
                if part.get("part") == "UsbProtection":
                    part.set("part", "UsbProtectionArray")

            nets = root.find("./nets")
            assert nets is not None
            for net in tuple(nets.findall("net")):
                nets.remove(net)

            def add_net(name: str, pins: tuple[tuple[str, str], ...]) -> None:
                net = ET.SubElement(nets, "net", {"name": name})
                for reference, pin in pins:
                    ET.SubElement(net, "node", {"ref": reference, "pin": pin})

            positive_pins = [("J1", "1"), ("U1", "1"), ("U6", "1")]
            ground_pins = [("U1", "3"), ("U6", "4"), ("U6", "5")]
            if wrong_shunt_pin:
                positive_pins.append(("U6", "2"))
            else:
                ground_pins.append(("U6", "2"))
            if common_reference:
                ground_pins.append(("J1", "4"))
            add_net("USB_DP", tuple(positive_pins))
            add_net("USB_DM", (("J1", "2"), ("U1", "2"), ("U6", "3")))
            add_net("BOARD_GND", tuple(ground_pins))
            if not common_reference:
                add_net("USB_GND", (("J1", "4"),))
            add_net("unconnected-(U6-Pad6)", (("U6", "6"),))
            tree.write(netlist, encoding="utf-8", xml_declaration=True)
            self.rehash_native_netlist(native)

        async with Client(create_server(self.root), mode="legacy") as client:

            async def compare(
                *, common_reference: bool, wrong_shunt_pin: bool = False
            ) -> DesignLintReport:
                write_netlist(
                    common_reference=common_reference,
                    wrong_shunt_pin=wrong_shunt_pin,
                )
                process = await self.cli_process(
                    "kicad_tooling.design_lint",
                    "--project",
                    "controller",
                    "--native-summary",
                    str(native),
                )
                self.assertIn(process.returncode, (0, 1), process.stderr + process.stdout)
                cli = parse_model_text(process.stdout, DesignLintReport)
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
                {
                    item.rule_id
                    for item in split.findings
                    if item.rule_id
                    in {"bus.usb_peer_reference_review", "bus.usb_data_path_mismatch"}
                },
                {"bus.usb_peer_reference_review"},
            )
            common = await compare(common_reference=True)
            self.assertFalse(
                any(
                    item.rule_id in {"bus.usb_peer_reference_review", "bus.usb_data_path_mismatch"}
                    for item in common.findings
                ),
                common.findings,
            )
            fault = await compare(common_reference=False, wrong_shunt_pin=True)
            path_faults = tuple(
                item for item in fault.findings if item.rule_id == "bus.usb_data_path_mismatch"
            )
            self.assertEqual(len(path_faults), 1, fault.findings)
            self.assertFalse(
                any(item.rule_id == "bus.usb_peer_reference_review" for item in fault.findings)
            )
            self.assertTrue(
                any(
                    "U6.2 is on USB_DP" in issue
                    for item in path_faults
                    for issue in item.evidence["issues"]
                )
            )


def test_usb_protection_shunt_review_cli_mcp_parity() -> None:
    run_mcp_parity(
        _UsbProtectionShuntParity,
        "_case_test_usb_protection_shunt_review_parity",
    )
