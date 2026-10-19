"""CLI/MCP parity for project-mapped IC decoupling minimums."""

from __future__ import annotations

import pytest

pytestmark = [
    pytest.mark.parity_lint,
    pytest.mark.slow,
    pytest.mark.template_checkout,
    pytest.mark.design_lint,
    pytest.mark.power_lint,
]

import xml.etree.ElementTree as ET

from mcp import Client

from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    ComponentIdentity,
    ConnectorInterfaceReview,
    ConnectorInventoryReview,
    DesignLintPolicy,
    DesignLintReport,
    ProjectManifest,
    ProjectTestContract,
    ValidationSummary,
)
from tests.design_lint_fixtures.ic_decoupling import ic_decoupling_map
from tests.mcp_parity_support import McpParityHarness, run_mcp_parity

RULE_ID = "power.ic_decoupling_below_project_minimum"


class _DesignLintMcpParityIcDecouplingCases(McpParityHarness):
    async def _case_test_ic_decoupling_review_matches_between_cli_and_mcp(self) -> None:
        """Compare exact-minimum control and below-minimum fault across both adapters."""
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"

        def write_netlist(capacitor_value: str) -> None:
            root = ET.Element("export")
            components = ET.SubElement(root, "components")
            for reference, value, footprint, library, part in (
                ("U1", "Synthetic IC", "Synthetic:QFN", "Synthetic", "Logic"),
                ("C1", capacitor_value, "Synthetic:0603", "Device", "C"),
            ):
                component = ET.SubElement(components, "comp", ref=reference)
                ET.SubElement(component, "value").text = value
                ET.SubElement(component, "footprint").text = footprint
                ET.SubElement(component, "libsource", lib=library, part=part)

            libparts = ET.SubElement(root, "libparts")
            for library, part, pins in (
                ("Synthetic", "Logic", (("1", "VDD", "power_in"), ("2", "GND", "passive"))),
                ("Device", "C", (("1", "1", "passive"), ("2", "2", "passive"))),
            ):
                libpart = ET.SubElement(libparts, "libpart", lib=library, part=part)
                pin_container = ET.SubElement(libpart, "pins")
                for number, name, electrical_type in pins:
                    ET.SubElement(
                        pin_container,
                        "pin",
                        num=number,
                        name=name,
                        type=electrical_type,
                    )

            nets = ET.SubElement(root, "nets")
            for name, pins in (
                ("+3V3", (("U1", "1"), ("C1", "1"))),
                ("GND", (("U1", "2"), ("C1", "2"))),
            ):
                net = ET.SubElement(nets, "net", name=name)
                for reference, number in pins:
                    ET.SubElement(net, "node", ref=reference, pin=number)
            netlist.write_text(ET.tostring(root, encoding="unicode"), encoding="utf-8")
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
                    "connector_reviews": (
                        ConnectorInterfaceReview(
                            reference="J1",
                            disposition="not_applicable",
                            basis="Synthetic parity case checks only the mapped decoupling minimum",
                        ),
                    ),
                    "connector_inventory_review": ConnectorInventoryReview(
                        basis="Synthetic parity fixture has no connector inventory requirement"
                    ),
                }
            ),
        )
        contract_path = self.island / "tests/contract.json"
        contract = read_model(contract_path, ProjectTestContract)
        write_model(
            contract_path,
            contract.model_copy(
                update={"design_lint": DesignLintPolicy(ic_decoupling_map=ic_decoupling_map())}
            ),
        )

        async with Client(create_server(self.root), mode="legacy") as client:
            for value, is_fault in (("100nF", False), ("47nF", True)):
                with self.subTest(value=value):
                    write_netlist(value)
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
                    findings = [item for item in mcp.findings if item.rule_id == RULE_ID]
                    self.assertEqual(len(findings), int(is_fault))
                    self.assertEqual(mcp.status, "REVIEW")


def test_ic_decoupling_review_matches_between_cli_and_mcp() -> None:
    run_mcp_parity(
        _DesignLintMcpParityIcDecouplingCases,
        "_case_test_ic_decoupling_review_matches_between_cli_and_mcp",
    )
