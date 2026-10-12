"""Design-lint connector-coverage CLI/MCP review and ignore lifecycle."""

from __future__ import annotations

from xml.etree import ElementTree

import pytest

pytestmark = [
    pytest.mark.parity_lint,
    pytest.mark.slow,
    pytest.mark.template_checkout,
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
]

from mcp import Client

from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    ConnectorInterfaceReview,
    ConnectorInventoryReview,
    DesignLintIgnore,
    DesignLintPolicy,
    ProjectManifest,
    ProjectTestContract,
)
from tests.design_lint_mcp_parity_report_support import DesignLintMcpParityReportHarness
from tests.mcp_parity_support import run_mcp_parity


class _DesignLintMcpParityConnectorCoverageCases(DesignLintMcpParityReportHarness):
    async def _case_test_connector_coverage_and_review_lifecycle(self) -> None:
        native, netlist = self.install_comprehensive_lint_report()
        async with Client(create_server(self.root), mode="legacy") as client:
            manifest_path = self.island / "project.json"
            manifest = read_model(manifest_path, ProjectManifest)
            write_model(
                manifest_path,
                manifest.model_copy(
                    update={
                        "connector_reviews": tuple(
                            ConnectorInterfaceReview(
                                reference=reference,
                                disposition="not_applicable",
                                basis="Synthetic fixture isolates heuristic behavior from pinout coverage",
                            )
                            for reference in (
                                "J1",
                                "J2",
                                "J3",
                                "J4",
                                "J5",
                                "J6",
                                "J7",
                                "J8",
                                "J9",
                                "J10",
                                "J11",
                                "J12",
                                "U7",
                            )
                        ),
                        "connector_inventory_review": ConnectorInventoryReview(
                            basis="Synthetic review covered all connector candidates in the schematic"
                        ),
                    }
                ),
            )
            open_report = await self.compare_lint_report(client, native, "REVIEW", 1)
            assert open_report.connector_coverage is not None
            self.assertEqual(open_report.connector_coverage.status, "COMPLETE")
            self.assertEqual(
                open_report.connector_coverage.inventory_review_basis,
                "Synthetic review covered all connector candidates in the schematic",
            )
            self.assertEqual(open_report.native_status, "FAIL")
            self.assertEqual(len(open_report.findings), 26)
            led_bridge = next(
                item
                for item in open_report.findings
                if item.rule_id == "component.led_directly_across_supply_and_return"
            )
            self.assertEqual(led_bridge.evidence["positive_net"], ("+3V3",))
            self.assertEqual(led_bridge.evidence["return_net"], ("GND",))
            peer_pin_finding = next(
                item
                for item in open_report.findings
                if item.rule_id == "connector.peer_pin_assignment_outlier"
            )
            self.assertEqual(peer_pin_finding.subject, "Synthetic:Port pin 8")

            self.assertEqual(peer_pin_finding.evidence["J1.8"], ("PERIPHERAL_SIGNAL",))
            self.assertEqual(peer_pin_finding.evidence["J3.8"], ())
            self.assertEqual(peer_pin_finding.evidence["outlier_pins"], ("J3.8",))
            generic_peer_finding = next(
                item
                for item in open_report.findings
                if item.rule_id == "connector.peer_pin_assignment_divergence"
            )
            self.assertEqual(generic_peer_finding.subject, "Synthetic:GenericPeerPort pin 2")
            self.assertEqual(generic_peer_finding.evidence["J9.2"], ("PEER_A",))
            self.assertEqual(generic_peer_finding.evidence["J10.2"], ("PEER_B",))
            unmapped_i2c = next(
                item
                for item in open_report.findings
                if item.rule_id == "bus.i2c_unmapped_responder"
            )
            self.assertEqual(unmapped_i2c.subject, "U1: I2C address-map coverage")
            unroled_returns = next(
                item
                for item in open_report.findings
                if item.rule_id == "net.return_labels_without_pin_roles"
            )
            self.assertEqual(
                unroled_returns.evidence,
                {
                    "GND": ("C1.2", "D1.2"),
                    "SERIAL_RETURN": ("J6.9",),
                    "USB_GND": ("J4.2",),
                },
            )
            control_finding = next(
                item
                for item in open_report.findings
                if item.rule_id == "control.unconnected_control_input"
            )
            self.assertEqual(control_finding.subject, "U3.1: ~{RESET}")
            self.assertEqual(control_finding.evidence["electrical_type"], ("input",))
            control_subjects = {
                item.subject
                for item in open_report.findings
                if item.rule_id == "control.unconnected_control_input"
            }
            self.assertIn("U3.2: POR_B", control_subjects)
            self.assertNotIn("U3.3: PORN", control_subjects)
            component_supply_finding = next(
                item
                for item in open_report.findings
                if item.rule_id == "component.repeated_supply_pin_function"
            )
            self.assertEqual(
                component_supply_finding.subject,
                "U2 (Synthetic:MultiSupplyLogic): VDD supply pins",
            )
            self.assertEqual(
                component_supply_finding.evidence,
                {"U2.1": ("+3V3",), "U2.2": ("+1V8",)},
            )
            decoupling_finding = next(
                item
                for item in open_report.findings
                if item.rule_id == "power.ic_rail_without_fitted_capacitor"
            )
            self.assertEqual(decoupling_finding.subject, "+1V8: IC supply decoupling review")
            self.assertEqual(decoupling_finding.evidence["power_input_pins"], ("U2.2",))
            differential_finding = next(
                item
                for item in open_report.findings
                if item.rule_id == "bus.complementary_pair_assignment"
            )
            self.assertEqual(differential_finding.subject, "J5: USB data pair")
            self.assertEqual(differential_finding.evidence["positive_pins"], ("J5.1",))
            self.assertEqual(differential_finding.evidence["negative_pins"], ("J5.2",))
            superspeed_finding = next(
                item
                for item in open_report.findings
                if item.rule_id == "bus.complementary_pair_assignment"
                and item.subject == "U16: USB SuperSpeed TX pair"
            )
            self.assertEqual(superspeed_finding.evidence["positive_pins"], ("U16.1",))
            self.assertEqual(superspeed_finding.evidence["negative_pins"], ("U16.2",))
            self.assertEqual(superspeed_finding.evidence["negative_nets"], ())
            named_pair_finding = next(
                item
                for item in open_report.findings
                if item.rule_id == "signal.named_pair_without_reviewed_requirement"
            )
            self.assertEqual(named_pair_finding.subject, "USB_A_DP / USB_A_DM")
            unconnected_supply = next(
                item
                for item in open_report.findings
                if item.rule_id == "connector.unconnected_supply_pin"
            )
            self.assertEqual(unconnected_supply.subject, "J4.1: +3V3")
            self.assertEqual(unconnected_supply.evidence, {"J4.1": ()})
            generic_power_input = next(
                item
                for item in open_report.findings
                if item.rule_id == "connector.unconnected_power_input"
            )
            self.assertEqual(
                generic_power_input.subject,
                "J12.1: generic native power-input pin is unassigned",
            )
            self.assertEqual(
                generic_power_input.evidence,
                {
                    "symbol": ("Synthetic:GenericPowerInputPort",),
                    "pin_electrical_type": ("power_in",),
                    "J12.1": (),
                    "native_pin_function": ("1",),
                },
            )
            i2c_finding = next(
                item
                for item in open_report.findings
                if item.rule_id == "bus.i2c_low_equivalent_resistance"
            )
            self.assertEqual(i2c_finding.evidence["equivalent_ohms"], ("SDA=500Ω",))
            self.assertEqual(
                i2c_finding.evidence["pullup_resistors"],
                ("R1=1000Ω to +3V3", "R2=1000Ω to +3V3"),
            )
            power_finding = next(
                item
                for item in open_report.findings
                if item.subject == "multiple connector symbols: PWR"
            )
            self.assertEqual(
                power_finding.evidence,
                {
                    "J1.1": ("+5V",),
                    "J2.1": (),
                    "J3.1": (),
                },
            )
            numbered_power_finding = next(
                item for item in open_report.findings if item.rule_id == "net.numbered_power_rails"
            )
            self.assertEqual(numbered_power_finding.subject, "CH VDD")
            self.assertEqual(
                numbered_power_finding.evidence,
                {"CH2_VDD": ("J7.1",), "CH3_VDD": ("J8.1",)},
            )
            return_finding = next(
                item
                for item in open_report.findings
                if item.subject == "multiple connector symbols: ground/return"
            )
            self.assertEqual(
                return_finding.evidence,
                {
                    "J1.7": ("GND1",),
                    "J2.7": ("GND2",),
                    "J3.7": ("GND1",),
                },
            )

            dnp_tree = ElementTree.fromstring(netlist.read_text(encoding="utf-8"))
            j3 = next(
                component
                for component in dnp_tree.findall("./components/comp")
                if component.get("ref") == "J3"
            )
            ElementTree.SubElement(j3, "property", {"name": "dnp", "value": "yes"})
            dnp_xml = ElementTree.tostring(dnp_tree, encoding="unicode")
            self.assertNotEqual(dnp_xml, netlist.read_text(encoding="utf-8"))
            netlist.write_text(dnp_xml, encoding="utf-8")
            self.rehash_native_netlist(native)
            open_report = await self.compare_lint_report(client, native, "REVIEW", 1)
            repeated = [
                item
                for item in open_report.findings
                if item.rule_id == "connector.repeated_pin_function"
            ]
            self.assertTrue(repeated)
            self.assertTrue(
                all(not pin.startswith("J3.") for item in repeated for pin in item.evidence)
            )
            self.assertFalse(
                any(
                    item.rule_id
                    in {"connector.unconnected_supply_pin", "connector.unconnected_return_pin"}
                    and any(pin.startswith("J3.") for pin in item.evidence)
                    for item in open_report.findings
                )
            )
            self.assertFalse(
                any(
                    item.rule_id == "connector.peer_pin_assignment_outlier"
                    and "J3.8" in item.evidence.get("outlier_pins", ())
                    for item in open_report.findings
                )
            )

            contract_path = self.island / "tests/contract.json"
            contract = read_model(contract_path, ProjectTestContract)
            write_model(
                contract_path,
                contract.model_copy(
                    update={
                        "design_lint": DesignLintPolicy(
                            rules=(
                                contract.design_lint.rules
                                if contract.design_lint is not None
                                else ()
                            ),
                            complementary_pin_function_alias_map=(
                                contract.design_lint.complementary_pin_function_alias_map
                                if contract.design_lint is not None
                                else None
                            ),
                            ignores=tuple(
                                DesignLintIgnore(
                                    rule_id=item.rule_id,
                                    fingerprint=item.fingerprint,
                                    reason="Synthetic pinout review accepts this exact observation",
                                )
                                for item in open_report.findings
                            ),
                        )
                    }
                ),
            )
            accepted = await self.compare_lint_report(client, native, "PASS", 0)
            self.assertEqual(accepted.netlist_sha256, open_report.netlist_sha256)
            self.assertNotEqual(accepted.policy_sha256, open_report.policy_sha256)
            self.assertTrue(
                any(
                    item.rule_id == "component.generic_peer_pin_assignment_outlier"
                    and item.disposition == "RULE_OFF"
                    for item in accepted.findings
                )
            )
            self.assertTrue(
                all(item.disposition in {"IGNORED", "RULE_OFF"} for item in accepted.findings),
                [
                    (item.rule_id, item.subject, item.disposition)
                    for item in accepted.findings
                    if item.disposition not in {"IGNORED", "RULE_OFF"}
                ],
            )


def test_design_lint_connector_coverage_and_review_lifecycle() -> None:
    run_mcp_parity(
        _DesignLintMcpParityConnectorCoverageCases,
        "_case_test_connector_coverage_and_review_lifecycle",
    )
