"""Design-lint CLI/MCP parity cases: design lint mcp parity usb data."""

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
    ComponentIdentity,
    ConnectorInventoryReview,
    DesignLintPolicy,
    DesignLintReport,
    ProjectManifest,
    ProjectTestContract,
    ReferenceBondRequirement,
    UsbReferencePinRequirement,
    ValidationSummary,
)
from tests.mcp_parity_support import (
    McpParityHarness,
    run_mcp_parity,
)
from tests.usb_data_path_support import usb_data_map as synthetic_usb_data_path_map


class _DesignLintMcpParityUsbDataCases(McpParityHarness):
    async def _case_test_usb_data_path_map_parity(self) -> None:
        """Compare the same PHY-specific USB path fault through CLI and MCP."""
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"

        def write_netlist(
            *, missing_dp_resistor: bool, wrong_reference_bond_net: bool = False
        ) -> None:
            dp_resistor_component = (
                ""
                if missing_dp_resistor
                else '<comp ref="R1"><value>27R</value>'
                "<footprint>Synthetic:0603</footprint>"
                '<libsource lib="Device" part="R"/></comp>'
            )
            dp_connector_pin = (
                '<net name="USB_DP_PORT"><node ref="J1" pin="1"/></net>'
                if missing_dp_resistor
                else '<net name="USB_DP_PORT"><node ref="J1" pin="1"/>'
                '<node ref="R1" pin="1"/></net>'
            )
            dp_phy_pin = (
                '<net name="USB_DP_PHY"><node ref="U1" pin="1"/></net>'
                if missing_dp_resistor
                else '<net name="USB_DP_PHY"><node ref="R1" pin="2"/><node ref="U1" pin="1"/></net>'
            )
            board_reference_nodes = '<node ref="U1" pin="3"/>'
            if not wrong_reference_bond_net:
                board_reference_nodes += '<node ref="R3" pin="2"/>'
            floating_reference_net = (
                '<net name="FLOATING_GND"><node ref="R3" pin="2"/></net>'
                if wrong_reference_bond_net
                else ""
            )
            netlist.write_text(
                "<export><components>"
                '<comp ref="J1"><value>Synthetic USB connector</value>'
                "<footprint>Synthetic:USB-A</footprint>"
                '<libsource lib="Synthetic" part="UsbA"/></comp>'
                '<comp ref="U1"><value>TUSB2036</value>'
                "<footprint>Synthetic:QFN</footprint>"
                '<libsource lib="Synthetic" part="TUSB2036"/></comp>'
                f"{dp_resistor_component}"
                '<comp ref="R2"><value>27R</value>'
                "<footprint>Synthetic:0603</footprint>"
                '<libsource lib="Device" part="R"/></comp>'
                '<comp ref="R3"><value>0R</value>'
                "<footprint>Synthetic:0603</footprint>"
                '<libsource lib="Device" part="R"/></comp>'
                "</components><libparts>"
                '<libpart lib="Synthetic" part="UsbA"><pins>'
                '<pin num="1" name="D+" type="passive"/>'
                '<pin num="2" name="D-" type="passive"/>'
                '<pin num="3" name="GND" type="passive"/>'
                "</pins></libpart>"
                '<libpart lib="Synthetic" part="TUSB2036"><pins>'
                '<pin num="1" name="DP1" type="input"/>'
                '<pin num="2" name="DM1" type="input"/>'
                '<pin num="3" name="AGND" type="power_in"/>'
                "</pins></libpart>"
                '<libpart lib="Device" part="R"><pins>'
                '<pin num="1" name="1" type="passive"/>'
                '<pin num="2" name="2" type="passive"/>'
                "</pins></libpart></libparts><nets>"
                f"{dp_connector_pin}{dp_phy_pin}"
                '<net name="USB_DM_PORT"><node ref="J1" pin="2"/>'
                '<node ref="R2" pin="1"/></net>'
                '<net name="USB_DM_PHY"><node ref="R2" pin="2"/>'
                '<node ref="U1" pin="2"/></net>'
                '<net name="USB_GND"><node ref="J1" pin="3"/>'
                '<node ref="R3" pin="1"/></net>'
                f'<net name="BOARD_GND">{board_reference_nodes}</net>'
                f"{floating_reference_net}"
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
        base_usb_path_map = synthetic_usb_data_path_map()
        interface = base_usb_path_map.interfaces[0].model_copy(
            update={
                "connector_reference_pins": (
                    UsbReferencePinRequirement(pin="J1.3", net="USB_GND"),
                ),
                "phy_reference_pins": (UsbReferencePinRequirement(pin="U1.3", net="BOARD_GND"),),
                "reference_policy": "bonded",
                "reference_bond": ReferenceBondRequirement(
                    reference="R3",
                    expected_symbol="Device:R",
                    expected_footprint="Synthetic:0603",
                    expected_value="0R",
                    side_a_pin="R3.1",
                    side_b_pin="R3.2",
                    side_a_net="USB_GND",
                    side_b_net="BOARD_GND",
                ),
            }
        )
        usb_path_map = base_usb_path_map.model_copy(update={"interfaces": (interface,)})
        write_model(
            contract_path,
            contract.model_copy(
                update={"design_lint": DesignLintPolicy(usb_data_path_map=usb_path_map)}
            ),
        )

        async with Client(create_server(self.root), mode="legacy") as client:

            async def compare(
                *, missing_dp_resistor: bool = False, wrong_reference_bond_net: bool = False
            ) -> DesignLintReport:
                write_netlist(
                    missing_dp_resistor=missing_dp_resistor,
                    wrong_reference_bond_net=wrong_reference_bond_net,
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
                self.assertEqual(mcp.status, "REVIEW")
                return mcp

            control = await compare()
            self.assertFalse(
                any(item.rule_id == "bus.usb_data_path_mismatch" for item in control.findings)
            )
            fault = await compare(missing_dp_resistor=True)
            self.assertEqual(
                [
                    item.subject
                    for item in fault.findings
                    if item.rule_id == "bus.usb_data_path_mismatch"
                ],
                ["usb-port-1: USB D+ path"],
            )
            bond_fault = await compare(wrong_reference_bond_net=True)
            bond_finding = next(
                item for item in bond_fault.findings if item.rule_id == "bus.usb_data_path_mismatch"
            )
            self.assertEqual(bond_finding.subject, "usb-port-1: USB reference path")
            self.assertTrue(
                any(
                    "R3.2 is on FLOATING_GND" in issue for issue in bond_finding.evidence["issues"]
                ),
                bond_finding.evidence["issues"],
            )


def test_usb_data_path_map_parity() -> None:
    run_mcp_parity(_DesignLintMcpParityUsbDataCases, "_case_test_usb_data_path_map_parity")
