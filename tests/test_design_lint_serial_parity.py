"""Cross-surface parity checks for the selected interface lint theme."""

from __future__ import annotations

import pytest
from mcp import Client

from kicad_tooling.hwrepo.contracts import write_model
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import CommandEvidence, ComponentContract, ValidationSummary
from tests.design_lint_fixtures.i2c_serial_parity import (
    alternate_function_serial_netlist,
    dual_uart_reference_netlist,
    dual_uart_separate_reference_map,
    electrical_contract,
    labelled_generic_uart_reference_netlist,
)
from tests.design_lint_fixtures.parity_harness import I2cSerialParityHarness

pytestmark = [pytest.mark.design_lint, pytest.mark.interface_lint, pytest.mark.parity_lint]


class DesignLintSerialParityTests(I2cSerialParityHarness):
    async def test_alternate_function_uart_labels_match_cli_and_mcp(self) -> None:
        self._write_native_evidence(
            missing_array=False,
            netlist_xml=alternate_function_serial_netlist(),
        )
        async with Client(create_server(self.root), mode="legacy") as client:
            report = await self._inspect_both_surfaces(client)
            findings = [
                item
                for item in report.findings
                if item.rule_id == "bus.serial_unmapped_peer" and item.subject.startswith("U1:")
            ]
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0].mode, "review")
            self.assertEqual(findings[0].evidence["discovery_basis"], ("net_label",))
            self.assertEqual(findings[0].evidence["TX_pins"], ("U1.1",))
            self.assertEqual(findings[0].evidence["RX_pins"], ("U1.2",))
            self.assertIn(
                "does not assert that a peer or connection is required", findings[0].message
            )
            await self._check_surface_registration()

    async def test_dual_uart_split_reference_localizes_one_header_on_cli_and_mcp(self) -> None:
        self._write_native_evidence(missing_array=False)
        write_model(
            self.island / "tests" / "electrical.json",
            electrical_contract().model_copy(update={"serial_peers": None}),
        )
        base_contract = self._project_contract()

        split_expected_nets: dict[str, tuple[str, ...]] | None = None
        async with Client(create_server(self.root), mode="legacy") as client:
            for split_first_return in (True, False):
                case = "split-return-fault" if split_first_return else "common-return-control"
                with self.subTest(case=case):
                    self.netlist_path.write_text(
                        dual_uart_reference_netlist(split_first_return=split_first_return),
                        encoding="utf-8",
                    )
                    expected_nets = {
                        "I2C_SDA": ("RN1.1", "U1.1"),
                        "I2C_SCL": ("RN1.3", "U1.2"),
                        "+3V3": ("J1.3", "J2.3", "RN1.2", "RN1.4", "U1.3"),
                        "UART1_TX": ("J1.2", "U1.5"),
                        "UART1_RX": ("J1.1", "U1.6"),
                        "UART2_TX": ("J2.2", "U1.7"),
                        "UART2_RX": ("J2.1", "U1.8"),
                        "GND_A": (
                            ("J1.4", "J2.4", "U1.4") if not split_first_return else ("J2.4", "U1.4")
                        ),
                        "SERIAL_B_TX": ("J3.1",),
                        "SERIAL_B_RX": ("J3.2",),
                    }
                    if split_first_return:
                        expected_nets["GND_B"] = ("J1.4",)
                    write_model(
                        self.island / "tests" / "contract.json",
                        base_contract.model_copy(
                            update={
                                "validation": base_contract.validation.model_copy(
                                    update={"nets": expected_nets}
                                )
                            }
                        ),
                    )
                    command = CommandEvidence(
                        argv=("synthetic-netlist-fixture", "dual-uart", case),
                        started_utc="2026-09-30T00:00:00+00:00",
                        returncode=0,
                    )
                    command_path = self.native / "netlist.command.json"
                    write_model(command_path, command)
                    summary = ValidationSummary.model_validate_json(
                        self.summary_path.read_text(encoding="utf-8")
                    )
                    write_model(
                        self.summary_path,
                        summary.model_copy(
                            update={
                                "artifacts_sha256": {
                                    **summary.artifacts_sha256,
                                    "netlist.xml": digest(self.netlist_path),
                                    "netlist.command.json": digest(command_path),
                                }
                            }
                        ),
                    )

                    report = await self._inspect_both_surfaces(client)
                    self.assertEqual(report.status, "REVIEW")
                    coverage = report.serial_peer_reference_coverage
                    self.assertIsNotNone(coverage)
                    assert coverage is not None
                    self.assertEqual(
                        (
                            coverage.status,
                            coverage.native_peer_link_count,
                            coverage.supported_reference_link_count,
                            coverage.incomplete_reference_link_count,
                            coverage.common_reference_link_count,
                            coverage.separate_reference_link_count,
                            coverage.mapped_separate_reference_link_count,
                            coverage.candidate_group_count,
                        ),
                        (
                            "EVALUATED",
                            4,
                            4,
                            0,
                            2 if split_first_return else 4,
                            2 if split_first_return else 0,
                            0,
                            1 if split_first_return else 0,
                        ),
                    )
                    findings = tuple(
                        item
                        for item in report.findings
                        if item.rule_id == "bus.serial_peer_reference_review"
                    )
                    if split_first_return:
                        split_expected_nets = expected_nets
                        self.assertEqual(len(findings), 1)
                        finding = findings[0]
                        self.assertEqual(
                            finding.subject,
                            "J1 / U1: serial reference-domain review",
                        )
                        self.assertEqual(finding.evidence["first_reference_net"], ("GND_B",))
                        self.assertEqual(finding.evidence["second_reference_net"], ("GND_A",))
                        self.assertEqual(
                            finding.evidence["shared_serial_pin_assignments"],
                            (
                                "UART1_RX: J1.1 (TX, output) -> U1.6 (UART1_RX, input)",
                                "UART1_TX: U1.5 (UART1_TX, output) -> J1.2 (RX, input)",
                            ),
                        )
                        self.assertNotIn("J2", finding.subject)
                    else:
                        self.assertEqual(findings, ())

            self.assertIsNotNone(split_expected_nets)
            assert split_expected_nets is not None
            self.netlist_path.write_text(
                dual_uart_reference_netlist(split_first_return=True),
                encoding="utf-8",
            )
            command = CommandEvidence(
                argv=("synthetic-netlist-fixture", "dual-uart", "reviewed-separate-references"),
                started_utc="2026-09-30T00:00:00+00:00",
                returncode=0,
            )
            command_path = self.native / "netlist.command.json"
            write_model(command_path, command)
            summary = ValidationSummary.model_validate_json(
                self.summary_path.read_text(encoding="utf-8")
            )
            write_model(
                self.summary_path,
                summary.model_copy(
                    update={
                        "artifacts_sha256": {
                            **summary.artifacts_sha256,
                            "netlist.xml": digest(self.netlist_path),
                            "netlist.command.json": digest(command_path),
                        }
                    }
                ),
            )
            project_contract = self._project_contract()
            expected_components = dict(project_contract.validation.components)
            expected_components["U1"] = expected_components["U1"].model_copy(
                update={"footprint": "Synthetic:Controller"}
            )
            write_model(
                self.island / "tests" / "contract.json",
                project_contract.model_copy(
                    update={
                        "validation": project_contract.validation.model_copy(
                            update={
                                "components": expected_components,
                                "nets": split_expected_nets,
                            }
                        )
                    }
                ),
            )
            write_model(
                self.island / "tests" / "electrical.json",
                electrical_contract().model_copy(
                    update={"serial_peers": dual_uart_separate_reference_map()}
                ),
            )

            intentional_split = await self._inspect_both_surfaces(client)
            self.assertEqual(intentional_split.status, "REVIEW")
            mapped_coverage = intentional_split.serial_peer_reference_coverage
            self.assertIsNotNone(mapped_coverage)
            assert mapped_coverage is not None
            self.assertEqual(
                (
                    mapped_coverage.authored_map_state,
                    mapped_coverage.separate_reference_link_count,
                    mapped_coverage.mapped_separate_reference_link_count,
                    mapped_coverage.candidate_group_count,
                ),
                ("required", 2, 2, 0),
            )
            self.assertNotIn(
                "bus.serial_peer_reference_review",
                {item.rule_id for item in intentional_split.findings},
            )
            await self._check_surface_registration()

    async def test_channel_labelled_generic_uart_reference_review_matches_cli_and_mcp(self) -> None:
        expected_components = {
            "U1": ComponentContract(value="Synthetic translator", footprint="Package:UART-TX"),
            "U2": ComponentContract(value="Synthetic serial bridge", footprint="Package:UART-RX"),
        }
        for split_reference in (True, False):
            case = "split-reference-fault" if split_reference else "common-reference-control"
            with self.subTest(case=case):
                self._write_native_evidence(
                    missing_array=False,
                    netlist_xml=labelled_generic_uart_reference_netlist(
                        split_reference=split_reference
                    ),
                )
                expected_nets = {
                    "Compute module/UART.0.TX": ("U1.1", "U2.2"),
                    "Compute module/UART.0.RX": ("U1.2", "U2.1"),
                    "+3V3": ("U1.8", "U2.8"),
                    "GND_A": ("U1.9", "U2.9") if not split_reference else ("U1.9",),
                }
                if split_reference:
                    expected_nets["GND_B"] = ("U2.9",)
                base_contract = self._project_contract()
                write_model(
                    self.island / "tests" / "contract.json",
                    base_contract.model_copy(
                        update={
                            "validation": base_contract.validation.model_copy(
                                update={
                                    "components": expected_components,
                                    "nets": expected_nets,
                                }
                            )
                        }
                    ),
                )
                write_model(
                    self.island / "tests" / "electrical.json",
                    electrical_contract().model_copy(update={"serial_peers": None}),
                )

                async with Client(create_server(self.root), mode="legacy") as client:
                    lint_report = await self._inspect_both_surfaces(client)
                    self.assertEqual(lint_report.status, "REVIEW")
                    findings = tuple(
                        item
                        for item in lint_report.findings
                        if item.rule_id == "bus.serial_peer_reference_review"
                    )
                    if split_reference:
                        self.assertEqual(len(findings), 1)
                        self.assertIn(
                            "Exact UART/USART TX and RX channel labels", findings[0].message
                        )
                        self.assertEqual(
                            findings[0].evidence["serial_label_link_assignments"],
                            (
                                "uart0: TX Compute module/UART.0.TX (U1.1, U2.2); "
                                + "RX Compute module/UART.0.RX (U1.2, U2.1)",
                            ),
                        )
                    else:
                        self.assertEqual(findings, ())
        await self._check_surface_registration()

    async def test_bonded_uart_reference_map_suppresses_only_valid_bond_on_cli_and_mcp(
        self,
    ) -> None:
        from kicad_tooling.hwrepo.models import ReferenceBondRequirement
        from tests.serial_peer_reference_support import (
            bonded_serial_reference_netlist,
            serial_peer_map,
        )
        from tests.test_electrical_parity import contract_netlist_xml

        requirement = serial_peer_map(
            reference_policy="bonded",
            output_reference_net="GND_A",
            input_reference_net="GND_B",
            reference_bond=ReferenceBondRequirement(
                reference="R3",
                expected_symbol="Device:R",
                expected_footprint="Synthetic:0603",
                expected_value="0R",
                side_a_pin="R3.1",
                side_b_pin="R3.2",
                side_a_net="GND_A",
                side_b_net="GND_B",
            ),
        )

        async with Client(create_server(self.root), mode="legacy") as client:
            for fault in (False, True):
                case = "broken-bond" if fault else "bond-control"
                with self.subTest(case=case):
                    observed = bonded_serial_reference_netlist(fault=fault)
                    self._write_native_evidence(
                        missing_array=False,
                        netlist_xml=contract_netlist_xml(observed),
                    )
                    project_contract = self._project_contract()
                    write_model(
                        self.island / "tests" / "contract.json",
                        project_contract.model_copy(
                            update={
                                "validation": project_contract.validation.model_copy(
                                    update={
                                        "components": dict(observed.components),
                                        "nets": dict(observed.nets),
                                    }
                                )
                            }
                        ),
                    )
                    write_model(
                        self.island / "tests" / "electrical.json",
                        electrical_contract().model_copy(update={"serial_peers": requirement}),
                    )
                    report = await self._inspect_both_surfaces(client)
                    findings = tuple(
                        item
                        for item in report.findings
                        if item.rule_id == "bus.serial_peer_reference_review"
                    )
                    if fault:
                        self.assertEqual(len(findings), 1)
                        self.assertEqual(
                            findings[0].subject,
                            "U1 / U2: serial reference-domain review",
                        )
                        self.assertIn("GND_A", findings[0].evidence["first_reference_net"])
                        self.assertIn("GND_B", findings[0].evidence["second_reference_net"])
                    else:
                        self.assertEqual(findings, ())
        await self._check_surface_registration()
