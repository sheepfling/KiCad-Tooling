"""Behavioral CLI/MCP parity using subprocess CLIs and the real MCP protocol.

Fixtures use small authored examples and explicitly synthetic retained native
netlists. No shared service is mocked. Comparison preserves domain statuses,
findings, identities, quantities, hashes and actions; only receipt paths, command
start timestamps and unittest's measured elapsed time are normalized.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

from mcp import Client
from pydantic import BaseModel

from kicad_tooling.hwrepo.contracts import parse_model_text, read_model, write_model
from kicad_tooling.hwrepo.discovery import load_config
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    AnalysisPending,
    CheckAllSummary,
    CheckEvidence,
    ComplementaryPinFunctionAlias,
    ComplementaryPinFunctionAliasMap,
    ComponentIdentity,
    ComponentRoleBinding,
    ComponentRoleMap,
    ComponentRolePin,
    ConnectorInterfaceReview,
    ConnectorInventoryReview,
    ConnectorReturnDistributionMap,
    ConnectorReturnDistributionRequirement,
    ContractCoachReport,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintReport,
    DesignLintRuleCatalog,
    DesignLintRuleOverride,
    DiagnosticReport,
    ElectricalAnalysisContract,
    ExternalProtectionInterfaceRequirement,
    I2cAddressBitRequirement,
    I2cAddressMap,
    I2cAddressSegmentRequirement,
    I2cPullupAnalysis,
    I2cPullupArrayChannelRequirement,
    I2cPullupArrayRequirement,
    I2cPullupBusRequirement,
    I2cPullupLineRequirement,
    I2cResponderAddressRequirement,
    ImportInventoryReport,
    InterfacePin,
    InterfaceRecord,
    InterfacesCatalog,
    LocalRescueReport,
    McpPurchasingPreferencesResult,
    ModelInventoryReport,
    NetlistContract,
    PartRecord,
    PartsCatalog,
    PartStatus,
    PcbDecouplingCapacitor,
    PcbDecouplingMap,
    PcbDecouplingRequirement,
    PcbProtectionPathMap,
    PcbProtectionPathRequirement,
    PcbReferencePlaneMap,
    PcbReferencePlaneRequirement,
    PcbSwitchingLoopEdge,
    PcbSwitchingLoopMap,
    PcbSwitchingLoopPad,
    PcbSwitchingLoopRequirement,
    PcbTrackWidthMap,
    PcbTrackWidthRequirement,
    ProjectImportReport,
    ProjectKind,
    ProjectManifest,
    ProjectScaffoldReport,
    ProjectStaticPipelineReport,
    ProjectTestContract,
    ProjectVerificationReport,
    PurchasingPreferences,
    PurchasingReport,
    ReferenceBondRequirement,
    Stm32CubeMxPinMap,
    Stm32PinExclusion,
    Stm32PinRequirement,
    TemplateDoctorReport,
    TemplateInventoryReport,
    ThreeDReport,
    ToolchainsCatalog,
    UsbReferencePinRequirement,
    ValidationSummary,
)
from kicad_tooling.validate import hashes
from tests import test_parts_workflow as native_fixture
from tests.support import initialize_git, reference_root
from tests.test_crystal_networks import crystal_map as synthetic_crystal_network_map
from tests.test_design_lint import header_only_spi_uart_netlist
from tests.test_electrical_parity import contract_netlist_xml
from tests.test_external_protection import protection_map as synthetic_protection_map
from tests.test_pcb_drc_coverage import pair_map as synthetic_differential_pair_map
from tests.test_pcb_drc_coverage import rules_text as synthetic_differential_pair_rules
from tests.test_power_paths import RULE_ID as POWER_PATH_RULE_ID
from tests.test_power_paths import power_path_map as synthetic_power_path_map
from tests.test_power_pin_paths import RULE_ID as POWER_INPUT_SOURCE_PATH_RULE_ID
from tests.test_power_sequences import RULE_ID as POWER_SEQUENCE_RULE_ID
from tests.test_power_sequences import power_sequence_map as synthetic_power_sequence_map
from tests.test_power_sequences import (
    power_sequence_output_cycle_map as synthetic_power_sequence_output_cycle_map,
)
from tests.test_power_sequences import (
    power_sequence_output_cycle_netlist as synthetic_power_sequence_output_cycle_netlist,
)
from tests.test_rc_filters import rc_filter_map as synthetic_rc_filter_map
from tests.test_regulator_feedback import regulator_feedback_map as synthetic_regulator_feedback_map
from tests.test_usb_data_paths import usb_data_map as synthetic_usb_data_path_map


def parity_workspace(base: Path) -> tuple[Path, Path, Path]:
    root = base / "repository"
    shutil.copytree(
        reference_root(),
        root,
        ignore=shutil.ignore_patterns(".git", "build", "__pycache__"),
    )
    manifest_path = root / "examples/projects/controller/project.json"
    manifest = read_model(manifest_path, ProjectManifest)
    write_model(
        manifest_path,
        manifest.model_copy(
            update={
                "connector_inventory_review": ConnectorInventoryReview(
                    basis="Synthetic parity fixture reviewed the complete schematic interface inventory"
                )
            }
        ),
    )
    initialize_git(root)
    island = root / "examples/projects/controller"
    incoming = root / "build/incoming/Incoming board.kicad_pro"
    incoming.parent.mkdir(parents=True)
    incoming.write_text("{}", encoding="utf-8")
    incoming.with_suffix(".kicad_sch").write_text("(kicad_sch)", encoding="utf-8")
    incoming.with_suffix(".kicad_pcb").write_text("(kicad_pcb)", encoding="utf-8")
    return root, island, incoming


async def parity_cli_process(base: Path, root: Path, module: str, *arguments: str):
    # A foreign cwd proves --root rather than process cwd selects the board.
    return await asyncio.to_thread(
        subprocess.run,
        (
            sys.executable,
            "-I",
            "-B",
            "-m",
            module,
            "--root",
            str(root),
            *arguments,
            "--format",
            "json",
        ),
        cwd=base,
        env=os.environ.copy(),
        text=True,
        capture_output=True,
        check=False,
        timeout=60,
    )


def parity_native_evidence(root: Path, island: Path) -> Path:
    """Retain a valid netlist whose independent electrical check explicitly failed."""
    manifest_path = island / "project.json"
    manifest = read_model(manifest_path, ProjectManifest)
    write_model(
        manifest_path,
        manifest.model_copy(
            update={
                "component_identity": ComponentIdentity(required=True, part_ids=("resistor-1k",)),
            }
        ),
    )
    write_model(
        root / "catalog/parts.json",
        PartsCatalog(
            schema_version="0.1",
            parts=(
                PartRecord(
                    id="resistor-1k",
                    revision="A",
                    description="Synthetic parity-test identity",
                    part_class="resistor",
                    unit="each",
                    manufacturer="Vishay",
                    mpn="MRS25000C1001FCT00",
                    datasheet_url="https://example.invalid/test-only",
                    lifecycle="active",
                    status=PartStatus.APPROVED,
                ),
            ),
        ),
    )
    config = load_config(root, manifest_path)
    directory = root / "build/native/controller"
    directory.mkdir(parents=True)
    (directory / "netlist.xml").write_text(native_fixture.NETLIST, encoding="utf-8")
    write_model(directory / "netlist.command.json", native_fixture.command())
    current = hashes(root, config.source_roots)
    write_model(
        directory / "summary.json",
        ValidationSummary(
            timestamp_utc="2026-09-24T00:00:00+00:00",
            checked_commit="LOCAL_UNBOUND",
            project_id="controller",
            project_kind=ProjectKind.PCB,
            checks={
                "source_scope": CheckEvidence(status="PASS", source_hashes=current),
                "source_unchanged": CheckEvidence(status="PASS", source_hashes=current),
                "toolchain": CheckEvidence(
                    status="PASS", observed_version=config.kicad_version, image=config.image
                ),
                "netlist": CheckEvidence(
                    status="FAIL", returncode=0, error="Independent electrical contract differs"
                ),
            },
            status="FAIL",
            artifacts_sha256={
                "netlist.xml": digest(directory / "netlist.xml"),
                "netlist.command.json": digest(directory / "netlist.command.json"),
            },
        ),
    )
    return directory / "summary.json"


class McpParityTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="mcp-semantic-parity-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.root, self.island, self.incoming = parity_workspace(self.base)

    async def cli_process(self, module, *arguments):
        return await parity_cli_process(self.base, self.root, module, *arguments)

    async def cli(self, module, model, *arguments, expected_exit=0):
        process = await self.cli_process(module, *arguments)
        self.assertEqual(process.returncode, expected_exit, process.stderr + process.stdout)
        return parse_model_text(process.stdout, model)

    async def call(self, client, tool, model, arguments=None):
        result = await client.call_tool(tool, arguments or {})
        self.assertFalse(result.is_error, result.content)
        self.assertIsNotNone(result.structured_content)
        return model.model_validate_json(json.dumps(result.structured_content))

    @staticmethod
    def semantic(report: BaseModel, receipt: str | None = None):
        def normalize(value, field=None):
            if isinstance(value, dict):
                return {key: normalize(item, key) for key, item in value.items()}
            if isinstance(value, list):
                return [normalize(item) for item in value]
            if isinstance(value, str):
                if field == "started_utc":
                    return "<command-start>"
                if receipt is not None:
                    value = value.replace(receipt, "<receipt>")
                if field == "stderr":
                    value = re.sub(
                        r"(?m)^(Ran \d+ tests? in )\d+(?:\.\d+)?s$", r"\1<elapsed>s", value
                    )
            return value

        return normalize(report.model_dump(mode="json"))

    def receipt_equal(self, cli, mcp, field="run_directory") -> None:
        left = getattr(cli, field)
        right = getattr(mcp, field)
        self.assertNotEqual(left, right)
        self.assertTrue(Path(left).is_relative_to(self.root / "build"))
        self.assertTrue(Path(right).is_relative_to(self.root / "build"))
        self.assertEqual(self.semantic(cli, left), self.semantic(mcp, right))

    def import_args(self):
        return {
            "source": self.incoming.relative_to(self.root).as_posix(),
            "project_id": "incoming",
            "toolchain_id": "kicad-10.0.5",
        }

    async def test_design_lint_rule_catalog_cli_mcp_parity(self) -> None:
        """List identical typed rules without requiring project or native evidence."""
        async with Client(create_server(self.root), mode="legacy") as client:
            cli = await self.cli(
                "kicad_tooling.design_lint",
                DesignLintRuleCatalog,
                "--catalog",
            )
            mcp = await self.call(
                client,
                "list_design_lint_rules",
                DesignLintRuleCatalog,
            )
        self.assertEqual(cli, mcp)
        self.assertTrue(cli.rules)
        self.assertEqual(cli.sha256, mcp.sha256)

    async def test_peer_component_power_pin_lint_cli_mcp_parity(self) -> None:
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"

        def render_netlist(*, split_domains: bool) -> str:
            supply_nodes = (
                '<net name="+3V3"><node ref="U1" pin="1"/><node ref="C1" pin="1"/></net>'
                '<net name="+5V"><node ref="U2" pin="1"/><node ref="C2" pin="1"/></net>'
                if split_domains
                else '<net name="+3V3"><node ref="U1" pin="1"/><node ref="U2" pin="1"/>'
                '<node ref="C1" pin="1"/><node ref="C2" pin="1"/></net>'
            )
            return_nodes = (
                '<net name="GND"><node ref="U1" pin="2"/><node ref="C1" pin="2"/></net>'
                '<net name="AGND"><node ref="U2" pin="2"/><node ref="C2" pin="2"/></net>'
                if split_domains
                else '<net name="GND"><node ref="U1" pin="2"/><node ref="U2" pin="2"/>'
                '<node ref="C1" pin="2"/><node ref="C2" pin="2"/></net>'
            )
            return (
                "<export><components>"
                '<comp ref="U1"><value>Synthetic peer</value>'
                "<footprint>Package:Controller</footprint>"
                '<libsource lib="Synthetic" part="PowerPeer"/></comp>'
                '<comp ref="U2"><value>Synthetic peer</value>'
                "<footprint>Package:Controller</footprint>"
                '<libsource lib="Synthetic" part="PowerPeer"/></comp>'
                '<comp ref="C1"><value>100n</value><libsource lib="Device" part="C"/></comp>'
                '<comp ref="C2"><value>100n</value><libsource lib="Device" part="C"/></comp>'
                '</components><libparts><libpart lib="Synthetic" part="PowerPeer"><pins>'
                '<pin num="1" name="VDD" type="power_in"/>'
                '<pin num="2" name="GND" type="power_in"/>'
                '</pins></libpart><libpart lib="Device" part="C"><pins>'
                '<pin num="1" name="1" type="passive"/>'
                '<pin num="2" name="2" type="passive"/>'
                "</pins></libpart></libparts><nets>"
                f"{supply_nodes}{return_nodes}</nets></export>"
            )

        def write_source_bound_netlist(*, split_domains: bool) -> None:
            netlist.write_text(render_netlist(split_domains=split_domains), encoding="utf-8")
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
            for split_domains, expected_status, expected_exit in (
                (True, "REVIEW", 1),
                (False, "PASS", 0),
            ):
                with self.subTest(split_domains=split_domains):
                    write_source_bound_netlist(split_domains=split_domains)
                    cli = await self.cli(
                        "kicad_tooling.design_lint",
                        DesignLintReport,
                        "--project",
                        "controller",
                        "--native-summary",
                        str(native),
                        expected_exit=expected_exit,
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
                    self.assertEqual(mcp.status, expected_status)
                    peer_findings = [
                        item
                        for item in mcp.findings
                        if item.rule_id == "component.peer_power_pin_assignment_divergence"
                    ]
                    self.assertEqual(len(peer_findings), 2 if split_domains else 0)

    async def test_peer_power_output_unconnected_lint_cli_mcp_parity(self) -> None:
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"

        def write_netlist(*, fault: bool) -> None:
            output_nets = (
                '<net name="VOUT"><node ref="U10" pin="2"/></net>'
                if fault
                else '<net name="VOUT_A"><node ref="U10" pin="2"/></net>'
                '<net name="VOUT_B"><node ref="U11" pin="2"/></net>'
            )
            text = native_fixture.NETLIST.replace(
                "</components><nets/>",
                '<comp ref="U10"><value>Synthetic output peer</value>'
                '<libsource lib="Synthetic" part="PowerOutputPeer"/></comp>'
                '<comp ref="U11"><value>Synthetic output peer</value>'
                '<libsource lib="Synthetic" part="PowerOutputPeer"/></comp>'
                '</components><libparts><libpart lib="Synthetic" '
                'part="PowerOutputPeer"><pins>'
                '<pin num="1" name="IO" type="passive"/>'
                '<pin num="2" name="OUT" type="power_out"/>'
                "</pins></libpart></libparts><nets>"
                '<net name="DATA"><node ref="U10" pin="1"/>'
                '<node ref="U11" pin="1"/></net>'
                f"{output_nets}</nets>",
            )
            netlist.write_text(text, encoding="utf-8")
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
                expected_status = "REVIEW" if fault else "PASS"
                cli = await self.cli(
                    "kicad_tooling.design_lint",
                    DesignLintReport,
                    "--project",
                    "controller",
                    "--native-summary",
                    str(native),
                    expected_exit=1 if fault else 0,
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
                self.assertEqual(mcp.status, expected_status)
                findings = tuple(
                    item
                    for item in mcp.findings
                    if item.rule_id == "component.peer_power_output_unconnected"
                )
                if fault:
                    self.assertEqual(len(findings), 1)
                    self.assertEqual(findings[0].evidence["unassigned_pins"], ("U11.2",))
                else:
                    self.assertEqual(findings, ())
                return mcp

            write_netlist(fault=True)
            await compare(fault=True)
            write_netlist(fault=False)
            await compare(fault=False)

    async def test_spi_peer_voltage_lint_cli_mcp_parity(self) -> None:
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

    async def test_serial_peer_voltage_lint_cli_mcp_parity(self) -> None:
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

    async def test_header_only_spi_uart_voltage_boundary_cli_mcp_parity(self) -> None:
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

    async def test_serial_connector_reference_lint_cli_mcp_parity(self) -> None:
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

    async def test_usb_peer_reference_lint_cli_mcp_parity(self) -> None:
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
                '<pin num="3" name="AGND" type="power_in"/>'
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

    async def test_can_peer_pair_divergence_lint_cli_mcp_parity(self) -> None:
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"
        netlist.write_text(
            """<export>
  <components>
    <comp ref="U1"><value>Synthetic CAN node</value><libsource lib="Synthetic" part="CanNode"/></comp>
    <comp ref="U2"><value>Synthetic CAN node</value><libsource lib="Synthetic" part="CanNode"/></comp>
    <comp ref="U3"><value>Synthetic CAN node</value><libsource lib="Synthetic" part="CanNode"/></comp>
    <comp ref="R1"><value>120R</value><libsource lib="Device" part="R"/></comp>
    <comp ref="R2"><value>120R</value><libsource lib="Device" part="R"/></comp>
  </components>
  <libparts>
    <libpart lib="Synthetic" part="CanNode"><pins>
      <pin num="1" name="CANH" type="passive"/>
      <pin num="2" name="CAN_L" type="passive"/>
    </pins></libpart>
    <libpart lib="Device" part="R"><pins>
      <pin num="1" name="~" type="passive"/>
      <pin num="2" name="~" type="passive"/>
    </pins></libpart>
  </libparts>
  <nets>
    <net name="NET_A"><node ref="U1" pin="1"/><node ref="U2" pin="1"/>
      <node ref="U3" pin="1"/><node ref="R1" pin="1"/><node ref="R2" pin="1"/></net>
    <net name="NET_B"><node ref="U1" pin="2"/><node ref="U2" pin="2"/>
      <node ref="R1" pin="2"/></net>
    <net name="NET_C"><node ref="U3" pin="2"/><node ref="R2" pin="2"/></net>
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
        self.assertEqual(
            {item.rule_id for item in mcp.findings},
            {"bus.can_peer_assignment_divergence"},
        )
        finding = mcp.findings[0]
        self.assertEqual(finding.evidence["shared_net"], ("NET_A",))
        self.assertEqual(finding.evidence["complementary_nets"], ("NET_B", "NET_C"))

    def damage_import(self) -> None:
        self.incoming.with_suffix(".kicad_sch").write_text(
            '(kicad_sch (sheet (property "Sheetfile" "missing.kicad_sch")))',
            encoding="utf-8",
        )

    def native_evidence(self) -> Path:
        """Retain a valid netlist whose independent electrical check explicitly failed."""
        return parity_native_evidence(self.root, self.island)

    async def test_inventory_parity(self) -> None:
        async with Client(create_server(self.root), mode="legacy") as client:
            for broken in (False, True):
                with self.subTest(malformed_peer=broken):
                    if broken:
                        (
                            self.root / "examples/projects/passive-signal-reference/project.json"
                        ).write_text("{bad")
                    cli = await self.cli(
                        "kicad_tooling.template",
                        TemplateInventoryReport,
                        "list",
                        expected_exit=int(broken),
                    )
                    mcp = await self.call(client, "list_projects", TemplateInventoryReport)
                    self.assertEqual(cli, mcp)
                    self.assertEqual(mcp.status, "FAIL" if broken else "PASS")
                    self.assertFalse(mcp.build_authorized)

    async def test_doctor_failure_parity(self) -> None:
        # The real subprocess runner sees exactly the same unavailable environment.
        with patch.dict(os.environ, {"PATH": ""}):
            cli = await self.cli(
                "kicad_tooling.template",
                TemplateDoctorReport,
                "doctor",
                "--native",
                "--project-id",
                "controller",
                "--runner",
                "local",
                expected_exit=1,
            )
            async with Client(create_server(self.root), mode="legacy") as client:
                mcp = await self.call(
                    client,
                    "doctor",
                    TemplateDoctorReport,
                    {
                        "project_id": "controller",
                        "native": True,
                        "runner": "local",
                    },
                )
        self.assertEqual(cli, mcp)
        self.assertEqual(mcp.status, "FAIL")
        self.assertTrue(any(item.status == "FAIL" for item in mcp.checks))

    async def test_import_preview_parity(self) -> None:
        async with Client(create_server(self.root), mode="legacy") as client:
            for broken in (False, True):
                with self.subTest(missing_sheet=broken):
                    if broken:
                        self.damage_import()
                    cli = await self.cli(
                        "kicad_tooling.template",
                        ProjectImportReport,
                        "import-project",
                        "--source",
                        str(self.incoming),
                        "--project-id",
                        "incoming",
                        "--toolchain",
                        "kicad-10.0.5",
                        "--dry-run",
                        expected_exit=int(broken),
                    )
                    mcp = await self.call(
                        client, "preview_import", ProjectImportReport, self.import_args()
                    )
                    self.assertEqual(cli, mcp)
                    self.assertEqual(mcp.status, "FAIL" if broken else "PASS")
                    self.assertTrue(mcp.dry_run)
                    self.assertFalse((self.root / "projects/incoming").exists())

    async def test_import_scan_parity(self) -> None:
        (self.incoming.parent / "incomplete.kicad_pro").write_text("{}", encoding="utf-8")
        cli = await self.cli(
            "kicad_tooling.template",
            ImportInventoryReport,
            "scan-imports",
            "--source-dir",
            str(self.incoming.parent),
            "--toolchain",
            "kicad-10.0.5",
            expected_exit=1,
        )
        async with Client(create_server(self.root), mode="legacy") as client:
            mcp = await self.call(
                client,
                "scan_imports",
                ImportInventoryReport,
                {
                    "source_directory": self.incoming.parent.relative_to(self.root).as_posix(),
                    "toolchain_id": "kicad-10.0.5",
                },
            )
        self.assertEqual(cli, mcp)
        self.assertEqual(mcp.status, "NEEDS_WORK")
        self.assertEqual({item.preview.status for item in mcp.candidates}, {"PASS", "FAIL"})

    async def test_missing_electrical_requirements_are_visible_without_claiming_failure(
        self,
    ) -> None:
        cli = await self.cli(
            "kicad_tooling.template", DiagnosticReport, "diagnose", "--project-id", "controller"
        )
        async with Client(create_server(self.root, allow_checks=True), mode="legacy") as client:
            mcp = await self.call(
                client, "diagnose_project", DiagnosticReport, {"project_id": "controller"}
            )
        self.receipt_equal(cli, mcp)
        self.assertEqual(mcp.status, "PASS")
        missing = next(row for row in mcp.findings if row.code == "ELECTRICAL_NOT_CONFIGURED")
        self.assertEqual(missing.severity, "REVIEW")
        self.assertIn("--init", missing.action)
        self.assertIn("--depth electrical", missing.action)

    async def test_import_diagnosis_parity(self) -> None:
        self.damage_import()
        cli = await self.cli(
            "kicad_tooling.template",
            DiagnosticReport,
            "diagnose",
            "--source",
            str(self.incoming),
            "--project-id",
            "incoming",
            "--toolchain",
            "kicad-10.0.5",
            expected_exit=1,
        )
        async with Client(create_server(self.root), mode="legacy") as client:
            mcp = await self.call(client, "diagnose_import", DiagnosticReport, self.import_args())
        self.receipt_equal(cli, mcp)
        self.assertEqual(mcp.status, "NEEDS_WORK")
        self.assertTrue(any(item.severity == "BLOCKING" for item in mcp.findings))

    async def test_project_diagnosis_parity(self) -> None:
        (self.island / "kicad/controller.kicad_sch").unlink()
        cli = await self.cli(
            "kicad_tooling.template",
            DiagnosticReport,
            "diagnose",
            "--project-id",
            "controller",
            expected_exit=1,
        )
        async with Client(create_server(self.root, allow_checks=True), mode="legacy") as client:
            mcp = await self.call(
                client, "diagnose_project", DiagnosticReport, {"project_id": "controller"}
            )
        self.receipt_equal(cli, mcp)
        self.assertEqual(mcp.status, "NEEDS_WORK")

    async def test_rescue_parity(self) -> None:
        (self.root / "examples/projects/passive-signal-reference/project.json").write_text("{bad")
        cli = await self.cli(
            "kicad_tooling.template",
            LocalRescueReport,
            "rescue",
            "--project-id",
            "controller",
            expected_exit=1,
        )
        async with Client(create_server(self.root), mode="legacy") as client:
            mcp = await self.call(
                client, "rescue_project", LocalRescueReport, {"project_id": "controller"}
            )
        self.receipt_equal(cli, mcp)
        self.assertEqual(mcp.status, "UNVERIFIED_GLOBAL")
        self.assertFalse(mcp.ci_eligible)
        self.assertFalse(mcp.release_eligible)

    async def test_selected_verification_parity(self) -> None:
        async with Client(create_server(self.root, allow_checks=True), mode="legacy") as client:
            for broken in (False, True):
                with self.subTest(missing_source=broken):
                    if broken:
                        (self.island / "kicad/controller.kicad_sch").unlink()
                    cli = await self.cli(
                        "kicad_tooling.verify",
                        ProjectVerificationReport,
                        "--project",
                        "controller",
                        expected_exit=int(broken),
                    )
                    mcp = await self.call(
                        client,
                        "check_project",
                        ProjectVerificationReport,
                        {"project_id": "controller"},
                    )
                    self.receipt_equal(cli, mcp)
                    self.assertEqual(mcp.status, "FAIL" if broken else "PASS")
                    self.assertFalse(mcp.build_authorized)
                    if not broken:
                        self.assertIsNone(mcp.electrical)
                        self.assertIn(
                            "Full electrical analysis was not run", " ".join(mcp.next_actions)
                        )

    async def test_scope_check_parity(self) -> None:
        cli = await self.cli(
            "kicad_tooling.ci", ProjectStaticPipelineReport, "--project", "controller"
        )
        async with Client(create_server(self.root, allow_checks=True), mode="legacy") as client:
            result = await client.call_tool("check_scope", {"project_ids": ["controller"]})
        self.assertFalse(result.is_error, result.content)
        self.assertIsNotNone(result.structured_content)
        mcp = ProjectStaticPipelineReport.model_validate_json(
            json.dumps(result.structured_content["report"]),
        )
        self.assertEqual(self.semantic(cli), self.semantic(mcp))
        self.assertEqual(mcp.projects, ("controller",))
        self.assertEqual(result.structured_content["status"], cli.status)
        self.assertFalse(result.structured_content["build_authorized"])

    async def test_tag_shard_scope_check_parity(self) -> None:
        cli = await self.cli(
            "kicad_tooling.ci",
            ProjectStaticPipelineReport,
            "--tag",
            "training",
            "--shard",
            "1/2",
            "--jobs",
            "2",
        )
        async with Client(create_server(self.root, allow_checks=True), mode="legacy") as client:
            result = await client.call_tool(
                "check_scope", {"tags": ["training"], "shard": "1/2", "jobs": 2}
            )
        self.assertFalse(result.is_error, result.content)
        self.assertIsNotNone(result.structured_content)
        mcp = ProjectStaticPipelineReport.model_validate_json(
            json.dumps(result.structured_content["report"]),
        )
        self.assertEqual(self.semantic(cli), self.semantic(mcp))
        self.assertEqual(len(mcp.projects), 3)

    async def test_native_scope_failure_parity(self) -> None:
        # Invalid native version fails the real CLI runner before any CAD command.
        # This exercises check_all on both surfaces, not a mocked service report.
        from tests.test_contract_coach import fake_executable

        binary = self.base / "bin"
        binary.mkdir()
        fake_executable(binary / "kicad-cli", 'print("0.0.0")\n')
        with patch.dict(
            os.environ, {"PATH": str(binary) + os.pathsep + os.environ.get("PATH", "")}
        ):
            cli = await self.cli(
                "kicad_tooling.ci",
                CheckAllSummary,
                "--kicad",
                "--project",
                "controller",
                "--output",
                str(self.root / "build/native-cli"),
                expected_exit=1,
            )
            async with Client(create_server(self.root, allow_checks=True), mode="legacy") as client:
                result = await client.call_tool(
                    "check_native_scope",
                    {
                        "view_id": "native-mcp",
                        "project_ids": ["controller"],
                    },
                )
        self.assertFalse(result.is_error, result.content)
        self.assertIsNotNone(result.structured_content)
        mcp = CheckAllSummary.model_validate_json(json.dumps(result.structured_content["report"]))
        self.assertEqual(cli, mcp)
        self.assertEqual(mcp.status, "FAIL")
        self.assertTrue(any(item.status == "FAIL" for item in mcp.projects))
        self.assertEqual(result.structured_content["status"], cli.status)
        self.assertFalse(result.structured_content["build_authorized"])
        cli_native = read_model(
            self.root / "build/native-cli/controller/summary.json", ValidationSummary
        )
        mcp_native = read_model(
            Path(result.structured_content["run_directory"]) / "controller/summary.json",
            ValidationSummary,
        )
        self.assertEqual(cli_native.checks, mcp_native.checks)
        self.assertEqual(cli_native.source, mcp_native.source)
        self.assertEqual(cli_native.project_id, mcp_native.project_id)
        self.assertEqual(cli_native.status, "FAIL")
        self.assertEqual(mcp_native.status, "FAIL")

    async def test_new_project_parity(self) -> None:
        cli = await self.cli(
            "kicad_tooling.template",
            ProjectScaffoldReport,
            "new-project",
            "--project-id",
            "fresh-board",
            "--kind",
            "pcb_only",
            "--toolchain",
            "kicad-10.0.5",
        )
        directory = self.root / "projects/fresh-board"
        expected_files = {
            path.relative_to(directory).as_posix(): path.read_bytes()
            for path in directory.rglob("*")
            if path.is_file()
        }
        shutil.rmtree(directory)
        async with Client(create_server(self.root, allow_writes=True), mode="legacy") as client:
            mcp = await self.call(
                client,
                "new_project",
                ProjectScaffoldReport,
                {
                    "project_id": "fresh-board",
                    "kind": "pcb_only",
                    "toolchain_id": "kicad-10.0.5",
                },
            )
        self.assertEqual(cli, mcp)
        self.assertEqual(
            expected_files,
            {
                path.relative_to(directory).as_posix(): path.read_bytes()
                for path in directory.rglob("*")
                if path.is_file()
            },
        )

    async def test_import_write_parity(self) -> None:
        cli = await self.cli(
            "kicad_tooling.template",
            ProjectImportReport,
            "import-project",
            "--source",
            str(self.incoming),
            "--project-id",
            "incoming",
            "--toolchain",
            "kicad-10.0.5",
        )
        directory = self.root / "projects/incoming"
        expected_files = {
            path.relative_to(directory).as_posix(): path.read_bytes()
            for path in directory.rglob("*")
            if path.is_file()
        }
        shutil.rmtree(directory)
        async with Client(create_server(self.root, allow_writes=True), mode="legacy") as client:
            mcp = await self.call(client, "import_project", ProjectImportReport, self.import_args())
        self.assertEqual(cli, mcp)
        self.assertFalse(mcp.dry_run)
        self.assertEqual(
            expected_files,
            {
                path.relative_to(directory).as_posix(): path.read_bytes()
                for path in directory.rglob("*")
                if path.is_file()
            },
        )

    async def test_contract_inspection_parity(self) -> None:
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"
        netlist.write_text(
            '<export><components><comp ref="J1"><value>Synthetic port</value>'
            '<libsource lib="Synthetic" part="Port"/><units><unit name="A"><pins>'
            '<pin num="1"/><pin num="7"/></pins></unit></units></comp>'
            '<comp ref="J2"><value>Synthetic port</value>'
            '<libsource lib="Synthetic" part="Port"/><units><unit name="A"><pins>'
            '<pin num="1"/><pin num="7"/></pins></unit></units></comp></components>'
            '<libparts><libpart lib="Synthetic" part="Port"><pins>'
            '<pin num="1" name="PWR" type="passive"/>'
            '<pin num="7" name="GND" type="passive"/></pins></libpart></libparts><nets>'
            '<net name="0V CTRL 1"><node ref="J1" pin="7"/></net>'
            '<net name="0V CTRL 2"><node ref="J2" pin="7"/></net>'
            '<net name="+5V"><node ref="J1" pin="1"/></net>'
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
            for case in ("valid", "empty", "tampered"):
                with self.subTest(case=case):
                    if case == "empty":
                        netlist.write_text(
                            "<export><components/><nets/></export>", encoding="utf-8"
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
                    elif case == "tampered":
                        (native.parent / "netlist.xml").write_text("<export/>", encoding="utf-8")
                    cli = await self.cli(
                        "kicad_tooling.contract_coach",
                        ContractCoachReport,
                        "--project-id",
                        "controller",
                        "--native-summary",
                        str(native),
                        expected_exit=int(case != "valid"),
                    )
                    mcp = await self.call(
                        client,
                        "inspect_contract",
                        ContractCoachReport,
                        {
                            "project_id": "controller",
                            "native_summary": native.relative_to(self.root).as_posix(),
                        },
                    )
                    self.assertEqual(cli, mcp)
                    self.assertEqual(
                        mcp.status, "READY_FOR_REVIEW" if case == "valid" else "BLOCKED"
                    )
                    if case == "valid":
                        self.assertEqual(mcp.native_status, "FAIL")
                        self.assertEqual(mcp.review_state, "UNREVIEWED")
                        self.assertEqual(
                            set(mcp.return_net_groups[0].nets), {"0V CTRL 1", "0V CTRL 2"}
                        )
                        power = next(
                            group
                            for group in mcp.similar_connector_pin_groups
                            if group.function == "PWR"
                        )
                        self.assertEqual(power.pins["J2.1"], ())
                        self.assertIn("approved connector pinout", " ".join(mcp.next_actions))
                    elif case == "empty":
                        self.assertIn("contains no component records", mcp.issues[0])
                        self.assertIsNone(mcp.observed)
                    self.assertFalse(mcp.electrical_coverage)

    async def test_empty_native_netlist_blocks_design_lint_cli_mcp_parity(self) -> None:
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"
        netlist.write_text("<export><components/><nets/></export>", encoding="utf-8")
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
        self.assertEqual(mcp.status, "BLOCKED")
        self.assertIn("contains no component records", mcp.issues[0])
        self.assertFalse(mcp.findings)
        self.assertIsNone(mcp.netlist_sha256)

    async def test_design_lint_parity(self) -> None:
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"
        netlist.write_text(
            '<export><components><comp ref="J1"><value>Synthetic port</value>'
            '<libsource lib="Synthetic" part="Port"/></comp><comp ref="J2">'
            '<value>Synthetic port</value><libsource lib="Synthetic" part="SerialPort"/>'
            '</comp><comp ref="J3"><value>Synthetic port</value>'
            '<libsource lib="Synthetic" part="Port"/></comp><comp ref="J4">'
            '<value>Synthetic aux port</value><libsource lib="Synthetic" part="AuxPort"/>'
            '</comp><comp ref="J5"><value>Synthetic USB data port</value>'
            '<libsource lib="Synthetic" part="UsbDataPort"/></comp>'
            '<comp ref="J6"><value>Synthetic serial return port</value>'
            '<libsource lib="Synthetic" part="SerialReturnPort"/></comp>'
            '<comp ref="J9"><value>Synthetic generic peer port</value>'
            '<libsource lib="Synthetic" part="GenericPeerPort"/></comp>'
            '<comp ref="J10"><value>Synthetic generic peer port</value>'
            '<libsource lib="Synthetic" part="GenericPeerPort"/></comp>'
            '<comp ref="J11"><value>Synthetic USB-C candidate</value>'
            '<libsource lib="Synthetic" part="UsbCPort"/></comp>'
            '<comp ref="J12"><value>Synthetic generic power-input connector</value>'
            '<libsource lib="Synthetic" part="GenericPowerInputPort"/></comp>'
            '<comp ref="U7"><value>Synthetic nonstandard-reference connector</value>'
            '<libsource lib="Connector_Generic" part="Conn_01x02"/></comp>'
            '<comp ref="U8"><value>Synthetic test point</value>'
            '<libsource lib="Connector" part="TestPoint_Alt"/></comp>'
            '<comp ref="J7"><value>Synthetic USB supply</value>'
            '<libsource lib="Synthetic" part="PowerInput"/></comp>'
            '<comp ref="J8"><value>Synthetic serial supply</value>'
            '<libsource lib="Synthetic" part="PowerOutput"/></comp>'
            '<comp ref="U4"><value>Synthetic pair naming candidate</value>'
            '<libsource lib="Synthetic" part="PairEndpoint"/></comp>'
            '<comp ref="U1"><value>Synthetic two-wire target</value>'
            '<libsource lib="Synthetic" part="I2cTarget"/></comp>'
            '<comp ref="U2"><value>Synthetic multi-supply logic</value>'
            '<libsource lib="Synthetic" part="MultiSupplyLogic"/></comp>'
            '<comp ref="U3"><value>Synthetic reset input</value>'
            '<libsource lib="Synthetic" part="ResetInput"/></comp>'
            '<comp ref="U5"><value>Synthetic SPI peripheral</value>'
            '<libsource lib="Synthetic" part="SpiPeripheral"/></comp>'
            '<comp ref="U12"><value>Synthetic open-collector alert</value>'
            '<libsource lib="Synthetic" part="OpenCollector"/></comp>'
            '<comp ref="U13"><value>Synthetic alert receiver</value>'
            '<libsource lib="Synthetic" part="AlertReceiver"/></comp>'
            '<comp ref="U14"><value>Synthetic open-emitter ready output</value>'
            '<libsource lib="Synthetic" part="OpenEmitter"/></comp>'
            '<comp ref="U15"><value>Synthetic ready receiver</value>'
            '<libsource lib="Synthetic" part="AlertReceiver"/></comp>'
            '<comp ref="U16"><value>Synthetic SuperSpeed endpoint</value>'
            '<libsource lib="Synthetic" part="UsbSuperSpeedEndpoint"/></comp>'
            '<comp ref="U17"><value>Synthetic vendor differential device</value>'
            '<libsource lib="Synthetic" part="VendorDifferentialDevice"/></comp>'
            '<comp ref="R1"><value>1k</value><libsource lib="Device" part="R"/></comp>'
            '<comp ref="R2"><value>1k</value><libsource lib="Device" part="R"/></comp>'
            '<comp ref="R3"><value>1k</value><libsource lib="Device" part="R"/></comp>'
            '<comp ref="C1"><value>100n</value><libsource lib="Device" part="C"/></comp>'
            '<comp ref="D1"><value>LED</value><libsource lib="Device" part="LED"/></comp>'
            "</components>"
            '<libparts><libpart lib="Synthetic" part="Port"><pins>'
            '<pin num="1" name="PWR" type="passive"/>'
            '<pin num="7" name="GND" type="passive"/>'
            '<pin num="8" name="" type="passive"/></pins></libpart>'
            '<libpart lib="Synthetic" part="SerialPort"><pins>'
            '<pin num="1" name="PWR" type="passive"/>'
            '<pin num="7" name="RTN" type="passive"/></pins></libpart>'
            '<libpart lib="Synthetic" part="AuxPort"><pins>'
            '<pin num="1" name="+3V3" type="passive"/>'
            '<pin num="2" name="2" type="passive"/></pins></libpart>'
            '<libpart lib="Synthetic" part="UsbDataPort"><pins>'
            '<pin num="1" name="D+" type="passive"/>'
            '<pin num="2" name="D−" type="passive"/></pins></libpart>'
            '<libpart lib="Synthetic" part="PairEndpoint"><pins>'
            '<pin num="1" name="1" type="passive"/>'
            '<pin num="2" name="2" type="passive"/></pins></libpart>'
            '<libpart lib="Synthetic" part="SerialReturnPort"><pins>'
            '<pin num="9" name="9" type="passive"/></pins></libpart>'
            '<libpart lib="Synthetic" part="GenericPeerPort"><pins>'
            '<pin num="1" name="1" type="passive"/>'
            '<pin num="2" name="" type="passive"/></pins></libpart>'
            '<libpart lib="Synthetic" part="GenericPowerInputPort"><pins>'
            '<pin num="1" name="1" type="power_in"/></pins></libpart>'
            '<libpart lib="Synthetic" part="UsbCPort"><pins>'
            '<pin num="4" name="CC1" type="passive"/>'
            '<pin num="5" name="CC2" type="passive"/></pins></libpart>'
            '<libpart lib="Synthetic" part="PowerInput"><pins>'
            '<pin num="1" name="1" type="passive"/></pins></libpart>'
            '<libpart lib="Synthetic" part="PowerOutput"><pins>'
            '<pin num="1" name="1" type="passive"/></pins></libpart>'
            '<libpart lib="Synthetic" part="I2cTarget"><pins>'
            '<pin num="1" name="SDA" type="passive"/>'
            '<pin num="2" name="SCL" type="passive"/></pins></libpart>'
            '<libpart lib="Synthetic" part="MultiSupplyLogic"><pins>'
            '<pin num="1" name="VDD" type="power_in"/>'
            '<pin num="2" name="VDD" type="power_in"/></pins></libpart>'
            '<libpart lib="Synthetic" part="ResetInput"><pins>'
            '<pin num="1" name="~{RESET}" type="input"/>'
            '<pin num="2" name="POR_B" type="input"/>'
            '<pin num="3" name="PORN" type="input"/></pins></libpart>'
            '<libpart lib="Synthetic" part="SpiPeripheral"><pins>'
            '<pin num="1" name="CS_N" type="input"/>'
            '<pin num="2" name="SCK" type="input"/>'
            '<pin num="3" name="MOSI" type="input"/></pins></libpart>'
            '<libpart lib="Synthetic" part="OpenCollector"><pins>'
            '<pin num="1" name="ALERT_N" type="open_collector"/></pins></libpart>'
            '<libpart lib="Synthetic" part="OpenEmitter"><pins>'
            '<pin num="1" name="READY_N" type="open_emitter"/></pins></libpart>'
            '<libpart lib="Synthetic" part="UsbSuperSpeedEndpoint"><pins>'
            '<pin num="1" name="StdB_SSTX+" type="passive"/>'
            '<pin num="2" name="StdB_SSTX-" type="passive"/></pins></libpart>'
            '<libpart lib="Synthetic" part="VendorDifferentialDevice"><pins>'
            '<pin num="1" name="OUTP" type="output"/>'
            '<pin num="2" name="OUTN" type="output"/></pins></libpart>'
            '<libpart lib="Synthetic" part="AlertReceiver"><pins>'
            '<pin num="1" name="ALERT_N" type="input"/></pins></libpart>'
            '<libpart lib="Device" part="R"><pins>'
            '<pin num="1" name="1" type="passive"/>'
            '<pin num="2" name="2" type="passive"/></pins></libpart>'
            '<libpart lib="Device" part="C"><pins>'
            '<pin num="1" name="1" type="passive"/>'
            '<pin num="2" name="2" type="passive"/></pins></libpart>'
            '<libpart lib="Device" part="LED"><pins>'
            '<pin num="1" name="A" type="passive"/>'
            '<pin num="2" name="K" type="passive"/></pins></libpart></libparts><nets>'
            '<net name="GND1"><node ref="J1" pin="7"/><node ref="J3" pin="7"/></net>'
            '<net name="GND2"><node ref="J2" pin="7"/></net>'
            '<net name="+5V"><node ref="J1" pin="1"/></net>'
            '<net name="PERIPHERAL_SIGNAL"><node ref="J1" pin="8"/></net>'
            '<net name="CH2_VDD"><node ref="J7" pin="1"/></net>'
            '<net name="CH3_VDD"><node ref="J8" pin="1"/></net>'
            '<net name="USB_DATA"><node ref="J5" pin="1"/><node ref="J5" pin="2"/></net>'
            '<net name="USB_GND"><node ref="J4" pin="2"/></net>'
            '<net name="SERIAL_RETURN"><node ref="J6" pin="9"/></net>'
            '<net name="PEER_SHARED"><node ref="J9" pin="1"/><node ref="J10" pin="1"/></net>'
            '<net name="PEER_A"><node ref="J9" pin="2"/></net>'
            '<net name="PEER_B"><node ref="J10" pin="2"/></net>'
            '<net name="TYPEC_CC1"><node ref="J11" pin="4"/></net>'
            '<net name="TYPEC_CC2"><node ref="J11" pin="5"/></net>'
            '<net name="USB_A_DP"><node ref="U4" pin="1"/></net>'
            '<net name="USB_A_DM"><node ref="U4" pin="2"/></net>'
            '<net name="+3V3"><node ref="R1" pin="2"/><node ref="R2" pin="2"/>'
            '<node ref="R3" pin="2"/><node ref="U2" pin="1"/><node ref="C1" pin="1"/>'
            '<node ref="D1" pin="1"/></net>'
            '<net name="GND"><node ref="C1" pin="2"/><node ref="D1" pin="2"/></net>'
            '<net name="+1V8"><node ref="U2" pin="2"/></net>'
            '<net name="SPI_CS_N"><node ref="U5" pin="1"/></net>'
            '<net name="SPI_SCK"><node ref="U5" pin="2"/></net>'
            '<net name="SPI_MOSI"><node ref="U5" pin="3"/></net>'
            '<net name="I2C_SDA"><node ref="U1" pin="1"/><node ref="R1" pin="1"/>'
            '<node ref="R2" pin="1"/></net>'
            '<net name="I2C_SCL"><node ref="U1" pin="2"/><node ref="R3" pin="1"/></net>'
            '<net name="ALERT_N"><node ref="U12" pin="1"/><node ref="U13" pin="1"/></net>'
            '<net name="READY_N"><node ref="U14" pin="1"/><node ref="U15" pin="1"/></net>'
            '<net name="SUPER_TX_POS"><node ref="U16" pin="1"/></net>'
            '<net name="VENDOR_LANE0_P"><node ref="U17" pin="1"/></net>'
            "</nets></export>",
            encoding="utf-8",
        )
        summary = read_model(native, ValidationSummary)
        summary = summary.model_copy(
            update={
                "artifacts_sha256": {
                    **summary.artifacts_sha256,
                    "netlist.xml": digest(netlist),
                }
            }
        )
        write_model(native, summary)

        contract_path = self.island / "tests/contract.json"
        contract = read_model(contract_path, ProjectTestContract)
        write_model(
            contract_path,
            contract.model_copy(
                update={
                    "design_lint": DesignLintPolicy(
                        complementary_pin_function_alias_map=ComplementaryPinFunctionAliasMap(
                            entries=(
                                ComplementaryPinFunctionAlias(
                                    symbol="Synthetic:VendorDifferentialDevice",
                                    family="vendor data lane 0",
                                    positive_functions=("OUTP",),
                                    negative_functions=("OUTN",),
                                    basis="Synthetic fixture explicitly defines these native pin functions as a pair",
                                ),
                            )
                        )
                    )
                }
            ),
        )

        async with Client(create_server(self.root), mode="legacy") as client:

            async def compare(expected_status: str, exit_code: int) -> DesignLintReport:
                cli = await self.cli(
                    "kicad_tooling.design_lint",
                    DesignLintReport,
                    "--project",
                    "controller",
                    "--native-summary",
                    str(native),
                    expected_exit=exit_code,
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
                self.assertEqual(mcp.status, expected_status, mcp.issues)
                return mcp

            uncovered = await compare("REVIEW", 1)
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
            source_text = source_text.replace(
                '<net name="+5V"><node ref="J1" pin="1"/></net>',
                '<net name="+5V"><node ref="J1" pin="1"/><node ref="R2" pin="2"/></net>',
            )
            source_text = source_text.replace(
                '<net name="+3V3"><node ref="R1" pin="2"/><node ref="R2" pin="2"/>',
                '<net name="+3V3"><node ref="R1" pin="2"/>',
            )
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
            mixed_rails = await compare("REVIEW", 1)
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
            open_report = await compare("REVIEW", 1)
            assert open_report.connector_coverage is not None
            self.assertEqual(open_report.connector_coverage.status, "COMPLETE")
            self.assertEqual(
                open_report.connector_coverage.inventory_review_basis,
                "Synthetic review covered all connector candidates in the schematic",
            )
            self.assertEqual(open_report.native_status, "FAIL")
            self.assertEqual(len(open_report.findings), 25)
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

            dnp_xml = netlist.read_text(encoding="utf-8").replace(
                '<comp ref="J3"><value>Synthetic port</value>',
                '<comp ref="J3"><property name="dnp" value="yes"/><value>Synthetic port</value>',
            )
            self.assertNotEqual(dnp_xml, netlist.read_text(encoding="utf-8"))
            netlist.write_text(dnp_xml, encoding="utf-8")
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
            open_report = await compare("REVIEW", 1)
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
            accepted = await compare("PASS", 0)
            self.assertEqual(accepted.netlist_sha256, open_report.netlist_sha256)
            self.assertNotEqual(accepted.policy_sha256, open_report.policy_sha256)
            self.assertTrue(all(item.disposition == "IGNORED" for item in accepted.findings))

    async def test_i2c_mapped_array_hint_resolution_cli_mcp_parity(self) -> None:
        native = self.native_evidence()
        manifest_path = self.island / "project.json"
        manifest = read_model(manifest_path, ProjectManifest)
        checks_path = self.island / manifest.checks
        project_test = read_model(checks_path, ProjectTestContract)
        electrical_relative = "tests/i2c-electrical.json"
        electrical_path = self.island / electrical_relative
        electrical_path.parent.mkdir(parents=True, exist_ok=True)
        pullup_spec = I2cPullupAnalysis(
            basis="Synthetic mapped resistor-array requirement",
            buses=(
                I2cPullupBusRequirement(
                    id="main",
                    basis="Synthetic two-wire interface requirement",
                    sda=I2cPullupLineRequirement(
                        net="I2C_SDA",
                        rail="+3V3",
                        minimum_ohms=1_000,
                        maximum_ohms=100_000,
                    ),
                    scl=I2cPullupLineRequirement(
                        net="I2C_SCL",
                        rail="+3V3",
                        minimum_ohms=1_000,
                        maximum_ohms=100_000,
                    ),
                ),
            ),
            arrays=(
                I2cPullupArrayRequirement(
                    reference="RN1",
                    expected_symbol="Synthetic:ResistorArray",
                    expected_footprint="Synthetic:RA4",
                    expected_value="4x4.7k",
                    basis="Synthetic array datasheet pin map",
                    channels=(
                        I2cPullupArrayChannelRequirement(
                            id="sda",
                            signal_pin="RN1.1",
                            rail_pin="RN1.2",
                            signal_net="I2C_SDA",
                            rail_net="+3V3",
                            resistance_ohms=4_700,
                            basis="Synthetic channel 1 map",
                        ),
                        I2cPullupArrayChannelRequirement(
                            id="scl",
                            signal_pin="RN1.3",
                            rail_pin="RN1.4",
                            signal_net="I2C_SCL",
                            rail_net="+3V3",
                            resistance_ohms=4_700,
                            basis="Synthetic channel 2 map",
                        ),
                    ),
                ),
            ),
        )
        write_model(
            checks_path,
            project_test.model_copy(update={"electrical": electrical_relative}),
        )
        write_model(
            electrical_path,
            ElectricalAnalysisContract(
                project_id="controller",
                ngspice_version="not run by synthetic parity fixture",
                grounding=AnalysisPending(reason="Synthetic fixture does not exercise grounding."),
                i2c_pullups=pullup_spec,
                power=AnalysisPending(reason="Synthetic fixture does not exercise power budgets."),
                high_frequency=AnalysisPending(
                    reason="Synthetic fixture does not exercise high-frequency analysis."
                ),
            ),
        )
        netlist = native.parent / "netlist.xml"
        netlist.write_text(
            "<export><components>"
            '<comp ref="U1"><value>Synthetic two-wire target</value>'
            '<libsource lib="Synthetic" part="I2cTarget"/></comp>'
            '<comp ref="RN1"><value>4x4.7k</value><footprint>Synthetic:RA4</footprint>'
            '<libsource lib="Synthetic" part="ResistorArray"/></comp>'
            "</components><libparts>"
            '<libpart lib="Synthetic" part="I2cTarget"><pins>'
            '<pin num="1" name="SDA" type="passive"/>'
            '<pin num="2" name="SCL" type="passive"/></pins></libpart>'
            '<libpart lib="Synthetic" part="ResistorArray"><pins>'
            '<pin num="1" name="1" type="passive"/><pin num="2" name="2" type="passive"/>'
            '<pin num="3" name="3" type="passive"/><pin num="4" name="4" type="passive"/>'
            "</pins></libpart></libparts><nets>"
            '<net name="I2C_SDA"><node ref="U1" pin="1"/><node ref="RN1" pin="1"/></net>'
            '<net name="I2C_SCL"><node ref="U1" pin="2"/><node ref="RN1" pin="3"/></net>'
            '<net name="+3V3"><node ref="RN1" pin="2"/><node ref="RN1" pin="4"/></net>'
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
        self.assertEqual(mcp.i2c_pullup_heuristic_coverage.status, "COMPLETE")
        self.assertEqual(
            mcp.i2c_pullup_heuristic_coverage.source_path,
            electrical_path.relative_to(self.root).as_posix(),
        )
        self.assertEqual(
            mcp.i2c_pullup_heuristic_coverage.netlist_sha256,
            digest(netlist),
        )
        self.assertNotIn("bus.i2c_missing_pullup", {item.rule_id for item in mcp.findings})

    async def test_output_led_lint_cli_mcp_parity(self) -> None:
        """Native pin-type metadata drives the same LED review through CLI and MCP."""
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"

        def write_netlist(output_type: str, *, custom_led: bool = False) -> None:
            led_component = (
                '<comp ref="D1"><value>LED</value>'
                "<footprint>Training:LED_0603</footprint>"
                '<fields><field name="PART_ID">training-led</field></fields>'
                '<libsource lib="Training" part="LED_5mm"/></comp>'
                if custom_led
                else '<comp ref="D1"><value>LED</value><libsource lib="Device" part="LED"/></comp>'
            )
            led_libpart = (
                '<libpart lib="Training" part="LED_5mm"><pins>'
                '<pin num="1" name="A" type="passive"/>'
                '<pin num="2" name="K" type="passive"/>'
                "</pins></libpart>"
                if custom_led
                else '<libpart lib="Device" part="LED"><pins>'
                '<pin num="1" name="A" type="passive"/>'
                '<pin num="2" name="K" type="passive"/>'
                "</pins></libpart>"
            )
            netlist.write_text(
                "<export><components>"
                '<comp ref="U1"><value>Synthetic output</value>'
                '<libsource lib="Synthetic" part="Output"/></comp>'
                f"{led_component}"
                "</components><libparts>"
                '<libpart lib="Synthetic" part="Output"><pins>'
                f'<pin num="1" name="GPIO" type="{output_type}"/>'
                "</pins></libpart>"
                f"{led_libpart}</libparts><nets>"
                '<net name="GPIO_LED"><node ref="U1" pin="1"/>'
                '<node ref="D1" pin="1"/></net>'
                '<net name="GND"><node ref="D1" pin="2"/></net>'
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

        write_netlist("output")
        async with Client(create_server(self.root), mode="legacy") as client:

            async def compare() -> DesignLintReport:
                process = await self.cli_process(
                    "kicad_tooling.design_lint",
                    "--project",
                    "controller",
                    "--native-summary",
                    str(native),
                )
                cli = parse_model_text(process.stdout, DesignLintReport)
                self.assertEqual(process.returncode, 1 if cli.status != "PASS" else 0)
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

            fault = await compare()
            finding = next(
                item
                for item in fault.findings
                if item.rule_id == "component.led_directly_driven_from_output"
            )
            self.assertEqual(finding.evidence["output_pins"], ("U1.1",))
            self.assertEqual(finding.evidence["output_pin_types"], ("U1.1=output",))

            write_netlist("input")
            control = await compare()
            self.assertNotIn(
                "component.led_directly_driven_from_output",
                {item.rule_id for item in control.findings},
            )

            write_netlist("output", custom_led=True)
            unclassified = await compare()
            self.assertNotIn(
                "component.led_directly_driven_from_output",
                {item.rule_id for item in unclassified.findings},
            )

            contract_path = self.island / "tests/contract.json"
            test_contract = read_model(contract_path, ProjectTestContract)
            role_map = ComponentRoleMap(
                entries=(
                    ComponentRoleBinding(
                        part_id="training-led",
                        symbol="Training:LED_5mm",
                        footprint="Training:LED_0603",
                        role="led",
                        pins=(
                            ComponentRolePin(number="1", function="A", electrical_type="passive"),
                            ComponentRolePin(number="2", function="K", electrical_type="passive"),
                        ),
                        basis="Synthetic parity fixture reviewed this exact two-pin symbol identity",
                    ),
                )
            )
            project_policy = (test_contract.design_lint or DesignLintPolicy()).model_copy(
                update={"component_role_map": role_map}
            )
            write_model(
                contract_path,
                test_contract.model_copy(update={"design_lint": project_policy}),
            )
            configured_fault = await compare()
            self.assertNotEqual(unclassified.policy_sha256, configured_fault.policy_sha256)
            custom_finding = next(
                item
                for item in configured_fault.findings
                if item.rule_id == "component.led_directly_driven_from_output"
            )
            self.assertEqual(custom_finding.evidence["role_part_id"], ("training-led",))
            self.assertEqual(custom_finding.evidence["role_basis"], (role_map.entries[0].basis,))

            write_netlist("input", custom_led=True)
            configured_control = await compare()
            self.assertNotIn(
                "component.led_directly_driven_from_output",
                {item.rule_id for item in configured_control.findings},
            )

    async def test_unconnected_generic_component_power_input_cli_mcp_parity(self) -> None:
        """Generic native power-input pins use the same review on both surfaces."""
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"

        def write_netlist(connected: bool) -> None:
            supply = (
                '<net name="POWER_INPUT_TEST"><node ref="U1" pin="1"/></net>' if connected else ""
            )
            netlist.write_text(
                "<export><components>"
                '<comp ref="U1"><value>Synthetic component</value>'
                "<footprint>Synthetic:Component</footprint>"
                '<libsource lib="Synthetic" part="GenericPowerInputComponent"/>'
                "</comp></components><libparts>"
                '<libpart lib="Synthetic" part="GenericPowerInputComponent"><pins>'
                '<pin num="1" name="1" type="power_in"/>'
                '<pin num="2" name="2" type="passive"/>'
                "</pins></libpart></libparts><nets>"
                '<net name="SIGNAL"><node ref="U1" pin="2"/></net>'
                f"{supply}</nets></export>",
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

            async def compare() -> DesignLintReport:
                process = await self.cli_process(
                    "kicad_tooling.design_lint",
                    "--project",
                    "controller",
                    "--native-summary",
                    str(native),
                )
                cli = parse_model_text(process.stdout, DesignLintReport)
                self.assertEqual(process.returncode, 1 if cli.status != "PASS" else 0)
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

            write_netlist(connected=False)
            fault = await compare()
            self.assertEqual(fault.status, "REVIEW", fault.issues)
            self.assertEqual(
                {item.rule_id for item in fault.findings},
                {"component.unconnected_power_input"},
            )
            self.assertEqual(
                fault.findings[0].subject,
                "U1.1: generic native power-input pin is unassigned",
            )

            write_netlist(connected=True)
            control = await compare()
            self.assertEqual(control.status, "PASS")
            self.assertNotIn(
                "component.unconnected_power_input",
                {item.rule_id for item in control.findings},
            )

    async def test_custom_capacitor_role_lint_cli_mcp_parity(self) -> None:
        """An exact custom capacitor role clears only the shared LINT-046 hint."""
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"

        def write_netlist(reference_net: str) -> None:
            netlist.write_text(
                "<export><components>"
                '<comp ref="U1"><value>Synthetic IC</value><footprint>Synthetic:IC</footprint>'
                '<libsource lib="Synthetic" part="PowerInput"/></comp>'
                '<comp ref="U2"><value>Synthetic source</value>'
                "<footprint>Synthetic:PowerSource</footprint>"
                '<libsource lib="Synthetic" part="PowerSource"/></comp>'
                '<comp ref="C1"><value>100nF</value>'
                "<footprint>Synthetic:CAP123_0603</footprint>"
                '<fields><field name="PART_ID">synthetic-decoupling-capacitor</field></fields>'
                '<libsource lib="Vendor" part="CAP123"/></comp>'
                "</components><libparts>"
                '<libpart lib="Synthetic" part="PowerInput"><pins>'
                '<pin num="1" name="VDD" type="power_in"/>'
                '<pin num="2" name="GND" type="power_in"/>'
                "</pins></libpart>"
                '<libpart lib="Synthetic" part="PowerSource"><pins>'
                '<pin num="1" name="VOUT" type="power_out"/>'
                "</pins></libpart>"
                '<libpart lib="Vendor" part="CAP123"><pins>'
                '<pin num="1" name="1" type="passive"/>'
                '<pin num="2" name="2" type="passive"/>'
                "</pins></libpart></libparts><nets>"
                '<net name="+3V3"><node ref="U1" pin="1"/>'
                '<node ref="U2" pin="1"/><node ref="C1" pin="1"/></net>'
                '<net name="GND"><node ref="U1" pin="2"/>'
                + ('<node ref="C1" pin="2"/>' if reference_net == "GND" else "")
                + "</net>"
                + (
                    '<net name="CAP_REF"><node ref="C1" pin="2"/></net>'
                    if reference_net == "CAP_REF"
                    else ""
                )
                + "</nets></export>",
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

        write_netlist("GND")
        async with Client(create_server(self.root), mode="legacy") as client:

            async def compare() -> DesignLintReport:
                process = await self.cli_process(
                    "kicad_tooling.design_lint",
                    "--project",
                    "controller",
                    "--native-summary",
                    str(native),
                )
                cli = parse_model_text(process.stdout, DesignLintReport)
                self.assertEqual(process.returncode, 1 if cli.status != "PASS" else 0)
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

            unclassified = await compare()
            self.assertEqual(unclassified.status, "REVIEW")
            self.assertIn(
                "power.ic_rail_without_fitted_capacitor",
                {item.rule_id for item in unclassified.findings},
            )

            contract_path = self.island / "tests/contract.json"
            test_contract = read_model(contract_path, ProjectTestContract)
            role_map = ComponentRoleMap(
                entries=(
                    ComponentRoleBinding(
                        part_id="synthetic-decoupling-capacitor",
                        symbol="Vendor:CAP123",
                        footprint="Synthetic:CAP123_0603",
                        role="capacitor",
                        pins=(
                            ComponentRolePin(number="1", function="1", electrical_type="passive"),
                            ComponentRolePin(number="2", function="2", electrical_type="passive"),
                        ),
                        basis="Synthetic parity fixture reviews the exact opaque capacitor identity",
                    ),
                )
            )
            project_policy = (test_contract.design_lint or DesignLintPolicy()).model_copy(
                update={"component_role_map": role_map}
            )
            write_model(
                contract_path,
                test_contract.model_copy(update={"design_lint": project_policy}),
            )
            mapped_control = await compare()
            self.assertEqual(mapped_control.status, "PASS", mapped_control.issues)
            self.assertNotIn(
                "power.ic_rail_without_fitted_capacitor",
                {item.rule_id for item in mapped_control.findings},
            )

            write_netlist("CAP_REF")
            mapped_fault = await compare()
            self.assertEqual(mapped_fault.status, "REVIEW")
            self.assertIn(
                "power.ic_rail_without_fitted_capacitor",
                {item.rule_id for item in mapped_fault.findings},
            )

    async def test_same_net_two_pin_passive_lint_cli_mcp_parity(self) -> None:
        """Compare the same-net review finding and its distinct-net control."""
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"

        def write_netlist(same_net: bool) -> None:
            if same_net:
                nets = '<net name="SHARED"><node ref="R1" pin="1"/>'
                nets += '<node ref="R1" pin="2"/></net>'
            else:
                nets = (
                    '<net name="INPUT"><node ref="R1" pin="1"/></net>'
                    '<net name="OUTPUT"><node ref="R1" pin="2"/></net>'
                )
            netlist.write_text(
                "<export><components>"
                '<comp ref="R1"><value>10k</value><footprint>Synthetic:R_0603</footprint>'
                '<libsource lib="Device" part="R"/></comp>'
                '</components><libparts><libpart lib="Device" part="R"><pins>'
                '<pin num="1" name="1" type="passive"/>'
                '<pin num="2" name="2" type="passive"/>'
                f"</pins></libpart></libparts><nets>{nets}</nets></export>",
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

        write_netlist(same_net=True)
        async with Client(create_server(self.root), mode="legacy") as client:

            async def compare() -> DesignLintReport:
                process = await self.cli_process(
                    "kicad_tooling.design_lint",
                    "--project",
                    "controller",
                    "--native-summary",
                    str(native),
                )
                cli = parse_model_text(process.stdout, DesignLintReport)
                self.assertEqual(process.returncode, 1 if cli.status != "PASS" else 0)
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

            fault = await compare()
            self.assertEqual(fault.status, "REVIEW")
            finding = next(
                item
                for item in fault.findings
                if item.rule_id == "component.two_pin_passive_same_net"
            )
            self.assertEqual(
                finding.evidence["pin_assignments"],
                (
                    "R1.1 -> SHARED",
                    "R1.2 -> SHARED",
                ),
            )
            self.assertEqual(finding.evidence["symbol"], ("Device:R",))

            write_netlist(same_net=False)
            control = await compare()
            self.assertNotIn(
                "component.two_pin_passive_same_net",
                {item.rule_id for item in control.findings},
            )

    async def test_same_net_two_pin_diode_lint_cli_mcp_parity(self) -> None:
        """Compare the same-net diode review finding and distinct-net control."""
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"

        def write_netlist(same_net: bool) -> None:
            if same_net:
                nets = '<net name="SHARED"><node ref="D1" pin="1"/>'
                nets += '<node ref="D1" pin="2"/></net>'
            else:
                nets = (
                    '<net name="ANODE"><node ref="D1" pin="1"/></net>'
                    '<net name="CATHODE"><node ref="D1" pin="2"/></net>'
                )
            netlist.write_text(
                "<export><components>"
                '<comp ref="D1"><value>1N4148</value>'
                "<footprint>Synthetic:SOD-123</footprint>"
                '<libsource lib="Device" part="D"/></comp>'
                '</components><libparts><libpart lib="Device" part="D"><pins>'
                '<pin num="1" name="A" type="passive"/>'
                '<pin num="2" name="K" type="passive"/>'
                f"</pins></libpart></libparts><nets>{nets}</nets></export>",
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

        write_netlist(same_net=True)
        async with Client(create_server(self.root), mode="legacy") as client:

            async def compare() -> DesignLintReport:
                process = await self.cli_process(
                    "kicad_tooling.design_lint",
                    "--project",
                    "controller",
                    "--native-summary",
                    str(native),
                )
                cli = parse_model_text(process.stdout, DesignLintReport)
                self.assertEqual(process.returncode, 1 if cli.status != "PASS" else 0)
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

            fault = await compare()
            self.assertEqual(fault.status, "REVIEW")
            finding = next(
                item
                for item in fault.findings
                if item.rule_id == "component.two_pin_diode_same_net"
            )
            self.assertEqual(
                finding.evidence["pin_assignments"],
                ("D1.1 -> SHARED", "D1.2 -> SHARED"),
            )
            self.assertEqual(finding.evidence["symbol"], ("Device:D",))

            write_netlist(same_net=False)
            control = await compare()
            self.assertNotIn(
                "component.two_pin_diode_same_net",
                {item.rule_id for item in control.findings},
            )

    async def test_same_net_two_pin_crystal_lint_cli_mcp_parity(self) -> None:
        """Compare the same-net crystal review finding and distinct-net control."""
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"

        def write_netlist(same_net: bool) -> None:
            if same_net:
                nets = '<net name="SHARED"><node ref="Y1" pin="1"/>'
                nets += '<node ref="Y1" pin="2"/></net>'
            else:
                nets = (
                    '<net name="XTAL_IN"><node ref="Y1" pin="1"/></net>'
                    '<net name="XTAL_OUT"><node ref="Y1" pin="2"/></net>'
                )
            netlist.write_text(
                "<export><components>"
                '<comp ref="Y1"><value>16 MHz</value>'
                "<footprint>Synthetic:Crystal</footprint>"
                '<libsource lib="Device" part="Crystal"/></comp>'
                '</components><libparts><libpart lib="Device" part="Crystal"><pins>'
                '<pin num="1" name="1" type="passive"/>'
                '<pin num="2" name="2" type="passive"/>'
                f"</pins></libpart></libparts><nets>{nets}</nets></export>",
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

        write_netlist(same_net=True)
        async with Client(create_server(self.root), mode="legacy") as client:

            async def compare() -> DesignLintReport:
                process = await self.cli_process(
                    "kicad_tooling.design_lint",
                    "--project",
                    "controller",
                    "--native-summary",
                    str(native),
                )
                cli = parse_model_text(process.stdout, DesignLintReport)
                self.assertEqual(process.returncode, 1 if cli.status != "PASS" else 0)
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

            fault = await compare()
            self.assertEqual(fault.status, "REVIEW")
            finding = next(
                item
                for item in fault.findings
                if item.rule_id == "component.two_pin_crystal_same_net"
            )
            self.assertEqual(
                finding.evidence["pin_assignments"],
                ("Y1.1 -> SHARED", "Y1.2 -> SHARED"),
            )
            self.assertEqual(finding.evidence["symbol"], ("Device:Crystal",))

            write_netlist(same_net=False)
            control = await compare()
            self.assertNotIn(
                "component.two_pin_crystal_same_net",
                {item.rule_id for item in control.findings},
            )

    async def test_same_net_two_pin_fuse_lint_cli_mcp_parity(self) -> None:
        """Compare the same-net fuse review finding and distinct-net control."""
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"

        def write_netlist(same_net: bool) -> None:
            if same_net:
                nets = '<net name="SHARED"><node ref="F1" pin="1"/>'
                nets += '<node ref="F1" pin="2"/></net>'
            else:
                nets = (
                    '<net name="INPUT"><node ref="F1" pin="1"/></net>'
                    '<net name="OUTPUT"><node ref="F1" pin="2"/></net>'
                )
            netlist.write_text(
                "<export><components>"
                '<comp ref="F1"><value>1A</value><footprint>Synthetic:Fuse_1206</footprint>'
                '<libsource lib="Device" part="Fuse"/></comp>'
                '</components><libparts><libpart lib="Device" part="Fuse"><pins>'
                '<pin num="1" name="1" type="passive"/>'
                '<pin num="2" name="2" type="passive"/>'
                f"</pins></libpart></libparts><nets>{nets}</nets></export>",
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

        write_netlist(same_net=True)
        async with Client(create_server(self.root), mode="legacy") as client:

            async def compare() -> DesignLintReport:
                process = await self.cli_process(
                    "kicad_tooling.design_lint",
                    "--project",
                    "controller",
                    "--native-summary",
                    str(native),
                )
                cli = parse_model_text(process.stdout, DesignLintReport)
                self.assertEqual(process.returncode, 1 if cli.status != "PASS" else 0)
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

            fault = await compare()
            self.assertEqual(fault.status, "REVIEW")
            finding = next(
                item for item in fault.findings if item.rule_id == "component.two_pin_fuse_same_net"
            )
            self.assertEqual(
                finding.evidence["pin_assignments"],
                ("F1.1 -> SHARED", "F1.2 -> SHARED"),
            )
            self.assertEqual(finding.evidence["symbol"], ("Device:Fuse",))

            write_netlist(same_net=False)
            control = await compare()
            self.assertNotIn(
                "component.two_pin_fuse_same_net",
                {item.rule_id for item in control.findings},
            )

    async def test_same_net_two_pin_ferrite_lint_cli_mcp_parity(self) -> None:
        """Compare the ferrite bypass hint and distinct-net control on both surfaces."""
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"

        def write_netlist(same_net: bool) -> None:
            if same_net:
                nets = '<net name="SHARED"><node ref="FB1" pin="1"/>'
                nets += '<node ref="FB1" pin="2"/></net>'
            else:
                nets = (
                    '<net name="INPUT"><node ref="FB1" pin="1"/></net>'
                    '<net name="OUTPUT"><node ref="FB1" pin="2"/></net>'
                )
            netlist.write_text(
                "<export><components>"
                '<comp ref="FB1"><value>600R@100MHz</value>'
                "<footprint>Synthetic:Ferrite_0603</footprint>"
                '<libsource lib="Device" part="FerriteBead"/></comp>'
                '</components><libparts><libpart lib="Device" part="FerriteBead"><pins>'
                '<pin num="1" name="1" type="passive"/>'
                '<pin num="2" name="2" type="passive"/>'
                f"</pins></libpart></libparts><nets>{nets}</nets></export>",
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

        write_netlist(same_net=True)
        async with Client(create_server(self.root), mode="legacy") as client:

            async def compare() -> DesignLintReport:
                process = await self.cli_process(
                    "kicad_tooling.design_lint",
                    "--project",
                    "controller",
                    "--native-summary",
                    str(native),
                )
                cli = parse_model_text(process.stdout, DesignLintReport)
                self.assertEqual(process.returncode, 1 if cli.status != "PASS" else 0)
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

            fault = await compare()
            self.assertEqual(fault.status, "REVIEW")
            finding = next(
                item
                for item in fault.findings
                if item.rule_id == "component.two_pin_ferrite_same_net"
            )
            self.assertEqual(
                finding.evidence["pin_assignments"],
                ("FB1.1 -> SHARED", "FB1.2 -> SHARED"),
            )
            self.assertEqual(finding.evidence["symbol"], ("Device:FerriteBead",))

            write_netlist(same_net=False)
            control = await compare()
            self.assertNotIn(
                "component.two_pin_ferrite_same_net",
                {item.rule_id for item in control.findings},
            )

    async def test_same_net_two_pin_switch_lint_cli_mcp_parity(self) -> None:
        """Compare exact SPST bypass review and the distinct-net control on both surfaces."""
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"

        def write_netlist(same_net: bool) -> None:
            if same_net:
                nets = '<net name="SHARED"><node ref="SW1" pin="1"/>'
                nets += '<node ref="SW1" pin="2"/></net>'
            else:
                nets = (
                    '<net name="INPUT"><node ref="SW1" pin="1"/></net>'
                    '<net name="OUTPUT"><node ref="SW1" pin="2"/></net>'
                )
            netlist.write_text(
                "<export><components>"
                '<comp ref="SW1"><value>Synthetic SPST</value>'
                "<footprint>Synthetic:SPST_THT</footprint>"
                '<libsource lib="Switch" part="SW_SPST"/></comp>'
                "</components><libparts>"
                '<libpart lib="Switch" part="SW_SPST"><pins>'
                '<pin num="1" name="A" type="passive"/>'
                '<pin num="2" name="B" type="passive"/>'
                f"</pins></libpart></libparts><nets>{nets}</nets></export>",
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

            async def compare() -> DesignLintReport:
                process = await self.cli_process(
                    "kicad_tooling.design_lint",
                    "--project",
                    "controller",
                    "--native-summary",
                    str(native),
                )
                cli = parse_model_text(process.stdout, DesignLintReport)
                self.assertEqual(process.returncode, 1 if cli.status != "PASS" else 0)
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

            write_netlist(same_net=True)
            fault = await compare()
            self.assertEqual(fault.status, "REVIEW")
            finding = next(
                item
                for item in fault.findings
                if item.rule_id == "component.two_pin_switch_same_net"
            )
            self.assertEqual(
                finding.evidence["pin_assignments"], ("SW1.1 -> SHARED", "SW1.2 -> SHARED")
            )
            self.assertEqual(finding.evidence["symbol"], ("Switch:SW_SPST",))

            write_netlist(same_net=False)
            control = await compare()
            self.assertNotIn(
                "component.two_pin_switch_same_net",
                {item.rule_id for item in control.findings},
            )

    async def test_connector_capacitor_only_dc_reference_lint_cli_mcp_parity(self) -> None:
        """Compare a connector/capacitor-only net hint and local-driver control."""
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"

        def write_netlist(with_driver: bool) -> None:
            driver_component = (
                '<comp ref="U1"><value>Synthetic output</value>'
                '<libsource lib="Synthetic" part="SignalDriver"/></comp>'
                if with_driver
                else ""
            )
            driver_libpart = (
                '<libpart lib="Synthetic" part="SignalDriver"><pins>'
                '<pin num="1" name="OUT" type="output"/></pins></libpart>'
                if with_driver
                else ""
            )
            driver_node = '<node ref="U1" pin="1"/>' if with_driver else ""
            netlist.write_text(
                "<export><components>"
                '<comp ref="J1"><value>Synthetic input connector</value>'
                '<libsource lib="Connector_Generic" part="Conn_01x02"/></comp>'
                '<comp ref="C1"><value>100n</value>'
                '<libsource lib="Device" part="C"/></comp>'
                f"{driver_component}</components><libparts>"
                '<libpart lib="Connector_Generic" part="Conn_01x02"><pins>'
                '<pin num="1" name="1" type="passive"/>'
                '<pin num="2" name="2" type="passive"/></pins></libpart>'
                '<libpart lib="Device" part="C"><pins>'
                '<pin num="1" name="1" type="passive"/>'
                '<pin num="2" name="2" type="passive"/></pins></libpart>'
                f"{driver_libpart}</libparts><nets>"
                '<net name="ANALOG_IN"><node ref="J1" pin="1"/>'
                f'<node ref="C1" pin="1"/>{driver_node}</net>'
                '<net name="GND"><node ref="J1" pin="2"/>'
                '<node ref="C1" pin="2"/></net>'
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

        write_netlist(with_driver=False)
        async with Client(create_server(self.root), mode="legacy") as client:

            async def compare() -> DesignLintReport:
                process = await self.cli_process(
                    "kicad_tooling.design_lint",
                    "--project",
                    "controller",
                    "--native-summary",
                    str(native),
                )
                cli = parse_model_text(process.stdout, DesignLintReport)
                self.assertEqual(process.returncode, 1 if cli.status != "PASS" else 0)
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

            fault = await compare()
            self.assertEqual(fault.status, "REVIEW")
            finding = next(
                item
                for item in fault.findings
                if item.rule_id == "net.connector_capacitor_only_no_dc_anchor"
            )
            self.assertEqual(finding.evidence["connector_pins"], ("J1.1",))
            self.assertEqual(finding.evidence["capacitor_pins"], ("C1.1",))

            write_netlist(with_driver=True)
            control = await compare()
            self.assertNotIn(
                "net.connector_capacitor_only_no_dc_anchor",
                {item.rule_id for item in control.findings},
            )

    async def test_standard_and_reviewed_custom_connector_identity_cli_mcp_parity(self) -> None:
        """Share standard and explicitly reviewed custom connector identity across surfaces."""
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"

        def write_netlist(*, common_return: bool, supply_connected: bool) -> None:
            if common_return:
                return_net = (
                    '<net name="GND"><node ref="J1" pin="1"/>'
                    '<node ref="U7" pin="1"/><node ref="A1" pin="1"/>'
                    '<node ref="A2" pin="1"/><node ref="A3" pin="1"/></net>'
                )
            else:
                return_net = (
                    '<net name="GND_A"><node ref="J1" pin="1"/></net>'
                    '<net name="GND_B"><node ref="U7" pin="1"/></net>'
                    '<net name="CUSTOM_GND_A"><node ref="A1" pin="1"/>'
                    '<node ref="A2" pin="1"/></net>'
                    '<net name="CUSTOM_GND_B"><node ref="A3" pin="1"/></net>'
                )
            second_supply = '<node ref="U7" pin="2"/>' if supply_connected else ""
            data_pins = '<node ref="J1" pin="3"/><node ref="U7" pin="3"/>'
            custom_supply = (
                '<net name="CUSTOM_SUPPLY"><node ref="A1" pin="2"/>'
                '<node ref="A2" pin="2"/><node ref="A3" pin="2"/></net>'
                if supply_connected
                else '<net name="CUSTOM_SUPPLY_A"><node ref="A1" pin="2"/>'
                '<node ref="A2" pin="2"/></net>'
                '<net name="CUSTOM_SUPPLY_B"><node ref="A3" pin="2"/></net>'
            )
            netlist.write_text(
                "<export><components>"
                '<comp ref="J1"><value>Port A</value>'
                '<libsource lib="Connector_Generic" part="Conn_01x03"/></comp>'
                '<comp ref="U7"><value>Port B</value>'
                '<libsource lib="Connector_Generic" part="Conn_01x03"/></comp>'
                '<comp ref="A1"><value>Custom Port A</value>'
                '<libsource lib="Synthetic" part="CustomPort"/></comp>'
                '<comp ref="A2"><value>Custom Port B</value>'
                '<libsource lib="Synthetic" part="CustomPort"/></comp>'
                '<comp ref="A3"><value>Custom Port C</value>'
                '<libsource lib="Synthetic" part="CustomPort"/></comp>'
                "</components><libparts>"
                '<libpart lib="Connector_Generic" part="Conn_01x03"><pins>'
                '<pin num="1" name="GND" type="passive"/>'
                '<pin num="2" name="VBUS" type="passive"/>'
                '<pin num="3" name="DATA" type="passive"/>'
                "</pins></libpart>"
                '<libpart lib="Synthetic" part="CustomPort"><pins>'
                '<pin num="1" name="Pin_1" type="passive"/>'
                '<pin num="2" name="Pin_2" type="passive"/>'
                "</pins></libpart></libparts><nets>"
                f"{return_net}"
                f'<net name="+5V"><node ref="J1" pin="2"/>{second_supply}</net>'
                f'<net name="DATA">{data_pins}</net>'
                f"{custom_supply}"
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
        custom_reviews = tuple(
            ConnectorInterfaceReview(
                reference=reference,
                disposition="interface",
                interface_id="synthetic-port",
                basis="Synthetic reviewed custom connector pinout",
                pin_map={"1": "1", "2": "2"},
            )
            for reference in ("A1", "A2", "A3")
        )

        def set_custom_connector_review(
            enabled: bool,
            *,
            references: tuple[str, ...] = ("A1", "A2", "A3"),
        ) -> None:
            selected_reviews = (
                tuple(item for item in custom_reviews if item.reference in references)
                if enabled
                else ()
            )
            write_model(
                manifest_path,
                manifest.model_copy(
                    update={
                        "interfaces": ("synthetic-port",) if selected_reviews else (),
                        "connector_reviews": selected_reviews,
                        "connector_inventory_review": ConnectorInventoryReview(
                            basis="Synthetic review covered the connector inventory"
                        ),
                    }
                ),
            )

        write_model(
            self.root / "catalog/interfaces.json",
            InterfacesCatalog(
                schema_version="1",
                interfaces=(
                    InterfaceRecord(
                        id="synthetic-port",
                        revision="synthetic-1",
                        pins=(
                            InterfacePin(
                                number="1",
                                signal="GND",
                                role="return",
                                direction="bidirectional",
                                voltage_domain="synthetic-reference",
                                mating="synthetic peer",
                                orientation="straight",
                                mechanical_clearance="synthetic",
                            ),
                            InterfacePin(
                                number="2",
                                signal="POWER",
                                role="supply",
                                direction="bidirectional",
                                voltage_domain="external-5v",
                                mating="synthetic peer",
                                orientation="straight",
                                mechanical_clearance="synthetic",
                            ),
                        ),
                    ),
                ),
            ),
        )
        set_custom_connector_review(True)
        write_netlist(common_return=False, supply_connected=False)
        async with Client(create_server(self.root), mode="legacy") as client:

            async def compare() -> DesignLintReport:
                process = await self.cli_process(
                    "kicad_tooling.design_lint",
                    "--project",
                    "controller",
                    "--native-summary",
                    str(native),
                )
                cli = parse_model_text(process.stdout, DesignLintReport)
                self.assertEqual(process.returncode, 1 if cli.status != "PASS" else 0)
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

            fault = await compare()
            assert fault.connector_peer_pin_coverage is not None
            self.assertEqual(
                fault.connector_peer_pin_coverage.netlist_sha256,
                fault.netlist_sha256,
            )
            self.assertEqual(
                fault.connector_peer_pin_coverage.repeated_function_finding_count,
                sum(item.rule_id == "connector.repeated_pin_function" for item in fault.findings),
            )
            repeated_rule_ids = {
                item.rule_id
                for item in fault.findings
                if item.rule_id
                in {
                    "connector.peer_pin_assignment_outlier",
                    "connector.peer_pin_assignment_divergence",
                }
            }
            self.assertFalse(
                repeated_rule_ids,
                "fully mapped generic connector peers should use the more specific role finding",
            )
            repeated_groups = tuple(
                item.evidence
                for item in fault.findings
                if item.rule_id == "connector.repeated_pin_function"
            )
            self.assertTrue(any("U7.1" in evidence for evidence in repeated_groups))
            self.assertTrue(any("U7.2" in evidence for evidence in repeated_groups))
            self.assertTrue(
                any("A1.1" in evidence and "A2.1" in evidence for evidence in repeated_groups)
            )
            self.assertTrue(any("A3.1" in evidence for evidence in repeated_groups))
            custom_return = next(
                evidence
                for evidence in repeated_groups
                if "A1.1" in evidence and "A2.1" in evidence
            )
            self.assertEqual(custom_return["A1.1"], ("CUSTOM_GND_A",))
            self.assertEqual(custom_return["A2.1"], ("CUSTOM_GND_A",))
            self.assertEqual(custom_return["A3.1"], ("CUSTOM_GND_B",))
            custom_supply = next(
                item
                for item in fault.findings
                if "same source-reviewed voltage domain" in item.message
            )
            self.assertEqual(custom_supply.evidence["A1.2"], ("CUSTOM_SUPPLY_A",))
            self.assertEqual(custom_supply.evidence["A2.2"], ("CUSTOM_SUPPLY_A",))
            self.assertEqual(custom_supply.evidence["A3.2"], ("CUSTOM_SUPPLY_B",))
            self.assertEqual(
                custom_supply.evidence["role_classification_sources"],
                (
                    (
                        "A1.2: project interface catalog role=supply; "
                        "voltage_domain=external-5v; native symbol function=Pin_2"
                    ),
                    (
                        "A2.2: project interface catalog role=supply; "
                        "voltage_domain=external-5v; native symbol function=Pin_2"
                    ),
                    (
                        "A3.2: project interface catalog role=supply; "
                        "voltage_domain=external-5v; native symbol function=Pin_2"
                    ),
                ),
            )
            self.assertEqual(custom_supply.evidence["reviewed_voltage_domain"], ("external-5v",))
            assert fault.connector_coverage is not None
            self.assertEqual(
                {
                    item.reference: item.status
                    for item in fault.connector_coverage.entries
                    if item.reference in {"A1", "A2", "A3"}
                },
                {"A1": "COVERED", "A2": "COVERED", "A3": "COVERED"},
            )

            set_custom_connector_review(True, references=("A1", "A3"))
            partial_map = await compare()
            assert partial_map.connector_coverage is not None
            self.assertEqual(
                next(
                    item.status
                    for item in partial_map.connector_coverage.entries
                    if item.reference == "A2"
                ),
                "UNDECLARED",
            )
            partial_role_findings = tuple(
                item
                for item in partial_map.findings
                if item.rule_id == "connector.repeated_pin_function"
                and "A1.1" in item.evidence
                and "A3.1" in item.evidence
            )
            self.assertTrue(partial_role_findings)
            self.assertFalse(
                {
                    item.rule_id
                    for item in partial_map.findings
                    if item.rule_id
                    in {
                        "connector.peer_pin_assignment_outlier",
                        "connector.peer_pin_assignment_divergence",
                    }
                    and item.evidence.get("symbol") == ("Synthetic:CustomPort",)
                },
                "the mapped role finding fully covers the two compared peers",
            )

            set_custom_connector_review(False)
            unreviewed_custom = await compare()
            assert unreviewed_custom.connector_coverage is not None
            self.assertFalse(
                {item.reference for item in unreviewed_custom.connector_coverage.entries}
                & {"A1", "A2", "A3"}
            )
            self.assertFalse(
                any(
                    pin.startswith(("A1.", "A2.", "A3."))
                    for item in unreviewed_custom.findings
                    if item.rule_id == "connector.repeated_pin_function"
                    for pin in item.evidence
                )
            )

            set_custom_connector_review(True)
            write_netlist(common_return=True, supply_connected=True)
            control = await compare()
            self.assertNotIn(
                "connector.repeated_pin_function",
                {item.rule_id for item in control.findings},
            )

            netlist.write_text(
                "<export><components>"
                + "".join(
                    f'<comp ref="J{index}"><value>Generic peer port</value>'
                    '<libsource lib="Connector_Generic" part="Conn_01x02"/></comp>'
                    for index in range(1, 4)
                )
                + "</components><libparts>"
                '<libpart lib="Connector_Generic" part="Conn_01x02"><pins>'
                '<pin num="1" name="Pin_1" type="passive"/>'
                '<pin num="2" name="Pin_2" type="passive"/>'
                "</pins></libpart></libparts><nets>"
                + "".join(
                    f'<net name="PORT_{pin}_{peer}"><node ref="J{peer}" pin="{pin}"/></net>'
                    for pin in (1, 2)
                    for peer in range(1, 4)
                )
                + "</nets></export>",
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
            placeholders = await compare()
            placeholder_divergences = [
                item
                for item in placeholders.findings
                if item.rule_id == "connector.peer_pin_assignment_divergence"
            ]
            self.assertEqual(len(placeholder_divergences), 2)
            self.assertFalse(
                any(
                    item.rule_id == "connector.repeated_pin_function"
                    for item in placeholders.findings
                )
            )
            self.assertTrue(
                all(
                    item.evidence["missing_pin_function_pins"] == ("J1.1", "J2.1", "J3.1")
                    if item.subject.endswith("pin 1")
                    else item.evidence["missing_pin_function_pins"] == ("J1.2", "J2.2", "J3.2")
                    for item in placeholder_divergences
                )
            )

            peer_interface = InterfaceRecord(
                id="generic-peer-port",
                revision="synthetic-1",
                pins=tuple(
                    InterfacePin(
                        number=number,
                        signal=f"SIGNAL_{number}",
                        role="signal",
                        direction="bidirectional",
                        voltage_domain="logic-3v3",
                        mating=f"SIGNAL_{number}",
                        orientation="straight",
                        mechanical_clearance="synthetic",
                    )
                    for number in ("1", "2")
                ),
            )
            write_model(
                self.root / "catalog/interfaces.json",
                InterfacesCatalog(schema_version="1", interfaces=(peer_interface,)),
            )

            def set_generic_peer_groups(groups: tuple[str, ...]) -> None:
                references = ("J1", "J2", "J3")
                selected = tuple(
                    ConnectorInterfaceReview(
                        reference=reference,
                        disposition="interface",
                        interface_id="generic-peer-port",
                        basis=f"Reviewed {reference} as an external signal interface",
                        pin_map={"1": "1", "2": "2"},
                        peer_assignment_group=groups[index],
                        peer_assignment_basis=(
                            f"Reviewed {reference} within peer-assignment group {groups[index]}"
                        ),
                    )
                    for index, reference in enumerate(references)
                )
                write_model(
                    manifest_path,
                    manifest.model_copy(
                        update={
                            "interfaces": ("generic-peer-port",),
                            "connector_reviews": selected,
                            "connector_inventory_review": ConnectorInventoryReview(
                                basis="Synthetic review covered the generic connector inventory"
                            ),
                        }
                    ),
                )

            set_generic_peer_groups(("uart-1", "uart-2", "uart-3"))
            separate_groups = await compare()
            self.assertFalse(
                {
                    item.rule_id
                    for item in separate_groups.findings
                    if item.rule_id
                    in {
                        "connector.peer_pin_assignment_outlier",
                        "connector.peer_pin_assignment_divergence",
                    }
                }
            )
            assert separate_groups.connector_coverage is not None
            self.assertEqual(
                {
                    entry.reference: entry.peer_assignment_group
                    for entry in separate_groups.connector_coverage.entries
                },
                {"J1": "uart-1", "J2": "uart-2", "J3": "uart-3"},
            )

            set_generic_peer_groups(("uart-ports", "uart-ports", "uart-ports"))
            same_group = await compare()
            same_group_findings = tuple(
                item
                for item in same_group.findings
                if item.rule_id == "connector.peer_pin_assignment_divergence"
            )
            self.assertEqual(len(same_group_findings), 2)
            self.assertTrue(
                all(
                    item.evidence["peer_assignment_group"] == ("uart-ports",)
                    for item in same_group_findings
                )
            )

            set_generic_peer_groups(("uart-1", "uart-2", "uart-3"))
            set_generic_peer_reviews = read_model(manifest_path, ProjectManifest)
            write_model(
                manifest_path,
                set_generic_peer_reviews.model_copy(
                    update={"connector_reviews": set_generic_peer_reviews.connector_reviews[:2]}
                ),
            )
            partial_group = await compare()
            self.assertTrue(
                any(
                    item.rule_id == "connector.peer_pin_assignment_divergence"
                    for item in partial_group.findings
                ),
                "an unreviewed connector keeps the conservative peer comparison active",
            )

    async def test_stm32_cube_mx_pin_map_parity(self) -> None:
        """Compare one valid pin map and one firmware pin drift through CLI and MCP."""
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"
        netlist.write_text(
            "<export><components>"
            '<comp ref="U1"><value>STM32F103C8T6</value>'
            "<footprint>Synthetic:LQFP-48</footprint>"
            '<libsource lib="Synthetic" part="STM32F103"/></comp>'
            '</components><libparts><libpart lib="Synthetic" part="STM32F103"><pins>'
            '<pin num="1" name="PA0" type="bidirectional"/>'
            '<pin num="2" name="PB6" type="bidirectional"/>'
            '<pin num="3" name="PB7" type="bidirectional"/>'
            '<pin num="34" name="PA13" type="bidirectional"/>'
            "</pins></libpart></libparts><nets>"
            '<net name="USER_BUTTON"><node ref="U1" pin="1"/></net>'
            '<net name="I2C_SCL"><node ref="U1" pin="2"/></net>'
            '<net name="I2C_SDA"><node ref="U1" pin="3"/></net>'
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

        ioc_path = self.root / "firmware/controller.ioc"
        ioc_path.parent.mkdir(parents=True)
        ioc_path.write_bytes(
            (Path(__file__).parent / "fixtures/design_lint/stm32-pin-map/valid.ioc").read_bytes()
        )
        pin_map = Stm32CubeMxPinMap(
            id="main-mcu",
            basis="Synthetic reviewed STM32F103 package pin table",
            reference="U1",
            expected_symbol="Synthetic:STM32F103",
            expected_part="STM32F103C8T6",
            ioc_path="firmware/controller.ioc",
            package_pins=("PA0", "PB6", "PB7", "PA13"),
            pins=(
                Stm32PinRequirement(
                    port_pin="PA0",
                    symbol_pin="1",
                    expected_net="USER_BUTTON",
                    accepted_ioc_signals=("GPIO_Input",),
                    accepted_ioc_gpio_labels=("BUTTON",),
                ),
                Stm32PinRequirement(
                    port_pin="PB6",
                    symbol_pin="2",
                    expected_net="I2C_SCL",
                    accepted_ioc_signals=("I2C1_SCL",),
                    accepted_ioc_gpio_labels=("SCL",),
                ),
                Stm32PinRequirement(
                    port_pin="PB7",
                    symbol_pin="3",
                    expected_net="I2C_SDA",
                    accepted_ioc_signals=("I2C1_SDA",),
                    accepted_ioc_gpio_labels=("SDA",),
                ),
            ),
            exclusions=(
                Stm32PinExclusion(
                    port_pin="PA13", reason="Reserved for the synthetic SWD debug interface"
                ),
            ),
        )
        contract_path = self.island / "tests/contract.json"
        contract = read_model(contract_path, ProjectTestContract)
        write_model(
            contract_path,
            contract.model_copy(
                update={"design_lint": DesignLintPolicy(stm32_pin_maps=(pin_map,))}
            ),
        )

        async with Client(create_server(self.root), mode="legacy") as client:

            async def compare() -> DesignLintReport:
                process = await self.cli_process(
                    "kicad_tooling.design_lint",
                    "--project",
                    "controller",
                    "--native-summary",
                    str(native),
                )
                cli = parse_model_text(process.stdout, DesignLintReport)
                self.assertEqual(
                    process.returncode, 0 if cli.status == "PASS" else 1, process.stderr
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

            valid = await compare()
            self.assertEqual(valid.stm32_pin_map_coverage.status, "COMPLETE")
            self.assertEqual(valid.stm32_pin_map_coverage.mismatches, ())
            self.assertEqual(valid.source_hashes["firmware/controller.ioc"], digest(ioc_path))

            ioc_path.write_text(
                ioc_path.read_text(encoding="utf-8").replace(
                    "PA0.Signal=GPIO_Input", "PA0.Signal=GPIO_Output"
                ),
                encoding="utf-8",
            )
            drifted = await compare()
            mismatch = drifted.stm32_pin_map_coverage.mismatches[0]
            self.assertEqual(mismatch.port_pin, "PA0")
            self.assertNotEqual(valid.source_hashes["firmware/controller.ioc"], mismatch.ioc_sha256)
            finding = next(
                item for item in drifted.findings if item.rule_id == "mcu.stm32_cubemx_pin_map"
            )
            self.assertEqual(finding.evidence["ioc_sha256"], (mismatch.ioc_sha256,))

    async def test_pcb_differential_pair_rule_coverage_parity(self) -> None:
        native = self.native_evidence()
        config = load_config(self.root, self.island / "project.json")
        board = self.root / config.project.replace(".kicad_pro", ".kicad_pcb")
        rules = self.root / config.project.replace(".kicad_pro", ".kicad_dru")
        contract_path = self.island / "tests/contract.json"
        contract = read_model(contract_path, ProjectTestContract)
        write_model(
            contract_path,
            contract.model_copy(
                update={
                    "design_lint": DesignLintPolicy(
                        pcb_differential_pair_rule_map=synthetic_differential_pair_map()
                    )
                }
            ),
        )
        board.write_text("(kicad_pcb (version 20250114))", encoding="utf-8")
        (native.parent / "netlist.xml").write_text(
            "<export><components>"
            '<comp ref="R1"><value>1k</value><footprint>Synthetic:R</footprint>'
            '<libsource lib="Device" part="R"/></comp>'
            "</components><nets>"
            '<net name="USB_D_P"/><net name="USB_D_N"/>'
            "</nets></export>",
            encoding="utf-8",
        )

        def refresh_receipt(ignored: tuple[str, ...] = ()) -> None:
            current = hashes(self.root, config.source_roots)
            drc_path = native.parent / "drc.json"
            drc_path.write_text(
                json.dumps(
                    {
                        "kicad_version": config.kicad_version,
                        "source": board.name,
                        "ignored_checks": [{"key": key} for key in ignored],
                        "violations": [],
                        "unconnected_items": [],
                    },
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            write_model(
                native.parent / "drc.command.json",
                native_fixture.command().model_copy(
                    update={
                        "argv": (
                            "synthetic-kicad-cli",
                            "pcb",
                            "drc",
                            "--format",
                            "json",
                            "--severity-all",
                            "--exit-code-violations",
                            "--output",
                            str(drc_path),
                            str(board),
                        )
                    }
                ),
            )
            summary = read_model(native, ValidationSummary)
            checks = dict(summary.checks)
            checks["source_scope"] = CheckEvidence(status="PASS", source_hashes=current)
            checks["source_unchanged"] = CheckEvidence(status="PASS", source_hashes=current)
            checks["drc"] = CheckEvidence(status="PASS", returncode=0)
            artifacts = {
                **summary.artifacts_sha256,
                "netlist.xml": digest(native.parent / "netlist.xml"),
                "netlist.command.json": digest(native.parent / "netlist.command.json"),
                "drc.json": digest(drc_path),
                "drc.command.json": digest(native.parent / "drc.command.json"),
            }
            write_model(
                native,
                summary.model_copy(
                    update={
                        "checks": checks,
                        "artifacts_sha256": artifacts,
                    }
                ),
            )

        async with Client(create_server(self.root), mode="legacy") as client:
            for scenario, expected, ignored, mode in (
                ("exact", "COMPLETE", (), "review"),
                ("missing", "INCOMPLETE", (), "review"),
                ("ignored", "INCOMPLETE", ("skew_out_of_range",), "review"),
                ("disabled", "DISABLED", (), "off"),
            ):
                with self.subTest(scenario=scenario):
                    if scenario == "missing":
                        rules.unlink(missing_ok=True)
                    else:
                        rules.write_text(synthetic_differential_pair_rules(), encoding="utf-8")
                    manifest_path = self.island / "project.json"
                    manifest = read_model(manifest_path, ProjectManifest)
                    required_inputs = set(manifest.required_inputs)
                    rules_relative = rules.relative_to(self.island).as_posix()
                    if rules.exists():
                        required_inputs.add(rules_relative)
                    else:
                        required_inputs.discard(rules_relative)
                    write_model(
                        manifest_path,
                        manifest.model_copy(
                            update={"required_inputs": tuple(sorted(required_inputs))}
                        ),
                    )
                    current_contract = read_model(contract_path, ProjectTestContract)
                    write_model(
                        contract_path,
                        current_contract.model_copy(
                            update={
                                "design_lint": DesignLintPolicy(
                                    pcb_differential_pair_rule_map=synthetic_differential_pair_map(),
                                    rules=(
                                        DesignLintRuleOverride(
                                            rule_id="pcb.differential_pair_rule_coverage",
                                            mode="off",
                                            reason="Synthetic parity case explicitly disables this audit",
                                        ),
                                    )
                                    if mode == "off"
                                    else (),
                                )
                            }
                        ),
                    )
                    refresh_receipt(ignored)
                    process = await self.cli_process(
                        "kicad_tooling.design_lint",
                        "--project",
                        "controller",
                        "--native-summary",
                        str(native),
                    )
                    self.assertIn(process.returncode, {0, 1}, process.stderr + process.stdout)
                    cli_report = parse_model_text(process.stdout, DesignLintReport)
                    mcp_report = await self.call(
                        client,
                        "inspect_design_lint",
                        DesignLintReport,
                        {
                            "project_id": "controller",
                            "native_summary": native.relative_to(self.root).as_posix(),
                        },
                    )
                    self.assertEqual(cli_report, mcp_report)
                    coverage = mcp_report.pcb_differential_pair_rules
                    self.assertEqual(coverage.status, expected, (coverage.issue, mcp_report.issues))
                    self.assertEqual(process.returncode, 0 if mcp_report.status == "PASS" else 1)
                    if scenario == "ignored":
                        pair = coverage.entries[0]
                        skew = next(item for item in pair.constraints if item.constraint == "skew")
                        self.assertEqual(skew.status, "IGNORED")
                    if scenario == "disabled":
                        self.assertIsNotNone(coverage.map_sha256)
                    else:
                        self.assertIsNotNone(coverage.native_drc_sha256)

    async def test_regulator_feedback_map_parity(self) -> None:
        """Compare the authored regulator-divider result through CLI and MCP."""
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"

        def write_netlist(*, upper_value: str) -> None:
            netlist.write_text(
                "<export><components>"
                '<comp ref="U1"><value>SYNTH-ADJ</value>'
                "<footprint>Synthetic:SOIC-8</footprint>"
                '<libsource lib="Synthetic" part="AdjustableRegulator"/></comp>'
                f'<comp ref="R1"><value>{upper_value}</value>'
                "<footprint>Synthetic:0603</footprint>"
                '<libsource lib="Device" part="R"/></comp>'
                '<comp ref="R2"><value>33k</value>'
                "<footprint>Synthetic:0603</footprint>"
                '<libsource lib="Device" part="R"/></comp>'
                "</components><libparts>"
                '<libpart lib="Synthetic" part="AdjustableRegulator"><pins>'
                '<pin num="1" name="OUT" type="passive"/>'
                '<pin num="2" name="FB" type="input"/>'
                '<pin num="3" name="VIN" type="power_in"/>'
                '<pin num="4" name="GND" type="power_in"/>'
                "</pins></libpart>"
                '<libpart lib="Device" part="R"><pins>'
                '<pin num="1" name="1" type="passive"/>'
                '<pin num="2" name="2" type="passive"/>'
                "</pins></libpart></libparts><nets>"
                '<net name="REG_OUT"><node ref="U1" pin="1"/>'
                '<node ref="R1" pin="1"/></net>'
                '<net name="FB"><node ref="U1" pin="2"/>'
                '<node ref="R1" pin="2"/><node ref="R2" pin="1"/></net>'
                '<net name="GND"><node ref="R2" pin="2"/>'
                '<node ref="U1" pin="4"/></net>'
                '<net name="VIN"><node ref="U1" pin="3"/></net>'
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

        write_netlist(upper_value="220k")
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
                        basis="Synthetic source has no external connector interfaces"
                    ),
                }
            ),
        )
        contract_path = self.island / "tests/contract.json"
        contract = read_model(contract_path, ProjectTestContract)
        policy = DesignLintPolicy(regulator_feedback_map=synthetic_regulator_feedback_map())
        write_model(contract_path, contract.model_copy(update={"design_lint": policy}))

        async with Client(create_server(self.root), mode="legacy") as client:

            async def compare(expected_status: str, exit_code: int) -> DesignLintReport:
                cli = await self.cli(
                    "kicad_tooling.design_lint",
                    DesignLintReport,
                    "--project",
                    "controller",
                    "--native-summary",
                    str(native),
                    expected_exit=exit_code,
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
                self.assertEqual(mcp.status, expected_status, mcp.issues)
                return mcp

            out_of_range = await compare("REVIEW", 1)
            entry = out_of_range.regulator_feedback_coverage.entries[0]
            self.assertEqual(entry.status, "OUT_OF_RANGE")
            self.assertEqual(entry.nominal_resistance_ohms["R1"], 220000.0)
            self.assertIn(
                "formula",
                next(
                    item.evidence
                    for item in out_of_range.findings
                    if item.rule_id == "power.regulator_feedback_mismatch"
                ),
            )

            blocking_policy = policy.model_copy(
                update={
                    "rules": (
                        DesignLintRuleOverride(
                            rule_id="power.regulator_feedback_mismatch",
                            mode="block",
                            reason="Synthetic output range is a reviewed requirement",
                        ),
                    )
                }
            )
            write_model(contract_path, contract.model_copy(update={"design_lint": blocking_policy}))
            blocked = await compare("FAIL", 1)
            self.assertEqual(
                next(
                    item
                    for item in blocked.findings
                    if item.rule_id == "power.regulator_feedback_mismatch"
                ).mode,
                "block",
            )

    async def test_rc_filter_map_parity(self) -> None:
        """Compare an authored RC filter and a source value mutation through CLI and MCP."""
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"

        def write_netlist(*, capacitor_value: str) -> None:
            netlist.write_text(
                "<export><components>"
                '<comp ref="R1"><value>1k</value>'
                "<footprint>Synthetic:0603</footprint>"
                '<libsource lib="Device" part="R"/></comp>'
                f'<comp ref="C1"><value>{capacitor_value}</value>'
                "<footprint>Synthetic:0603</footprint>"
                '<libsource lib="Device" part="C"/></comp>'
                "</components><libparts>"
                '<libpart lib="Device" part="R"><pins>'
                '<pin num="1" name="1" type="passive"/>'
                '<pin num="2" name="2" type="passive"/>'
                "</pins></libpart>"
                '<libpart lib="Device" part="C"><pins>'
                '<pin num="1" name="1" type="passive"/>'
                '<pin num="2" name="2" type="passive"/>'
                "</pins></libpart></libparts><nets>"
                '<net name="FILTER_IN"><node ref="R1" pin="1"/></net>'
                '<net name="FILTER_OUT"><node ref="R1" pin="2"/>'
                '<node ref="C1" pin="1"/></net>'
                '<net name="GND"><node ref="C1" pin="2"/></net>'
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

        write_netlist(capacitor_value="100nF")
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
                        basis="Synthetic source has no external connector interfaces"
                    ),
                }
            ),
        )
        contract_path = self.island / "tests/contract.json"
        contract = read_model(contract_path, ProjectTestContract)
        policy = DesignLintPolicy(rc_filter_map=synthetic_rc_filter_map())
        write_model(contract_path, contract.model_copy(update={"design_lint": policy}))

        async with Client(create_server(self.root), mode="legacy") as client:

            async def compare(expected_status: str, exit_code: int) -> DesignLintReport:
                cli = await self.cli(
                    "kicad_tooling.design_lint",
                    DesignLintReport,
                    "--project",
                    "controller",
                    "--native-summary",
                    str(native),
                    expected_exit=exit_code,
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
                self.assertEqual(mcp.status, expected_status, mcp.issues)
                return mcp

            complete = await compare("PASS", 0)
            self.assertEqual(complete.rc_filter_coverage.entries[0].status, "COMPLETE")
            self.assertAlmostEqual(
                complete.rc_filter_coverage.entries[0].calculated_corner_hz or 0,
                1591.55,
                delta=0.02,
            )

            write_netlist(capacitor_value="220nF")
            changed = await compare("REVIEW", 1)
            self.assertEqual(changed.rc_filter_coverage.entries[0].status, "OUT_OF_RANGE")
            self.assertTrue(
                any(item.rule_id == "filter.rc_corner_mismatch" for item in changed.findings)
            )

    async def test_usb_data_path_map_parity(self) -> None:
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

    async def test_power_path_map_parity(self) -> None:
        """Compare a required ferrite path fault through the CLI and MCP adapters."""
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"

        def write_netlist(*, open_ferrite: bool) -> None:
            if open_ferrite:
                downstream_nets = (
                    '<net name="VLOAD"><node ref="U1" pin="3"/></net>'
                    '<net name="FLOATING"><node ref="FB1" pin="2"/></net>'
                )
            else:
                downstream_nets = (
                    '<net name="VLOAD"><node ref="FB1" pin="2"/><node ref="U1" pin="3"/></net>'
                )
            netlist.write_text(
                "<export><components>"
                '<comp ref="J1"><value>Synthetic source</value>'
                "<footprint>Synthetic:Conn2</footprint>"
                '<libsource lib="Synthetic" part="PowerInput"/></comp>'
                '<comp ref="FB1"><value>Ferrite bead</value>'
                "<footprint>Synthetic:0603</footprint>"
                '<libsource lib="Device" part="FerriteBead"/></comp>'
                '<comp ref="U1"><value>Synthetic controller</value>'
                "<footprint>Synthetic:QFN</footprint>"
                '<libsource lib="Synthetic" part="Controller"/></comp>'
                "</components><libparts>"
                '<libpart lib="Synthetic" part="PowerInput"><pins>'
                '<pin num="1" name="1" type="passive"/>'
                '<pin num="2" name="2" type="passive"/>'
                "</pins></libpart>"
                '<libpart lib="Device" part="FerriteBead"><pins>'
                '<pin num="1" name="1" type="passive"/>'
                '<pin num="2" name="2" type="passive"/>'
                "</pins></libpart>"
                '<libpart lib="Synthetic" part="Controller"><pins>'
                '<pin num="1" name="1" type="passive"/>'
                '<pin num="2" name="2" type="passive"/>'
                '<pin num="3" name="VDD" type="passive"/>'
                "</pins></libpart></libparts><nets>"
                '<net name="VIN"><node ref="J1" pin="1"/>'
                '<node ref="FB1" pin="1"/></net>'
                f"{downstream_nets}"
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
                    "connector_reviews": (
                        ConnectorInterfaceReview(
                            reference="J1",
                            disposition="not_applicable",
                            basis="Synthetic parity case checks only the mapped power topology",
                        ),
                    ),
                    "connector_inventory_review": ConnectorInventoryReview(
                        basis="Synthetic parity fixture reviewed its power input interface"
                    ),
                }
            ),
        )
        contract_path = self.island / "tests/contract.json"
        contract = read_model(contract_path, ProjectTestContract)
        write_model(
            contract_path,
            contract.model_copy(
                update={"design_lint": DesignLintPolicy(power_path_map=synthetic_power_path_map())}
            ),
        )

        async with Client(create_server(self.root), mode="legacy") as client:

            async def compare(*, fault: bool) -> DesignLintReport:
                write_netlist(open_ferrite=fault)
                exit_code = 1 if fault else 0
                cli = await self.cli(
                    "kicad_tooling.design_lint",
                    DesignLintReport,
                    "--project",
                    "controller",
                    "--native-summary",
                    str(native),
                    expected_exit=exit_code,
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

            control = await compare(fault=False)
            self.assertEqual(control.status, "PASS", control.issues)
            self.assertNotIn(POWER_PATH_RULE_ID, {item.rule_id for item in control.findings})

            fault = await compare(fault=True)
            self.assertEqual(fault.status, "REVIEW", fault.issues)
            finding = next(item for item in fault.findings if item.rule_id == POWER_PATH_RULE_ID)
            self.assertEqual(finding.subject, "input-to-controller: required power path differs")

    async def test_power_sequence_map_parity(self) -> None:
        """Compare a mapped sequence fault through native XML, CLI, and MCP."""
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"

        def write_netlist(*, open_enable: bool) -> None:
            if open_enable:
                control_nets = (
                    '<net name="GOOD_A"><node ref="U1" pin="3"/></net>'
                    '<net name="FLOATING"><node ref="U2" pin="1"/></net>'
                )
            else:
                control_nets = (
                    '<net name="GOOD_A"><node ref="U1" pin="3"/><node ref="U2" pin="1"/></net>'
                )
            netlist.write_text(
                "<export><components>"
                '<comp ref="U1"><value>Synthetic regulator A</value>'
                "<footprint>Synthetic:SOT23-5</footprint><fields>"
                '<field name="PART_ID">SYNTH-REG-A</field></fields>'
                '<libsource lib="Synthetic" part="Regulator"/></comp>'
                '<comp ref="U2"><value>Synthetic regulator B</value>'
                "<footprint>Synthetic:SOT23-5</footprint><fields>"
                '<field name="PART_ID">SYNTH-REG-B</field></fields>'
                '<libsource lib="Synthetic" part="Regulator"/></comp>'
                "</components><libparts>"
                '<libpart lib="Synthetic" part="Regulator"><pins>'
                '<pin num="1" name="P1" type="passive"/>'
                '<pin num="2" name="P2" type="passive"/>'
                '<pin num="3" name="P3" type="passive"/>'
                "</pins></libpart></libparts><nets>"
                '<net name="CONTROL_ON"><node ref="U1" pin="1"/></net>'
                '<net name="RAIL_A"><node ref="U1" pin="2"/></net>'
                f"{control_nets}"
                '<net name="RAIL_B"><node ref="U2" pin="2"/></net>'
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

        contract_path = self.island / "tests/contract.json"
        contract = read_model(contract_path, ProjectTestContract)
        write_model(
            contract_path,
            contract.model_copy(
                update={
                    "design_lint": DesignLintPolicy(
                        power_sequence_map=synthetic_power_sequence_map()
                    )
                }
            ),
        )

        async with Client(create_server(self.root), mode="legacy") as client:
            for open_enable in (False, True):
                with self.subTest(open_enable=open_enable):
                    write_netlist(open_enable=open_enable)
                    cli = await self.cli(
                        "kicad_tooling.design_lint",
                        DesignLintReport,
                        "--project",
                        "controller",
                        "--native-summary",
                        str(native),
                        expected_exit=int(open_enable),
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
                    findings = [
                        item for item in mcp.findings if item.rule_id == POWER_SEQUENCE_RULE_ID
                    ]
                    self.assertEqual(len(findings), int(open_enable))
                    self.assertEqual(mcp.status, "REVIEW" if open_enable else "PASS")
                    if open_enable:
                        self.assertEqual(
                            findings[0].subject,
                            "rail-b: required power-sequence stage differs",
                        )

    async def test_mapped_output_to_enable_cycle_parity(self) -> None:
        """Compare an inferred mapped-endpoint cycle through CLI and MCP."""
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"
        contract_path = self.island / "tests/contract.json"

        def write_case(*, cycle: bool) -> None:
            observed = synthetic_power_sequence_output_cycle_netlist(cycle=cycle)
            root = ET.Element("export")
            component_container = ET.SubElement(root, "components")
            for reference, component in observed.components.items():
                comp = ET.SubElement(component_container, "comp", ref=reference)
                ET.SubElement(comp, "value").text = component.value
                ET.SubElement(comp, "footprint").text = component.footprint
                fields = ET.SubElement(comp, "fields")
                ET.SubElement(fields, "field", name="PART_ID").text = component.part_id
                ET.SubElement(comp, "libsource", lib="Synthetic", part="Regulator")
            libparts = ET.SubElement(root, "libparts")
            libpart = ET.SubElement(libparts, "libpart", lib="Synthetic", part="Regulator")
            pins = ET.SubElement(libpart, "pins")
            for number, name in (("1", "EN"), ("2", "OUT"), ("3", "PG")):
                ET.SubElement(pins, "pin", num=number, name=name, type="passive")
            nets = ET.SubElement(root, "nets")
            for net_name, net_pins in sorted(observed.nets.items()):
                if not net_pins:
                    continue
                net = ET.SubElement(nets, "net", name=net_name)
                for pin in net_pins:
                    reference, number = pin.split(".", maxsplit=1)
                    ET.SubElement(net, "node", ref=reference, pin=number)
            netlist.write_bytes(ET.tostring(root, encoding="utf-8"))
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
            contract = read_model(contract_path, ProjectTestContract)
            write_model(
                contract_path,
                contract.model_copy(
                    update={
                        "design_lint": DesignLintPolicy(
                            power_sequence_map=synthetic_power_sequence_output_cycle_map(
                                cycle=cycle
                            )
                        )
                    }
                ),
            )

        async with Client(create_server(self.root), mode="legacy") as client:
            for cycle in (False, True):
                with self.subTest(cycle=cycle):
                    write_case(cycle=cycle)
                    cli = await self.cli(
                        "kicad_tooling.design_lint",
                        DesignLintReport,
                        "--project",
                        "controller",
                        "--native-summary",
                        str(native),
                        expected_exit=int(cycle),
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
                    findings = [
                        item for item in mcp.findings if item.rule_id == POWER_SEQUENCE_RULE_ID
                    ]
                    self.assertEqual(len(findings), int(cycle))
                    self.assertEqual(mcp.status, "REVIEW" if cycle else "PASS")
                    if cycle:
                        self.assertEqual(
                            findings[0].evidence["observed_output_to_enable_cycle_stages"],
                            ("rail-a, rail-b",),
                        )

    async def test_power_input_source_path_heuristic_cli_mcp_parity(self) -> None:
        """Compare source-path controls and faults through both public surfaces."""
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"

        def write_netlist(
            *,
            wrong_rail: bool,
            unrecognized_source: bool = False,
            jumper_symbol: str | None = None,
            jumper_pin_numbers: tuple[str, ...] = ("1", "2"),
            jumper_pin_functions: tuple[str, ...] = ("A", "B"),
            jumper_source_pin: str = "1",
            jumper_load_pin: str = "2",
        ) -> None:
            path_reference = "JP1" if jumper_symbol else "FB1"
            if jumper_symbol:
                input_side = '<net name="GND"><node ref="C1" pin="2"/></net>'
                source_side = (
                    f'<net name="VIN"><node ref="U1" pin="1"/>'
                    f'<node ref="JP1" pin="{jumper_source_pin}"/></net>'
                )
                source_pin_type = "power_out"
                load_pin = jumper_load_pin
                unused_pin_nets = "".join(
                    f'<net name="JP_UNUSED_{number}"><node ref="JP1" pin="{number}"/></net>'
                    for number in jumper_pin_numbers
                    if number not in {jumper_source_pin, jumper_load_pin}
                )
            elif unrecognized_source:
                input_side = '<net name="GND"><node ref="C1" pin="2"/></net>'
                source_side = (
                    f'<net name="AUX_INPUT"><node ref="U1" pin="1"/>'
                    f'<node ref="{path_reference}" pin="1"/></net>'
                )
                source_pin_type = "passive"
                load_pin = "2"
                unused_pin_nets = ""
            elif wrong_rail:
                input_side = f'<net name="GND"><node ref="{path_reference}" pin="1"/>'
                input_side += '<node ref="C1" pin="2"/></net>'
                source_side = '<net name="VIN"><node ref="U1" pin="1"/></net>'
                source_pin_type = "power_out"
                load_pin = "2"
                unused_pin_nets = ""
            else:
                input_side = '<net name="GND"><node ref="C1" pin="2"/></net>'
                source_side = (
                    f'<net name="VIN"><node ref="U1" pin="1"/>'
                    f'<node ref="{path_reference}" pin="1"/></net>'
                )
                source_pin_type = "power_out"
                load_pin = "2"
                unused_pin_nets = ""
            path_component = (
                f'<comp ref="JP1"><value>Synthetic jumper</value>'
                "<footprint>Synthetic:0603</footprint>"
                f'<libsource lib="Jumper" part="{jumper_symbol}"/></comp>'
                if jumper_symbol
                else '<comp ref="FB1"><value>Ferrite bead</value>'
                "<footprint>Synthetic:0603</footprint>"
                '<libsource lib="Device" part="FerriteBead"/></comp>'
            )
            if jumper_symbol:
                path_libpart = (
                    f'<libpart lib="Jumper" part="{jumper_symbol}"><pins>'
                    + "".join(
                        f'<pin num="{number}" name="{function}" type="passive"/>'
                        for number, function in zip(jumper_pin_numbers, jumper_pin_functions)
                    )
                    + "</pins></libpart>"
                )
            else:
                path_libpart = (
                    '<libpart lib="Device" part="FerriteBead"><pins>'
                    '<pin num="1" name="1" type="passive"/>'
                    '<pin num="2" name="2" type="passive"/>'
                    "</pins></libpart>"
                )
            netlist.write_text(
                "<export><components>"
                '<comp ref="U1"><value>Synthetic source</value>'
                "<footprint>Synthetic:PowerSource</footprint>"
                '<libsource lib="Synthetic" part="PowerSource"/></comp>'
                f"{path_component}"
                '<comp ref="U2"><value>Synthetic load</value>'
                "<footprint>Synthetic:PowerLoad</footprint>"
                '<libsource lib="Synthetic" part="PowerLoad"/></comp>'
                '<comp ref="C1"><value>100nF</value>'
                "<footprint>Synthetic:0603</footprint>"
                '<libsource lib="Device" part="C"/></comp>'
                "</components><libparts>"
                '<libpart lib="Synthetic" part="PowerSource"><pins>'
                f'<pin num="1" name="VOUT" type="{source_pin_type}"/>'
                "</pins></libpart>"
                f"{path_libpart}"
                '<libpart lib="Synthetic" part="PowerLoad"><pins>'
                '<pin num="1" name="VIN" type="power_in"/>'
                "</pins></libpart>"
                '<libpart lib="Device" part="C"><pins>'
                '<pin num="1" name="1" type="passive"/>'
                '<pin num="2" name="2" type="passive"/>'
                "</pins></libpart></libparts><nets>"
                f"{source_side}"
                f'<net name="VLOAD"><node ref="{path_reference}" pin="{load_pin}"/>'
                '<node ref="U2" pin="1"/><node ref="C1" pin="1"/></net>'
                f"{input_side}{unused_pin_nets}</nets></export>",
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
                        basis="Synthetic parity case has no external connector in its fixture"
                    ),
                }
            ),
        )
        contract_path = self.island / "tests/contract.json"
        contract = read_model(contract_path, ProjectTestContract)
        write_model(
            contract_path,
            contract.model_copy(update={"design_lint": DesignLintPolicy()}),
        )

        async with Client(create_server(self.root), mode="legacy") as client:

            async def compare(
                *,
                wrong_rail: bool = False,
                unrecognized_source: bool = False,
                jumper_symbol: str | None = None,
                jumper_pin_numbers: tuple[str, ...] = ("1", "2"),
                jumper_pin_functions: tuple[str, ...] = ("A", "B"),
                jumper_source_pin: str = "1",
                jumper_load_pin: str = "2",
            ) -> DesignLintReport:
                write_netlist(
                    wrong_rail=wrong_rail,
                    unrecognized_source=unrecognized_source,
                    jumper_symbol=jumper_symbol,
                    jumper_pin_numbers=jumper_pin_numbers,
                    jumper_pin_functions=jumper_pin_functions,
                    jumper_source_pin=jumper_source_pin,
                    jumper_load_pin=jumper_load_pin,
                )
                exit_code = int(
                    wrong_rail
                    or unrecognized_source
                    or jumper_symbol == "SolderJumper_2_Open"
                    or (jumper_symbol == "SolderJumper_3_Bridged12" and jumper_load_pin == "3")
                )
                cli = await self.cli(
                    "kicad_tooling.design_lint",
                    DesignLintReport,
                    "--project",
                    "controller",
                    "--native-summary",
                    str(native),
                    expected_exit=exit_code,
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

            control = await compare(wrong_rail=False)
            self.assertEqual(control.status, "PASS", control.issues)
            self.assertNotIn(
                POWER_INPUT_SOURCE_PATH_RULE_ID,
                {item.rule_id for item in control.findings},
            )

            fault = await compare(wrong_rail=True)
            self.assertEqual(fault.status, "REVIEW", fault.issues)
            finding = next(
                item for item in fault.findings if item.rule_id == POWER_INPUT_SOURCE_PATH_RULE_ID
            )
            self.assertEqual(finding.subject, "VLOAD: power-input source-path review")

            unknown_source = await compare(unrecognized_source=True)
            self.assertEqual(unknown_source.status, "REVIEW", unknown_source.issues)
            unknown_finding = next(
                item
                for item in unknown_source.findings
                if item.rule_id == POWER_INPUT_SOURCE_PATH_RULE_ID
            )
            self.assertEqual(unknown_finding.evidence["recognized_source_nets"], ())
            self.assertEqual(unknown_finding.evidence["source_anchor_state"], ("not_recognized",))

            bridged_jumper = await compare(jumper_symbol="SolderJumper_2_Bridged")
            self.assertEqual(bridged_jumper.status, "PASS", bridged_jumper.issues)
            self.assertNotIn(
                POWER_INPUT_SOURCE_PATH_RULE_ID,
                {item.rule_id for item in bridged_jumper.findings},
            )

            open_jumper = await compare(jumper_symbol="SolderJumper_2_Open")
            self.assertEqual(open_jumper.status, "REVIEW", open_jumper.issues)
            open_finding = next(
                item
                for item in open_jumper.findings
                if item.rule_id == POWER_INPUT_SOURCE_PATH_RULE_ID
            )
            self.assertEqual(open_finding.subject, "VLOAD: power-input source-path review")

            bridged_three_pin12 = await compare(
                jumper_symbol="SolderJumper_3_Bridged12",
                jumper_pin_numbers=("1", "2", "3"),
                jumper_pin_functions=("A", "C", "B"),
                jumper_source_pin="1",
                jumper_load_pin="2",
            )
            self.assertEqual(bridged_three_pin12.status, "PASS", bridged_three_pin12.issues)
            self.assertNotIn(
                POWER_INPUT_SOURCE_PATH_RULE_ID,
                {item.rule_id for item in bridged_three_pin12.findings},
            )

            bridged_three_pin123 = await compare(
                jumper_symbol="SolderJumper_3_Bridged123",
                jumper_pin_numbers=("1", "2", "3"),
                jumper_pin_functions=("A", "C", "B"),
                jumper_source_pin="1",
                jumper_load_pin="3",
            )
            self.assertEqual(bridged_three_pin123.status, "PASS", bridged_three_pin123.issues)
            self.assertNotIn(
                POWER_INPUT_SOURCE_PATH_RULE_ID,
                {item.rule_id for item in bridged_three_pin123.findings},
            )

            unbridged_terminal = await compare(
                jumper_symbol="SolderJumper_3_Bridged12",
                jumper_pin_numbers=("1", "2", "3"),
                jumper_pin_functions=("A", "C", "B"),
                jumper_source_pin="1",
                jumper_load_pin="3",
            )
            self.assertEqual(unbridged_terminal.status, "REVIEW", unbridged_terminal.issues)
            unbridged_finding = next(
                item
                for item in unbridged_terminal.findings
                if item.rule_id == POWER_INPUT_SOURCE_PATH_RULE_ID
            )
            self.assertEqual(unbridged_finding.subject, "VLOAD: power-input source-path review")

    async def test_pcb_decoupling_track_width_and_switching_loop_map_parity(self) -> None:
        """Compare source-bound PCB geometry maps through both adapters."""
        fixture = (
            Path(__file__).parents[1]
            / "kicad_tooling/hwrepo/fixtures/pcb-decoupling-placement.kicad_pcb"
        )
        board_path = self.island / "kicad/controller.kicad_pcb"
        shutil.copyfile(fixture, board_path)
        native = self.native_evidence()
        requirement = PcbDecouplingRequirement(
            id="synthetic-core-rail",
            basis="Synthetic pin map and placement threshold",
            ic_reference="U1",
            ic_footprint="Synthetic:IC_QFN",
            supply_pad="U1.1",
            return_pad="U1.2",
            supply_net="VDD",
            return_net="GND",
            capacitors=(
                PcbDecouplingCapacitor(
                    reference="C1",
                    footprint="Synthetic:Cap_0603",
                    supply_pad="C1.1",
                    return_pad="C1.2",
                ),
            ),
            selection="any",
            max_distance_um=1000,
            max_return_via_distance_um=1000,
        )
        policy = DesignLintPolicy(
            pcb_protection_path_map=PcbProtectionPathMap(
                basis="Synthetic mapped ESD entry pad and return-via coverage",
                requirements=(
                    PcbProtectionPathRequirement(
                        id="synthetic-usb-d-plus-protection",
                        connector_reference="J1",
                        connector_footprint="Synthetic:Conn1",
                        connector_signal_pad="J1.1",
                        protection_reference="D1",
                        protection_footprint="Synthetic:TVS",
                        protection_signal_pad="D1.1",
                        protection_reference_pad="D1.2",
                        signal_net="DATA",
                        reference_net="GND",
                        max_entry_distance_um=650,
                        minimum_reference_vias=1,
                        reference_via_radius_um=3000,
                    ),
                ),
            ),
            pcb_decoupling_map=PcbDecouplingMap(
                basis="Synthetic KiCad native report parity map",
                requirements=(requirement,),
            ),
            pcb_track_width_map=PcbTrackWidthMap(
                basis="Synthetic KiCad native width parity map",
                requirements=(
                    PcbTrackWidthRequirement(
                        id="synthetic-vdd-width",
                        basis="Synthetic 251 um screen against a 250 um track",
                        net="VDD",
                        minimum_width_um=251,
                    ),
                ),
            ),
            pcb_reference_plane_map=PcbReferencePlaneMap(
                basis="Synthetic adjacent-reference coverage parity map",
                requirements=(
                    PcbReferencePlaneRequirement(
                        id="synthetic-vdd-reference",
                        basis="Synthetic VDD route expected over adjacent GND copper",
                        signal_net="VDD",
                        signal_layers=("F.Cu",),
                        reference_net="GND",
                        minimum_track_length_um=500,
                        minimum_referenced_fraction=0.9,
                        review_excluded_short_tracks=True,
                    ),
                    PcbReferencePlaneRequirement(
                        id="synthetic-data-reference",
                        basis="Synthetic DATA route with a mapped endpoint-via clearance",
                        signal_net="DATA",
                        signal_layers=("F.Cu",),
                        reference_net="GND",
                        minimum_track_length_um=1,
                        minimum_referenced_fraction=0.9,
                    ),
                ),
            ),
            pcb_switching_loop_map=PcbSwitchingLoopMap(
                basis="Synthetic buck loop pad-center and return-plane mapping",
                requirements=(
                    PcbSwitchingLoopRequirement(
                        id="synthetic-buck-input-loop",
                        basis="Synthetic input-capacitor and switching-path mapping",
                        loop_pads=(
                            PcbSwitchingLoopPad(
                                pad="U1.1", footprint="Synthetic:IC_QFN", net="VDD"
                            ),
                            PcbSwitchingLoopPad(
                                pad="C1.1", footprint="Synthetic:Cap_0603", net="VDD"
                            ),
                            PcbSwitchingLoopPad(
                                pad="C1.2", footprint="Synthetic:Cap_0603", net="GND"
                            ),
                            PcbSwitchingLoopPad(
                                pad="U1.2", footprint="Synthetic:IC_QFN", net="GND"
                            ),
                        ),
                        return_net="GND",
                        return_plane_layer="B.Cu",
                        return_plane_pads=(
                            PcbSwitchingLoopPad(
                                pad="U1.2", footprint="Synthetic:IC_QFN", net="GND"
                            ),
                            PcbSwitchingLoopPad(
                                pad="C1.2", footprint="Synthetic:Cap_0603", net="GND"
                            ),
                        ),
                        maximum_area_um2=1000,
                        route_edges=(
                            PcbSwitchingLoopEdge(
                                from_pad="U1.1",
                                to_pad="C1.1",
                                kind="trace",
                                net="VDD",
                                layers=("F.Cu",),
                            ),
                            PcbSwitchingLoopEdge(
                                from_pad="C1.1",
                                to_pad="C1.2",
                                kind="component",
                                component_reference="C1",
                            ),
                            PcbSwitchingLoopEdge(
                                from_pad="C1.2",
                                to_pad="U1.2",
                                kind="plane",
                                net="GND",
                                plane_layer="B.Cu",
                            ),
                            PcbSwitchingLoopEdge(
                                from_pad="U1.2",
                                to_pad="U1.1",
                                kind="component",
                                component_reference="U1",
                            ),
                        ),
                    ),
                ),
            ),
        )
        contract_path = self.island / "tests/contract.json"
        contract = read_model(contract_path, ProjectTestContract)
        write_model(contract_path, contract.model_copy(update={"design_lint": policy}))

        shim = self.base / "docker-shim"
        shim.mkdir()
        docker = shim / "docker"
        docker.write_text(
            """#!/usr/bin/env python3
import hashlib
import json
import sys
from pathlib import Path

arguments = sys.argv[1:]
mounts = [arguments[index + 1] for index, item in enumerate(arguments[:-1]) if item == "-v"]
work_root = Path(next(item.split(":", 1)[0] for item in mounts if item.endswith(":/work:ro")))
output_root = Path(next(item.split(":", 1)[0] for item in mounts if item.endswith(":/output:rw")))
board = work_root / arguments[-2].removeprefix("/work/")
image = next(item for item in arguments if "@sha256:" in item)
version = image.split("@", 1)[0].rsplit(":", 1)[1]
rows = (
    ("J1.1", "DATA", "Synthetic:Conn1", ("J1.1", "D1.1"), (1850000, 2000000)),
    ("D1.1", "DATA", "Synthetic:TVS", ("J1.1", "D1.1"), (2500000, 2000000)),
    ("D1.2", "GND", "Synthetic:TVS", ("D1.2",), (2500000, 3000000)),
    ("U1.1", "VDD", "Synthetic:IC_QFN", ("U1.1", "C1.1"), (0, 0)),
    ("U1.2", "GND", "Synthetic:IC_QFN", ("U1.2", "C1.2"), (0, 1000)),
    ("C1.1", "VDD", "Synthetic:Cap_0603", ("U1.1", "C1.1"), (500000, 0)),
    ("C1.2", "GND", "Synthetic:Cap_0603", ("U1.2", "C1.2"), (500000, 1000)),
)
plane_uuid = "00000000-0000-0000-0000-0000000000a1"
return_via_id = "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
protection_via_id = "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd"
snapshot = {
    "schema_version": "10",
    "board_sha256": hashlib.sha256(board.read_bytes()).hexdigest(),
    "kicad_version": version,
    "zones_refilled": True,
    "pads": [
        {
            "pad": reference,
            "net": net,
            "footprint": footprint,
            "dnp": False,
            "connected_pads": list(connected),
            "connected_vias": ([return_via_id] if reference == "C1.2" else [protection_via_id] if reference == "D1.2" else []),
            "connected_zones": ([{"uuid": plane_uuid, "layer": "B.Cu"}] if reference in ("U1.2", "C1.2") else []),
            "connected_islands": ([{"uuid": plane_uuid, "layer": "B.Cu", "island_index": 0}] if reference in ("U1.2", "C1.2") else []),
            "positions_nm": [list(position)],
        }
        for reference, net, footprint, connected, position in rows
    ],
    "vias": [{
        "id": return_via_id,
        "net": "GND",
        "x_nm": 500000,
        "y_nm": 1000,
        "start_layer": "F.Cu",
        "end_layer": "B.Cu",
        "diameter_nm": 400000,
        "drill_nm": 200000,
        "kind": "through",
        "multiplicity": 1,
    }, {
        "id": "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
        "net": "DATA",
        "x_nm": 2000000,
        "y_nm": 2000000,
        "start_layer": "F.Cu",
        "end_layer": "B.Cu",
        "diameter_nm": 400000,
        "drill_nm": 200000,
        "kind": "through",
        "multiplicity": 1,
    }, {
        "id": protection_via_id,
        "net": "GND",
        "x_nm": 2500000,
        "y_nm": 3000000,
        "start_layer": "F.Cu",
        "end_layer": "B.Cu",
        "diameter_nm": 400000,
        "drill_nm": 200000,
        "kind": "through",
        "multiplicity": 1,
    }],
    "net_ties": [],
    "zones": [{
        "uuid": plane_uuid,
        "layer": "B.Cu",
        "name": "Synthetic GND return plane",
        "net": "GND",
        "filled_island_count": 1,
        "unanchored_pad_island_indexes": [],
        "filled_islands": [{
            "island_index": 0,
            "outline_nm": [[0, 0], [1000000, 0], [1000000, 1000000], [0, 1000000]],
            "holes_nm": [],
        }],
    }, {
        "uuid": "00000000-0000-0000-0000-0000000000a2",
        "layer": "In1.Cu",
        "name": "Synthetic GND antipad plane",
        "net": "GND",
        "filled_island_count": 1,
        "unanchored_pad_island_indexes": [0],
        "filled_islands": [{
            "island_index": 0,
            "outline_nm": [[1000000, 1000000], [4000000, 1000000], [4000000, 4000000], [1000000, 4000000]],
            "holes_nm": [[[2000000, 1750000], [2500000, 1750000], [2500000, 2250000], [2000000, 2250000]]],
        }],
    }],
    "access_probe_observations": [],
    "access_probe_requests_sha256": None,
    "tracks": [
        {
            "uuid": "00000000-0000-0000-0000-000000000101",
            "net": "VDD",
            "layer": "F.Cu",
            "width_nm": 250000,
            "start_nm": [0, 0],
            "end_nm": [500000, 0],
            "geometry_kind": "segment",
            "start_pads": ["U1.1"],
            "end_pads": ["C1.1"],
            "start_vias": [],
            "end_vias": [],
            "start_tracks": [],
            "end_tracks": [],
        },
        {
            "uuid": "00000000-0000-0000-0000-000000000102",
            "net": "GND",
            "layer": "F.Cu",
            "width_nm": 250000,
            "start_nm": [0, 1000],
            "end_nm": [500000, 1000],
            "geometry_kind": "segment",
            "start_pads": ["U1.2"],
            "end_pads": ["C1.2"],
            "start_vias": [],
            "end_vias": [],
            "start_tracks": [],
            "end_tracks": [],
        },
        {
            "uuid": "00000000-0000-0000-0000-000000000103",
            "net": "DATA",
            "layer": "F.Cu",
            "width_nm": 250000,
            "start_nm": [2000000, 2000000],
            "end_nm": [3000000, 2000000],
            "geometry_kind": "segment",
            "start_pads": [],
            "end_pads": [],
            "start_vias": ["ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"],
            "end_vias": [],
            "start_tracks": [],
            "end_tracks": [],
        },
        {
            "uuid": "00000000-0000-0000-0000-000000000104",
            "net": "VDD",
            "layer": "F.Cu",
            "width_nm": 250000,
            "start_nm": [0, 500000],
            "end_nm": [100000, 500000],
            "geometry_kind": "segment",
            "start_pads": [],
            "end_pads": [],
            "start_vias": [],
            "end_vias": [],
            "start_tracks": [],
            "end_tracks": [],
        },
        {
            "uuid": "00000000-0000-0000-0000-000000000105",
            "net": "GND",
            "layer": "F.Cu",
            "width_nm": 250000,
            "start_nm": [2500000, 3000000],
            "end_nm": [3000000, 3000000],
            "geometry_kind": "segment",
            "start_pads": ["D1.2"],
            "end_pads": [],
            "start_vias": [protection_via_id],
            "end_vias": [],
            "start_tracks": [],
            "end_tracks": [],
        },
    ],
    "copper_layers": ["F.Cu", "In1.Cu", "B.Cu"],
}
destination = output_root / arguments[-1].removeprefix("/output/")
destination.write_text(json.dumps(snapshot), encoding="utf-8")
""",
            encoding="utf-8",
        )
        docker.chmod(0o755)
        environment = os.environ.copy()
        environment["PATH"] = os.pathsep.join((str(shim), environment["PATH"]))
        config = load_config(self.root, self.island / "project.json")

        async with Client(create_server(self.root), mode="legacy") as client:
            with patch.dict(os.environ, {"PATH": environment["PATH"]}):
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
        cli_result = cli.model_dump(mode="json")
        mcp_result = mcp.model_dump(mode="json")
        for report in (cli_result, mcp_result):
            report["pcb_decoupling"]["snapshot_path"] = "<per-run native snapshot>"
            report["pcb_protection_path"]["snapshot_path"] = "<per-run native snapshot>"
            report["pcb_track_width"]["snapshot_path"] = "<per-run native snapshot>"
            report["pcb_reference_plane"]["snapshot_path"] = "<per-run native snapshot>"
            report["pcb_switching_loop"]["snapshot_path"] = "<per-run native snapshot>"

        self.assertEqual(cli_result, mcp_result)
        self.assertEqual(mcp.status, "REVIEW", mcp.issues)
        self.assertEqual(mcp.pcb_decoupling.status, "COMPLETE")
        self.assertEqual(mcp.pcb_protection_path.status, "COMPLETE")
        self.assertEqual(
            mcp.pcb_protection_path.entries[0].connector_to_protection_distance_nm,
            650_000,
        )
        self.assertEqual(mcp.pcb_protection_path.entries[0].reference_vias_within_radius, 1)
        self.assertEqual(mcp.pcb_decoupling.entries[0].selected_capacitors, ("C1",))
        self.assertEqual(mcp.pcb_decoupling.entries[0].candidates[0].distance_nm, 500_000)
        self.assertEqual(
            mcp.pcb_decoupling.entries[0].candidates[0].return_via_distance_nm,
            0,
        )
        self.assertEqual(
            mcp.pcb_decoupling.entries[0].candidates[0].nearest_return_via_id,
            "e" * 64,
        )
        self.assertEqual(mcp.pcb_track_width.status, "COMPLETE")
        self.assertEqual(mcp.pcb_track_width.entries[0].tracks[0].width_nm, 250_000)
        self.assertTrue(mcp.pcb_track_width.entries[0].tracks[0].below_minimum)
        self.assertEqual(mcp.pcb_reference_plane.status, "INCOMPLETE")
        self.assertEqual(mcp.pcb_reference_plane.entries[0].tracks[0].reference_layer, "In1.Cu")
        self.assertEqual(mcp.pcb_reference_plane.entries[0].tracks[0].covered_fraction_numerator, 0)
        self.assertTrue(mcp.pcb_reference_plane.entries[0].tracks[0].below_minimum)
        self.assertTrue(mcp.pcb_reference_plane.entries[0].review_excluded_short_tracks)
        self.assertEqual(
            mcp.pcb_reference_plane.entries[0].excluded_short_track_uuids,
            ("00000000-0000-0000-0000-000000000104",),
        )
        self.assertEqual(mcp.pcb_switching_loop.status, "INCOMPLETE")
        loop = mcp.pcb_switching_loop.entries[0]
        self.assertEqual(loop.loop_area_twice_nm2, 1_000_000_000)
        self.assertEqual(loop.return_plane_status, "CONNECTED")
        self.assertEqual(loop.return_island_index, 0)
        self.assertEqual(loop.route_status, "INCOMPLETE")
        self.assertEqual(loop.route_edges[0].status, "RESOLVED")
        self.assertEqual(loop.route_edges[0].length_nm, 500_000)
        plane_edge = loop.route_edges[2]
        self.assertEqual(plane_edge.status, "DECLARED")
        self.assertIsNotNone(plane_edge.plane_zone_uuid)
        self.assertEqual(plane_edge.plane_island_index, 0)
        self.assertEqual(plane_edge.plane_island_area_twice_nm2, 2_000_000_000_000)
        route_finding = next(
            item for item in mcp.findings if item.rule_id == "pcb.switching_loop_geometry"
        )
        self.assertIn("length 500000 nm", route_finding.evidence["trace_route_edges"][0])
        finding = next(item for item in mcp.findings if item.rule_id == "pcb.minimum_track_width")
        self.assertEqual(finding.evidence["net"], ("VDD",))
        reference_finding = next(
            item
            for item in mcp.findings
            if item.rule_id == "pcb.reference_plane_coverage" and "VDD" in item.subject
        )
        self.assertIn("VDD", reference_finding.subject)
        data_reference = next(
            item
            for item in mcp.pcb_reference_plane.entries
            if item.id == "synthetic-data-reference"
        )
        data_measurement = data_reference.tracks[0]
        data_via_id = "f" * 64
        self.assertEqual(
            (
                data_measurement.covered_fraction_numerator,
                data_measurement.covered_fraction_denominator,
            ),
            (1, 2),
        )
        self.assertTrue(data_measurement.below_minimum)
        self.assertEqual(data_measurement.endpoint_via_ids, (data_via_id,))
        self.assertEqual(
            data_measurement.endpoint_via_ids_with_center_in_reference_holes,
            (data_via_id,),
        )
        data_reference_finding = next(
            item
            for item in mcp.findings
            if item.rule_id == "pcb.reference_plane_coverage"
            and "synthetic-data-reference" in item.subject
        )
        self.assertIn(
            "do not identify which clearance created a hole", data_reference_finding.message
        )
        self.assertEqual(
            data_reference_finding.evidence["endpoint_via_hole_candidates"],
            (data_via_id,),
        )
        assert mcp.pcb_decoupling.snapshot_path is not None
        snapshot_path = self.root / mcp.pcb_decoupling.snapshot_path
        self.assertEqual(digest(snapshot_path), mcp.pcb_decoupling.snapshot_sha256)
        self.assertEqual(mcp.pcb_track_width.snapshot_sha256, mcp.pcb_decoupling.snapshot_sha256)
        self.assertEqual(
            mcp.pcb_protection_path.snapshot_sha256, mcp.pcb_decoupling.snapshot_sha256
        )
        self.assertEqual(
            mcp.pcb_reference_plane.snapshot_sha256, mcp.pcb_decoupling.snapshot_sha256
        )
        self.assertEqual(mcp.pcb_switching_loop.snapshot_sha256, mcp.pcb_decoupling.snapshot_sha256)
        self.assertEqual(config.kicad_version, "10.0.0")

    async def test_missing_native_evidence_keeps_configured_pcb_width_gap_visible(self) -> None:
        """A failed native lane must not erase configured width-map coverage."""
        policy = DesignLintPolicy(
            pcb_track_width_map=PcbTrackWidthMap(
                basis="Synthetic authored width review",
                requirements=(
                    PcbTrackWidthRequirement(
                        id="synthetic-vdd-width",
                        basis="Synthetic minimum width",
                        net="VDD",
                        minimum_width_um=250,
                    ),
                ),
            )
        )
        contract_path = self.island / "tests/contract.json"
        contract = read_model(contract_path, ProjectTestContract)
        write_model(contract_path, contract.model_copy(update={"design_lint": policy}))
        missing_summary = self.root / "build/missing-native-summary.json"
        missing_summary.parent.mkdir(parents=True, exist_ok=True)
        missing_summary.write_text("{ malformed synthetic summary", encoding="utf-8")

        async with Client(create_server(self.root), mode="legacy") as client:
            cli = await self.cli(
                "kicad_tooling.design_lint",
                DesignLintReport,
                "--project",
                "controller",
                "--native-summary",
                str(missing_summary),
                expected_exit=1,
            )
            mcp = await self.call(
                client,
                "inspect_design_lint",
                DesignLintReport,
                {
                    "project_id": "controller",
                    "native_summary": missing_summary.relative_to(self.root).as_posix(),
                },
            )

        for report in (cli, mcp):
            self.assertEqual(report.status, "BLOCKED")
            self.assertEqual(report.pcb_track_width.status, "BLOCKED")
            self.assertIn("native PCB geometry is unavailable", report.pcb_track_width.issue or "")

    async def test_connector_return_distribution_map_parity(self) -> None:
        """Compare role-based return-distribution review through CLI and MCP."""
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"
        roles = ("signal",) * 6 + ("return", "supply", "shield")
        pin_names = tuple(f"SIG{number}" for number in range(1, 7)) + (
            "GND",
            "VCC",
            "SHIELD",
        )
        component_pins = "".join(
            f'<pin num="{number}" name="{name}" type="passive"/>'
            for number, name in enumerate(pin_names, start=1)
        )
        net_nodes = "".join(
            f'<net name="NET_{number:02d}"><node ref="J1" pin="{number}"/></net>'
            for number in range(1, len(roles) + 1)
        )
        netlist.write_text(
            "<export><components>"
            '<comp ref="J1"><value>Synthetic external interface</value>'
            "<footprint>Synthetic:Port</footprint>"
            '<libsource lib="Synthetic" part="ExternalPort"/></comp>'
            "</components><libparts>"
            '<libpart lib="Synthetic" part="ExternalPort"><pins>'
            + component_pins
            + "</pins></libpart></libparts><nets>"
            + net_nodes
            + "</nets></export>",
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
                    "interfaces": ("synthetic-link",),
                    "connector_reviews": (
                        ConnectorInterfaceReview(
                            reference="J1",
                            disposition="interface",
                            interface_id="synthetic-link",
                            basis="Synthetic reviewed connector interface",
                            pin_map={str(number): str(number) for number in range(1, 10)},
                        ),
                    ),
                    "connector_inventory_review": ConnectorInventoryReview(
                        basis="Synthetic review covered all connector candidates in the schematic"
                    ),
                }
            ),
        )
        write_model(
            self.root / "catalog/interfaces.json",
            InterfacesCatalog(
                schema_version="1",
                interfaces=(
                    InterfaceRecord(
                        id="synthetic-link",
                        revision="synthetic-1",
                        pins=tuple(
                            InterfacePin(
                                number=str(number),
                                signal=f"contact-{number}",
                                role=role,
                                direction="bidirectional",
                                voltage_domain="synthetic-domain",
                                mating="synthetic peer",
                                orientation="straight",
                                mechanical_clearance="synthetic",
                            )
                            for number, role in enumerate(roles, start=1)
                        ),
                    ),
                ),
            ),
        )
        contract_path = self.island / "tests/contract.json"
        contract = read_model(contract_path, ProjectTestContract)
        policy = DesignLintPolicy(
            connector_return_distribution_map=ConnectorReturnDistributionMap(
                requirements=(
                    ConnectorReturnDistributionRequirement(
                        id="external-link",
                        interface_id="synthetic-link",
                        minimum_signal_pin_count=4,
                        maximum_signal_to_return_ratio=3.0,
                        basis="Synthetic authored signal/return contact threshold",
                    ),
                )
            )
        )
        write_model(contract_path, contract.model_copy(update={"design_lint": policy}))

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
        self.assertEqual(mcp.status, "REVIEW", mcp.issues)
        self.assertEqual(mcp.connector_return_distribution.status, "COMPLETE")
        self.assertEqual(mcp.connector_return_distribution.entries[0].signal_pin_count, 6)
        self.assertEqual(mcp.connector_return_distribution.entries[0].return_pin_count, 1)
        self.assertTrue(
            any(item.rule_id == "connector.return_distribution" for item in mcp.findings)
        )

    async def test_external_protection_map_parity(self) -> None:
        """Compare exact external-protection coverage through CLI and MCP."""
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"
        netlist.write_text(
            "<export><components>"
            '<comp ref="J1"><value>Synthetic USB connector</value>'
            "<footprint>Synthetic:USB-C</footprint>"
            '<libsource lib="Synthetic" part="UsbPort"/></comp>'
            '<comp ref="D1"><value>Synthetic TVS</value>'
            "<footprint>Synthetic:SOD323</footprint>"
            '<libsource lib="Synthetic" part="TVS"/></comp>'
            "</components><libparts>"
            '<libpart lib="Synthetic" part="UsbPort"><pins>'
            '<pin num="1" name="D+" type="passive"/>'
            '<pin num="2" name="D-" type="passive"/>'
            "</pins></libpart>"
            '<libpart lib="Synthetic" part="TVS"><pins>'
            '<pin num="1" name="IO" type="passive"/>'
            '<pin num="2" name="GND" type="passive"/>'
            "</pins></libpart></libparts><nets>"
            '<net name="USB_DP"><node ref="J1" pin="1"/>'
            '<node ref="D1" pin="1"/></net>'
            '<net name="USB_DM"><node ref="J1" pin="2"/></net>'
            '<net name="GND"><node ref="D1" pin="2"/></net>'
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
                    "interfaces": ("usb-data",),
                    "connector_reviews": (
                        ConnectorInterfaceReview(
                            reference="J1",
                            disposition="interface",
                            interface_id="usb-data",
                            basis="Synthetic reviewed USB connector pinout",
                            pin_map={"1": "1", "2": "2"},
                        ),
                    ),
                    "connector_inventory_review": ConnectorInventoryReview(
                        basis="Synthetic review covered all connector candidates in the schematic"
                    ),
                }
            ),
        )
        write_model(
            self.root / "catalog/interfaces.json",
            InterfacesCatalog(
                schema_version="1",
                interfaces=(
                    InterfaceRecord(
                        id="usb-data",
                        revision="synthetic-1",
                        pins=(
                            InterfacePin(
                                number="1",
                                signal="USB_D+",
                                direction="bidirectional",
                                voltage_domain="synthetic-low-voltage",
                                mating="synthetic host",
                                orientation="not applicable",
                                mechanical_clearance="not applicable",
                            ),
                            InterfacePin(
                                number="2",
                                signal="USB_D-",
                                direction="bidirectional",
                                voltage_domain="synthetic-low-voltage",
                                mating="synthetic host",
                                orientation="not applicable",
                                mechanical_clearance="not applicable",
                            ),
                        ),
                    ),
                ),
            ),
        )
        contract_path = self.island / "tests/contract.json"
        contract = read_model(contract_path, ProjectTestContract)
        protection = synthetic_protection_map()
        protection = protection.model_copy(
            update={
                "interfaces": (
                    *protection.interfaces,
                    ExternalProtectionInterfaceRequirement(
                        connector_reference="J1",
                        expected_connector_symbol="Synthetic:UsbPort",
                        expected_connector_footprint="Synthetic:USB-C",
                        connector_pin="J1.2",
                        signal_net="USB_DM",
                        disposition="not_required",
                        basis="Synthetic reviewed data-line protection decision",
                    ),
                )
            }
        )
        write_model(
            contract_path,
            contract.model_copy(
                update={"design_lint": DesignLintPolicy(external_protection_map=protection)}
            ),
        )

        async with Client(create_server(self.root), mode="legacy") as client:

            async def compare(expected_status: str, exit_code: int) -> DesignLintReport:
                cli = await self.cli(
                    "kicad_tooling.design_lint",
                    DesignLintReport,
                    "--project",
                    "controller",
                    "--native-summary",
                    str(native),
                    expected_exit=exit_code,
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
                self.assertEqual(mcp.status, expected_status, mcp.issues)
                return mcp

            matched = await compare("REVIEW", 1)
            assert matched.external_protection_coverage is not None
            self.assertEqual(matched.external_protection_coverage.status, "COMPLETE")
            self.assertEqual(
                matched.external_protection_coverage.entries[0].status,
                "PROTECTED",
            )
            self.assertEqual(matched.external_protection_coverage.netlist_sha256, digest(netlist))
            assert matched.connector_coverage is not None
            self.assertEqual(
                matched.connector_coverage.interface_catalog_path,
                "catalog/interfaces.json",
            )
            pair_review = next(
                finding
                for finding in matched.findings
                if finding.rule_id == "signal.named_pair_without_reviewed_requirement"
            )
            self.assertEqual(pair_review.subject, "USB_DP / USB_DM")

            netlist.write_text(
                netlist.read_text(encoding="utf-8").replace(
                    '<net name="USB_DP"><node ref="J1" pin="1"/>'
                    '<node ref="D1" pin="1"/></net>'
                    '<net name="USB_DM"><node ref="J1" pin="2"/></net>',
                    '<net name="USB_DP"><node ref="J1" pin="1"/></net>'
                    '<net name="USB_DM"><node ref="J1" pin="2"/>'
                    '<node ref="D1" pin="1"/></net>',
                ),
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
            mismatched = await compare("REVIEW", 1)
            assert mismatched.external_protection_coverage is not None
            self.assertEqual(
                mismatched.external_protection_coverage.entries[0].status,
                "INCOMPLETE",
            )
            self.assertTrue(
                any(
                    finding.rule_id == "protection.mapped_device_mismatch"
                    for finding in mismatched.findings
                )
            )

    async def test_crystal_network_map_parity(self) -> None:
        """Compare source-bound crystal topology and load evidence through CLI and MCP."""
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"
        netlist.write_text(
            "<export><components>"
            '<comp ref="U1"><value>Synthetic MCU</value>'
            "<footprint>Synthetic:SOIC-8</footprint>"
            '<libsource lib="Synthetic" part="Oscillator"/></comp>'
            '<comp ref="Y1"><value>Synthetic 16 MHz crystal</value>'
            "<footprint>Synthetic:Crystal-3225</footprint>"
            '<libsource lib="Device" part="Crystal"/></comp>'
            '<comp ref="C1"><value>18pF</value><footprint>Synthetic:0603</footprint>'
            '<libsource lib="Device" part="C"/></comp>'
            '<comp ref="C2"><value>18pF</value><footprint>Synthetic:0603</footprint>'
            '<libsource lib="Device" part="C"/></comp>'
            "</components><libparts>"
            '<libpart lib="Synthetic" part="Oscillator"><pins>'
            '<pin num="1" name="XTAL_IN" type="input"/>'
            '<pin num="2" name="XTAL_OUT" type="output"/>'
            "</pins></libpart>"
            '<libpart lib="Device" part="Crystal"><pins>'
            '<pin num="1" name="1" type="passive"/>'
            '<pin num="2" name="2" type="passive"/>'
            "</pins></libpart>"
            '<libpart lib="Device" part="C"><pins>'
            '<pin num="1" name="1" type="passive"/>'
            '<pin num="2" name="2" type="passive"/>'
            "</pins></libpart></libparts><nets>"
            '<net name="OSC_IN"><node ref="U1" pin="1"/>'
            '<node ref="Y1" pin="1"/><node ref="C1" pin="1"/></net>'
            '<net name="OSC_OUT"><node ref="U1" pin="2"/>'
            '<node ref="Y1" pin="2"/><node ref="C2" pin="1"/></net>'
            '<net name="GND"><node ref="C1" pin="2"/><node ref="C2" pin="2"/></net>'
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

        contract_path = self.island / "tests/contract.json"
        contract = read_model(contract_path, ProjectTestContract)
        write_model(
            contract_path,
            contract.model_copy(
                update={
                    "design_lint": DesignLintPolicy(
                        crystal_network_map=synthetic_crystal_network_map()
                    )
                }
            ),
        )

        async with Client(create_server(self.root), mode="legacy") as client:

            async def compare(expected_status: str, exit_code: int) -> DesignLintReport:
                cli = await self.cli(
                    "kicad_tooling.design_lint",
                    DesignLintReport,
                    "--project",
                    "controller",
                    "--native-summary",
                    str(native),
                    expected_exit=exit_code,
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
                self.assertEqual(mcp.status, expected_status, mcp.issues)
                return mcp

            matched = await compare("PASS", 0)
            self.assertEqual(matched.crystal_network_coverage.status, "COMPLETE")
            self.assertEqual(matched.crystal_network_coverage.netlist_sha256, digest(netlist))
            entry = matched.crystal_network_coverage.entries[0]
            self.assertEqual(entry.status, "COMPLETE")
            self.assertEqual(entry.calculated_minimum_load_pf, 10.0)
            self.assertEqual(entry.calculated_maximum_load_pf, 12.0)

            netlist.write_text(
                netlist.read_text(encoding="utf-8").replace(
                    '<net name="OSC_IN"><node ref="U1" pin="1"/>'
                    '<node ref="Y1" pin="1"/><node ref="C1" pin="1"/>'
                    '</net><net name="OSC_OUT"><node ref="U1" pin="2"/>'
                    '<node ref="Y1" pin="2"/><node ref="C2" pin="1"/></net>',
                    '<net name="OSC_IN"><node ref="U1" pin="1"/>'
                    '<node ref="Y1" pin="1"/><node ref="C1" pin="1"/>'
                    '<node ref="C2" pin="1"/></net>'
                    '<net name="OSC_OUT"><node ref="U1" pin="2"/>'
                    '<node ref="Y1" pin="2"/></net>',
                ),
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
            mismatched = await compare("REVIEW", 1)
            self.assertEqual(mismatched.crystal_network_coverage.entries[0].status, "INCOMPLETE")
            self.assertTrue(
                any(
                    finding.rule_id == "oscillator.crystal_load_network_mismatch"
                    for finding in mismatched.findings
                )
            )

    async def test_i2c_address_map_parity(self) -> None:
        """Compare mapped static-address review through the CLI and MCP surfaces."""
        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"
        netlist.write_text(
            "<export><components>"
            '<comp ref="U1"><value>Synthetic EEPROM</value>'
            '<libsource lib="Synthetic" part="EEPROM"/></comp>'
            '<comp ref="U2"><value>Synthetic EEPROM</value>'
            '<libsource lib="Synthetic" part="EEPROM"/></comp>'
            '<comp ref="U3"><value>Unmapped synthetic EEPROM</value>'
            '<libsource lib="Synthetic" part="EEPROM"/></comp>'
            '<comp ref="R1"><value>4.7k</value><libsource lib="Device" part="R"/></comp>'
            '<comp ref="R2"><value>4.7k</value><libsource lib="Device" part="R"/></comp>'
            "</components><libparts>"
            '<libpart lib="Synthetic" part="EEPROM"><pins>'
            '<pin num="1" name="SDA" type="passive"/>'
            '<pin num="2" name="SCL" type="passive"/>'
            '<pin num="3" name="A0" type="passive"/>'
            "</pins></libpart>"
            '<libpart lib="Device" part="R"><pins>'
            '<pin num="1" name="1" type="passive"/>'
            '<pin num="2" name="2" type="passive"/>'
            "</pins></libpart></libparts><nets>"
            '<net name="I2C_SDA"><node ref="U1" pin="1"/>'
            '<node ref="U2" pin="1"/><node ref="U3" pin="1"/>'
            '<node ref="R1" pin="1"/></net>'
            '<net name="I2C_SCL"><node ref="U1" pin="2"/>'
            '<node ref="U2" pin="2"/><node ref="U3" pin="2"/>'
            '<node ref="R2" pin="1"/></net>'
            '<net name="+3V3"><node ref="U1" pin="3"/>'
            '<node ref="R1" pin="2"/><node ref="R2" pin="2"/></net>'
            '<net name="GND"><node ref="U2" pin="3"/></net>'
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

        address_map = I2cAddressMap(
            basis="Synthetic reviewed responder and segment map",
            segments=(
                I2cAddressSegmentRequirement(
                    id="main",
                    sda_net="I2C_SDA",
                    scl_net="I2C_SCL",
                    responders=(
                        I2cResponderAddressRequirement(
                            reference="U1",
                            expected_symbol="Synthetic:EEPROM",
                            sda_pin="U1.1",
                            scl_pin="U1.2",
                            mode="strapped",
                            address=0x50,
                            address_bits=(
                                I2cAddressBitRequirement(
                                    bit=0,
                                    pin="U1.3",
                                    function="A0",
                                    low_net="GND",
                                    high_net="+3V3",
                                ),
                            ),
                            basis="Synthetic expected 7-bit address 0x50",
                        ),
                        I2cResponderAddressRequirement(
                            reference="U2",
                            expected_symbol="Synthetic:EEPROM",
                            sda_pin="U2.1",
                            scl_pin="U2.2",
                            mode="fixed",
                            address=0x51,
                            basis="Synthetic fixed 7-bit address 0x51",
                        ),
                    ),
                ),
            ),
        )
        contract_path = self.island / "tests/contract.json"
        contract = read_model(contract_path, ProjectTestContract)
        write_model(
            contract_path,
            contract.model_copy(
                update={"design_lint": DesignLintPolicy(i2c_address_map=address_map)}
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
        self.assertEqual(mcp.status, "REVIEW", mcp.model_dump_json(indent=2))
        self.assertEqual(mcp.i2c_address_coverage.status, "COMPLETE")
        self.assertEqual(mcp.i2c_address_coverage.netlist_sha256, digest(netlist))
        mismatch = [item for item in mcp.findings if item.rule_id == "bus.i2c_address_mismatch"]
        collisions = [item for item in mcp.findings if item.rule_id == "bus.i2c_address_collision"]
        self.assertEqual(len(mismatch), 1)
        self.assertEqual(len(collisions), 1)
        self.assertEqual(mismatch[0].subject, "U1 on main: 0x51")
        self.assertEqual(collisions[0].subject, "main: U1, U2 at 0x51")
        unmapped = [item for item in mcp.findings if item.rule_id == "bus.i2c_unmapped_responder"]
        self.assertEqual(len(unmapped), 1)
        self.assertEqual(unmapped[0].subject, "U3: I2C address-map coverage")

    async def test_schematic_geometry_opt_in_parity(self) -> None:
        """Exercise source-bound geometry through installed CLI and MCP adapters."""
        schematic = self.island / "kicad/controller.kicad_sch"
        schematic_source = (
            (
                Path(__file__).parent
                / "fixtures/design_lint/t-junction/near-miss-crossing-and-t-junction.kicad_sch"
            )
            .read_text(encoding="utf-8")
            .replace("near-miss-pin-line", "controller")
        )
        text_nodes = (
            '  (text "PARITY_A" (at 25.4 25.4 0) '
            "(effects (font (size 1.27 1.27))) "
            '(uuid "d1000000-0000-4000-8000-000000000001"))\n'
            '  (text "PARITY_B" (at 25.4 25.4 0) '
            "(effects (font (size 1.27 1.27))) "
            '(uuid "d1000000-0000-4000-8000-000000000002"))\n'
            '  (text "LONG_LABEL_ALPHA" (at 150 25.4 0) '
            "(effects (font (size 1.27 1.27)) (justify right)) "
            '(uuid "d1000000-0000-4000-8000-000000000003"))\n'
            '  (text "LONG_LABEL_BETA" (at 153.6 25.4 0) '
            "(effects (font (size 1.27 1.27))) "
            '(uuid "d1000000-0000-4000-8000-000000000004"))\n'
            '  (text "WIRE_NOTE" (at 127 127 0) '
            "(effects (font (size 1.27 1.27))) "
            '(uuid "d1000000-0000-4000-8000-000000000005"))\n'
            '  (text "BODY_NOTE" (at 76.2 78.0 0) '
            "(effects (font (size 1.27 1.27))) "
            '(uuid "d1000000-0000-4000-8000-000000000006"))\n'
        )
        body_wire = (
            "  (wire (pts (xy 71.12 76.2) (xy 81.28 76.2)) "
            "(stroke (width 0) (type default)) "
            '(uuid "f1000000-0000-4000-8000-000000000001"))\n'
        )
        schematic_source = schematic_source.replace(
            "  (sheet_instances", f"{body_wire}{text_nodes}  (sheet_instances", 1
        )
        schematic.write_text(schematic_source, encoding="utf-8")

        manifest_path = self.island / "project.json"
        manifest = read_model(manifest_path, ProjectManifest)
        write_model(manifest_path, manifest.model_copy(update={"toolchain_id": "kicad-10.0.6"}))
        toolchains_path = self.root / "catalog/toolchains.json"
        toolchains = read_model(toolchains_path, ToolchainsCatalog)
        toolchain_10_0_6 = toolchains.toolchains[0].model_copy(
            update={
                "id": "kicad-10.0.6",
                "kicad_version": "10.0.6",
                "image": f"registry.invalid/kicad:10.0.6@sha256:{'a' * 64}",
            }
        )
        write_model(
            toolchains_path,
            toolchains.model_copy(
                update={"toolchains": (*toolchains.toolchains, toolchain_10_0_6)}
            ),
        )

        contract_path = self.island / "tests/contract.json"
        contract = read_model(contract_path, ProjectTestContract)
        write_model(
            contract_path,
            contract.model_copy(
                update={
                    "design_lint": DesignLintPolicy(
                        rules=(
                            DesignLintRuleOverride(
                                rule_id="schematic.wire_end_on_pin_line",
                                mode="review",
                                reason="Synthetic parity fixture opts in to pin-line localization",
                            ),
                            DesignLintRuleOverride(
                                rule_id="schematic.unmarked_wire_crossing",
                                mode="review",
                                reason="Synthetic parity fixture opts in to crossing review",
                            ),
                            DesignLintRuleOverride(
                                rule_id="schematic.unmarked_t_junction",
                                mode="review",
                                reason="Synthetic parity fixture opts in to T-junction review",
                            ),
                            DesignLintRuleOverride(
                                rule_id="schematic.coincident_text_anchors",
                                mode="review",
                                reason="Synthetic parity fixture opts in to graphical text review",
                            ),
                            DesignLintRuleOverride(
                                rule_id="schematic.free_text_overlap",
                                mode="review",
                                reason="Synthetic parity fixture opts in to rendered text-envelope review",
                            ),
                            DesignLintRuleOverride(
                                rule_id="schematic.free_text_over_wire",
                                mode="review",
                                reason="Synthetic parity fixture opts in to free-text wire-envelope review",
                            ),
                            DesignLintRuleOverride(
                                rule_id="schematic.wire_through_symbol_body",
                                mode="review",
                                reason="Synthetic parity fixture opts in to symbol-body wire review",
                            ),
                            DesignLintRuleOverride(
                                rule_id="schematic.free_text_over_symbol_body",
                                mode="review",
                                reason="Synthetic parity fixture opts in to text-body review",
                            ),
                        )
                    )
                }
            ),
        )

        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"
        netlist.write_text(
            native_fixture.NETLIST.replace(
                "<nets/>",
                '<nets><net name="unconnected-(R1-Pad1)"><node ref="R1" pin="1"/></net></nets>',
            ),
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
        self.assertEqual(mcp.status, "REVIEW", mcp.model_dump_json(indent=2))
        self.assertEqual(
            mcp.schematic_geometry.status,
            "COMPLETE",
            mcp.schematic_geometry.model_dump_json(indent=2),
        )
        self.assertEqual(mcp.schematic_geometry.mode, "review")
        self.assertEqual(
            mcp.schematic_geometry.source_path, schematic.relative_to(self.root).as_posix()
        )
        self.assertEqual(mcp.schematic_geometry.source_sha256, digest(schematic))
        self.assertEqual(mcp.schematic_geometry.netlist_sha256, digest(netlist))
        self.assertEqual(mcp.schematic_geometry.kicad_version, "10.0.6")
        self.assertEqual(mcp.schematic_geometry.finding_count, 9)
        geometry_findings = [
            item for item in mcp.findings if item.rule_id == "schematic.wire_end_on_pin_line"
        ]
        self.assertEqual(len(geometry_findings), 1)
        self.assertEqual(geometry_findings[0].evidence["pin"], ("R1.1",))
        crossing_findings = [
            item for item in mcp.findings if item.rule_id == "schematic.unmarked_wire_crossing"
        ]
        self.assertEqual(len(crossing_findings), 1)
        self.assertEqual(crossing_findings[0].evidence["crossing_mm"], ("127.000000,127.000000",))
        t_junction_findings = [
            item for item in mcp.findings if item.rule_id == "schematic.unmarked_t_junction"
        ]
        self.assertEqual(len(t_junction_findings), 1)
        self.assertEqual(t_junction_findings[0].evidence["junction_mm"], ("177.800000,177.800000",))
        text_anchor_findings = [
            item for item in mcp.findings if item.rule_id == "schematic.coincident_text_anchors"
        ]
        self.assertEqual(len(text_anchor_findings), 1)
        self.assertEqual(
            text_anchor_findings[0].evidence["first_text_uuid"],
            ("d1000000-0000-4000-8000-000000000001",),
        )
        text_overlap_findings = [
            item for item in mcp.findings if item.rule_id == "schematic.free_text_overlap"
        ]
        self.assertEqual(len(text_overlap_findings), 1)
        self.assertEqual(
            text_overlap_findings[0].evidence["first_text_uuid"],
            ("d1000000-0000-4000-8000-000000000003",),
        )
        text_wire_findings = [
            item for item in mcp.findings if item.rule_id == "schematic.free_text_over_wire"
        ]
        self.assertEqual(len(text_wire_findings), 2)
        self.assertEqual(
            {item.evidence["text_uuid"] for item in text_wire_findings},
            {("d1000000-0000-4000-8000-000000000005",)},
        )
        self.assertTrue(all("overlap_segment_mm" in item.evidence for item in text_wire_findings))
        body_findings = [
            item for item in mcp.findings if item.rule_id == "schematic.wire_through_symbol_body"
        ]
        self.assertEqual(len(body_findings), 1)
        self.assertEqual(body_findings[0].evidence["reference"], ("R1",))
        self.assertEqual(
            body_findings[0].evidence["wire_uuid"], ("f1000000-0000-4000-8000-000000000001",)
        )
        self.assertIn("body_box_mm", body_findings[0].evidence)
        text_body_findings = [
            item for item in mcp.findings if item.rule_id == "schematic.free_text_over_symbol_body"
        ]
        self.assertEqual(len(text_body_findings), 1)
        self.assertEqual(
            text_body_findings[0].evidence["text_uuid"],
            ("d1000000-0000-4000-8000-000000000006",),
        )
        self.assertEqual(text_body_findings[0].evidence["reference"], ("R1",))
        self.assertIn("overlap_area_mm2", text_body_findings[0].evidence)

        contract = read_model(contract_path, ProjectTestContract)
        write_model(
            contract_path,
            contract.model_copy(
                update={
                    "design_lint": DesignLintPolicy(
                        rules=(
                            DesignLintRuleOverride(
                                rule_id="schematic.wire_end_on_pin_line",
                                mode="off",
                                reason="Synthetic parity fixture checks explicit opt-out",
                            ),
                            DesignLintRuleOverride(
                                rule_id="schematic.unmarked_wire_crossing",
                                mode="off",
                                reason="Synthetic parity fixture checks crossing opt-out",
                            ),
                            DesignLintRuleOverride(
                                rule_id="schematic.unmarked_t_junction",
                                mode="off",
                                reason="Synthetic parity fixture checks T-junction opt-out",
                            ),
                            DesignLintRuleOverride(
                                rule_id="schematic.coincident_text_anchors",
                                mode="off",
                                reason="Synthetic parity fixture checks graphical text opt-out",
                            ),
                            DesignLintRuleOverride(
                                rule_id="schematic.free_text_over_wire",
                                mode="off",
                                reason="Synthetic parity fixture checks wire-envelope opt-out",
                            ),
                            DesignLintRuleOverride(
                                rule_id="schematic.wire_through_symbol_body",
                                mode="off",
                                reason="Synthetic parity fixture checks symbol-body opt-out",
                            ),
                            DesignLintRuleOverride(
                                rule_id="schematic.free_text_over_symbol_body",
                                mode="off",
                                reason="Synthetic parity fixture checks text-body opt-out",
                            ),
                        )
                    )
                }
            ),
        )
        async with Client(create_server(self.root), mode="legacy") as client:
            disabled_cli = await self.cli(
                "kicad_tooling.design_lint",
                DesignLintReport,
                "--project",
                "controller",
                "--native-summary",
                str(native),
                expected_exit=0,
            )
            disabled_mcp = await self.call(
                client,
                "inspect_design_lint",
                DesignLintReport,
                {
                    "project_id": "controller",
                    "native_summary": native.relative_to(self.root).as_posix(),
                },
            )
        self.assertEqual(disabled_cli, disabled_mcp)
        self.assertEqual(disabled_mcp.status, "PASS")
        self.assertEqual(disabled_mcp.schematic_geometry.status, "DISABLED")
        self.assertFalse(
            any(item.rule_id == "schematic.wire_end_on_pin_line" for item in disabled_mcp.findings)
        )
        self.assertFalse(
            any(
                item.rule_id == "schematic.unmarked_wire_crossing" for item in disabled_mcp.findings
            )
        )
        self.assertFalse(
            any(item.rule_id == "schematic.unmarked_t_junction" for item in disabled_mcp.findings)
        )
        self.assertFalse(
            any(
                item.rule_id == "schematic.coincident_text_anchors"
                for item in disabled_mcp.findings
            )
        )
        self.assertFalse(
            any(item.rule_id == "schematic.free_text_over_wire" for item in disabled_mcp.findings)
        )
        self.assertFalse(
            any(
                item.rule_id == "schematic.wire_through_symbol_body"
                for item in disabled_mcp.findings
            )
        )
        self.assertFalse(
            any(
                item.rule_id == "schematic.free_text_over_symbol_body"
                for item in disabled_mcp.findings
            )
        )

    async def test_reused_child_sheet_geometry_source_binding_cli_mcp_parity(self) -> None:
        """Bind repeated child findings to each KiCad hierarchy instance."""
        fixture_root = Path(__file__).parent / "fixtures/design_lint/repeated-sheet"
        schematic = self.island / "kicad/controller.kicad_sch"
        channel = self.island / "kicad/repeated-channel.kicad_sch"
        schematic.write_text(
            (fixture_root / "repeated-sheet-root.kicad_sch")
            .read_text(encoding="utf-8")
            .replace("repeated-sheet-root", "controller"),
            encoding="utf-8",
        )
        channel_text = (
            (fixture_root / "repeated-channel.kicad_sch")
            .read_text(encoding="utf-8")
            .replace("repeated-sheet-root", "controller")
        )
        channel_text = channel_text.replace(
            "  (sheet_instances",
            "  (wire (pts (xy 76.2 80.01) (xy 101.6 80.01)) "
            "(stroke (width 0) (type default)) "
            '(uuid "c0000000-0000-4000-8000-000000000013"))\n'
            "  (sheet_instances",
            1,
        )
        channel.write_text(
            channel_text,
            encoding="utf-8",
        )

        manifest_path = self.island / "project.json"
        manifest = read_model(manifest_path, ProjectManifest)
        write_model(
            manifest_path,
            manifest.model_copy(
                update={
                    "toolchain_id": "kicad-10.0.6",
                    "required_inputs": tuple(
                        sorted(
                            {
                                *manifest.required_inputs,
                                channel.relative_to(self.island).as_posix(),
                            }
                        )
                    ),
                }
            ),
        )
        toolchains_path = self.root / "catalog/toolchains.json"
        toolchains = read_model(toolchains_path, ToolchainsCatalog)
        toolchain_10_0_6 = toolchains.toolchains[0].model_copy(
            update={
                "id": "kicad-10.0.6",
                "kicad_version": "10.0.6",
                "image": f"registry.invalid/kicad:10.0.6@sha256:{'a' * 64}",
            }
        )
        write_model(
            toolchains_path,
            toolchains.model_copy(
                update={"toolchains": (*toolchains.toolchains, toolchain_10_0_6)}
            ),
        )

        contract_path = self.island / "tests/contract.json"
        contract = read_model(contract_path, ProjectTestContract)
        write_model(
            contract_path,
            contract.model_copy(
                update={
                    "design_lint": DesignLintPolicy(
                        rules=(
                            DesignLintRuleOverride(
                                rule_id="schematic.wire_end_on_pin_line",
                                mode="review",
                                reason="Synthetic repeated-sheet fixture checks per-instance pin mapping",
                            ),
                            DesignLintRuleOverride(
                                rule_id="schematic.unmarked_t_junction",
                                mode="review",
                                reason="Synthetic repeated-sheet parity fixture opts in to review",
                            ),
                        )
                    )
                }
            ),
        )

        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"
        netlist.write_text(
            native_fixture.NETLIST.replace(
                "<nets/>",
                '<nets><net name="unconnected-(R1-Pad2)"><node ref="R1" pin="2"/>'
                '</net><net name="unconnected-(R2-Pad2)"><node ref="R2" pin="2"/>'
                "</net></nets>",
            ),
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
        coverage = mcp.schematic_geometry
        self.assertEqual(coverage.status, "COMPLETE", mcp.model_dump_json(indent=2))
        self.assertEqual(coverage.source_sha256, digest(schematic))
        self.assertNotEqual(coverage.source_tree_sha256, coverage.source_sha256)
        self.assertEqual(coverage.finding_count, 6)
        self.assertEqual(len(coverage.source_bindings), 3)
        self.assertEqual(
            {binding.sheet_path for binding in coverage.source_bindings},
            {(), ("InstanceA",), ("InstanceB",)},
        )
        findings = [
            item for item in mcp.findings if item.rule_id == "schematic.unmarked_t_junction"
        ]
        self.assertEqual(len(findings), 2)
        self.assertEqual(len({item.fingerprint for item in findings}), 2)
        self.assertEqual(
            {item.evidence["schematic"][0] for item in findings},
            {channel.relative_to(self.root).as_posix()},
        )
        self.assertEqual(
            {item.evidence["sheet_instance_path"][0] for item in findings},
            {
                "/d0000000-0000-4000-8000-000000000001/d0000000-0000-4000-8000-000000000002",
                "/d0000000-0000-4000-8000-000000000001/d0000000-0000-4000-8000-000000000003",
            },
        )
        self.assertEqual(
            {item.evidence["schematic_sha256"][0] for item in findings},
            {digest(channel)},
        )
        pin_line_findings = [
            item for item in mcp.findings if item.rule_id == "schematic.wire_end_on_pin_line"
        ]
        self.assertEqual(len(pin_line_findings), 2)
        self.assertEqual(
            {item.evidence["pin"][0] for item in pin_line_findings},
            {"R1.2", "R2.2"},
        )
        self.assertEqual(
            {item.evidence["sheet_instance_path"][0] for item in pin_line_findings},
            {item.evidence["sheet_instance_path"][0] for item in findings},
        )

    async def test_schematic_pin_tip_on_wire_interior_cli_mcp_parity(self) -> None:
        schematic = self.island / "kicad/controller.kicad_sch"
        schematic.write_bytes(
            (
                Path(__file__).parent
                / "fixtures/design_lint/pin-on-wire-middle-no-junction.kicad_sch"
            ).read_bytes()
        )

        manifest_path = self.island / "project.json"
        manifest = read_model(manifest_path, ProjectManifest)
        write_model(manifest_path, manifest.model_copy(update={"toolchain_id": "kicad-10.0.6"}))
        toolchains_path = self.root / "catalog/toolchains.json"
        toolchains = read_model(toolchains_path, ToolchainsCatalog)
        toolchain_10_0_6 = toolchains.toolchains[0].model_copy(
            update={
                "id": "kicad-10.0.6",
                "kicad_version": "10.0.6",
                "image": f"registry.invalid/kicad:10.0.6@sha256:{'a' * 64}",
            }
        )
        write_model(
            toolchains_path,
            toolchains.model_copy(
                update={"toolchains": (*toolchains.toolchains, toolchain_10_0_6)}
            ),
        )
        contract_path = self.island / "tests/contract.json"
        contract = read_model(contract_path, ProjectTestContract)
        write_model(
            contract_path,
            contract.model_copy(
                update={
                    "design_lint": DesignLintPolicy(
                        rules=(
                            DesignLintRuleOverride(
                                rule_id="schematic.pin_tip_on_wire_interior",
                                mode="review",
                                reason="Synthetic parity fixture opts in to wire-interior review",
                            ),
                        )
                    )
                }
            ),
        )

        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"
        netlist.write_text(
            native_fixture.NETLIST.replace(
                "<nets/>",
                '<nets><net name="unconnected-(R1-Pad1)"><node ref="R1" pin="1"/></net></nets>',
            ),
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
        self.assertEqual(mcp.status, "REVIEW", mcp.model_dump_json(indent=2))
        self.assertEqual(
            mcp.schematic_geometry.status,
            "COMPLETE",
            mcp.schematic_geometry.model_dump_json(indent=2),
        )
        self.assertEqual(mcp.schematic_geometry.mode, "review")
        self.assertEqual(
            mcp.schematic_geometry.rule_modes["schematic.pin_tip_on_wire_interior"],
            "review",
        )
        self.assertEqual(mcp.schematic_geometry.finding_count, 1)
        findings = [
            item for item in mcp.findings if item.rule_id == "schematic.pin_tip_on_wire_interior"
        ]
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].evidence["pin"], ("R1.1",))
        self.assertEqual(findings[0].evidence["wire_segment_start_mm"], ("50.800000,71.120000",))
        self.assertEqual(findings[0].evidence["wire_segment_end_mm"], ("101.600000,71.120000",))

    async def test_schematic_label_near_wire_endpoint_cli_mcp_parity(self) -> None:
        schematic = self.island / "kicad/controller.kicad_sch"
        schematic.write_bytes(
            (
                Path(__file__).parent / "fixtures/design_lint/label-near-wire-endpoint.kicad_sch"
            ).read_bytes()
        )

        manifest_path = self.island / "project.json"
        manifest = read_model(manifest_path, ProjectManifest)
        write_model(manifest_path, manifest.model_copy(update={"toolchain_id": "kicad-10.0.6"}))
        toolchains_path = self.root / "catalog/toolchains.json"
        toolchains = read_model(toolchains_path, ToolchainsCatalog)
        toolchain_10_0_6 = toolchains.toolchains[0].model_copy(
            update={
                "id": "kicad-10.0.6",
                "kicad_version": "10.0.6",
                "image": f"registry.invalid/kicad:10.0.6@sha256:{'a' * 64}",
            }
        )
        write_model(
            toolchains_path,
            toolchains.model_copy(
                update={"toolchains": (*toolchains.toolchains, toolchain_10_0_6)}
            ),
        )
        contract_path = self.island / "tests/contract.json"
        contract = read_model(contract_path, ProjectTestContract)
        write_model(
            contract_path,
            contract.model_copy(
                update={
                    "design_lint": DesignLintPolicy(
                        rules=(
                            DesignLintRuleOverride(
                                rule_id="schematic.label_near_wire_endpoint",
                                mode="review",
                                reason="Synthetic parity fixture opts in to label localization",
                            ),
                        )
                    )
                }
            ),
        )

        native = self.native_evidence()
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
        self.assertEqual(mcp.status, "REVIEW", mcp.model_dump_json(indent=2))
        self.assertEqual(
            mcp.schematic_geometry.status,
            "COMPLETE",
            mcp.schematic_geometry.model_dump_json(indent=2),
        )
        self.assertEqual(mcp.schematic_geometry.mode, "review")
        self.assertEqual(
            mcp.schematic_geometry.rule_modes["schematic.label_near_wire_endpoint"], "review"
        )
        findings = [
            item for item in mcp.findings if item.rule_id == "schematic.label_near_wire_endpoint"
        ]
        self.assertEqual(len(findings), 1)
        self.assertEqual(
            findings[0].evidence["label_uuid"], ("b0000000-0000-4000-8000-000000000006",)
        )
        self.assertEqual(
            findings[0].evidence["near_wire_endpoints"],
            ("b0000000-0000-4000-8000-000000000005@101.600000,71.120000 (0.500000 mm)",),
        )

    async def test_schematic_wire_endpoint_near_pin_tip_cli_mcp_parity(self) -> None:
        schematic = self.island / "kicad/controller.kicad_sch"
        schematic.write_bytes(
            (
                Path(__file__).parent / "fixtures/design_lint/wire-end-near-pin-tip.kicad_sch"
            ).read_bytes()
        )
        manifest_path = self.island / "project.json"
        manifest = read_model(manifest_path, ProjectManifest)
        write_model(manifest_path, manifest.model_copy(update={"toolchain_id": "kicad-10.0.6"}))
        toolchains_path = self.root / "catalog/toolchains.json"
        toolchains = read_model(toolchains_path, ToolchainsCatalog)
        toolchain_10_0_6 = toolchains.toolchains[0].model_copy(
            update={
                "id": "kicad-10.0.6",
                "kicad_version": "10.0.6",
                "image": f"registry.invalid/kicad:10.0.6@sha256:{'a' * 64}",
            }
        )
        write_model(
            toolchains_path,
            toolchains.model_copy(
                update={"toolchains": (*toolchains.toolchains, toolchain_10_0_6)}
            ),
        )
        contract_path = self.island / "tests/contract.json"
        contract = read_model(contract_path, ProjectTestContract)
        write_model(
            contract_path,
            contract.model_copy(
                update={
                    "design_lint": DesignLintPolicy(
                        rules=(
                            DesignLintRuleOverride(
                                rule_id="schematic.wire_endpoint_near_pin_tip",
                                mode="review",
                                reason="Synthetic parity fixture opts in to wire near-miss review",
                            ),
                        )
                    )
                }
            ),
        )

        native = self.native_evidence()
        netlist = native.parent / "netlist.xml"
        netlist.write_text(
            native_fixture.NETLIST.replace(
                "<nets/>",
                '<nets><net name="unconnected-(R1-Pad1)"><node ref="R1" pin="1"/></net></nets>',
            ),
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
        self.assertEqual(mcp.status, "REVIEW", mcp.model_dump_json(indent=2))
        self.assertEqual(mcp.schematic_geometry.status, "COMPLETE")
        self.assertEqual(mcp.schematic_geometry.mode, "review")
        self.assertEqual(
            mcp.schematic_geometry.rule_modes["schematic.wire_endpoint_near_pin_tip"],
            "review",
        )
        self.assertEqual(mcp.schematic_geometry.finding_count, 1)
        findings = [
            item for item in mcp.findings if item.rule_id == "schematic.wire_endpoint_near_pin_tip"
        ]
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].evidence["pin"], ("R1.1",))
        self.assertEqual(findings[0].evidence["wire_endpoint_mm"], ("76.200000,70.620000",))
        self.assertEqual(findings[0].evidence["distance_to_pin_tip_mm"], ("0.500000",))

        contract = read_model(contract_path, ProjectTestContract)
        write_model(
            contract_path,
            contract.model_copy(
                update={
                    "design_lint": DesignLintPolicy(
                        rules=(
                            DesignLintRuleOverride(
                                rule_id="schematic.wire_endpoint_near_pin_tip",
                                mode="off",
                                reason="Synthetic parity fixture checks explicit opt-out",
                            ),
                        )
                    )
                }
            ),
        )
        async with Client(create_server(self.root), mode="legacy") as client:
            disabled_cli = await self.cli(
                "kicad_tooling.design_lint",
                DesignLintReport,
                "--project",
                "controller",
                "--native-summary",
                str(native),
                expected_exit=0,
            )
            disabled_mcp = await self.call(
                client,
                "inspect_design_lint",
                DesignLintReport,
                {
                    "project_id": "controller",
                    "native_summary": native.relative_to(self.root).as_posix(),
                },
            )
        self.assertEqual(disabled_cli, disabled_mcp)
        self.assertEqual(disabled_mcp.status, "PASS")
        self.assertEqual(disabled_mcp.schematic_geometry.status, "DISABLED")
        self.assertNotIn(
            "schematic.wire_endpoint_near_pin_tip",
            {item.rule_id for item in disabled_mcp.findings},
        )

    async def test_model_coverage_parity(self) -> None:
        board = self.island / "kicad/controller.kicad_pcb"
        async with Client(create_server(self.root), mode="legacy") as client:
            for broken in (False, True):
                with self.subTest(missing_assigned_model=broken):
                    assignment = '(model "${KIPRJMOD}/missing.step")' if broken else ""
                    board.write_text(
                        '(kicad_pcb (footprint "Test:Part" '
                        f'(property "Reference" "U1") {assignment}))',
                        encoding="utf-8",
                    )
                    cli = await self.cli(
                        "kicad_tooling.visualize",
                        ThreeDReport,
                        "--project",
                        "controller",
                        "--check-models",
                        expected_exit=int(broken),
                    )
                    mcp = await self.call(
                        client,
                        "inspect_3d_models",
                        ModelInventoryReport,
                        {"project_id": "controller"},
                    )
                    self.assertEqual(cli.models, mcp)
                    self.assertEqual(mcp.status, "FAIL" if broken else "REVIEW")
                    self.assertEqual(cli.mode, "inspect")
                    self.assertEqual(cli.runner, "none")

    async def test_parts_preferences_parity(self) -> None:
        path = self.island / "docs/purchasing.json"
        cli = await self.cli(
            "kicad_tooling.parts",
            PurchasingPreferences,
            "--project",
            "controller",
            "--init-preferences",
            str(path),
            "--boards",
            "10",
            "--spare-percent",
            "10",
            "--spare-minimum",
            "3",
        )
        expected_bytes = path.read_bytes()
        path.unlink()
        async with Client(create_server(self.root, allow_edits=True), mode="legacy") as client:
            mcp = await self.call(
                client,
                "save_parts_preferences",
                McpPurchasingPreferencesResult,
                {
                    "project_id": "controller",
                    "preferences": cli.model_dump(mode="json"),
                },
            )
        self.assertEqual(cli, mcp.preferences)
        self.assertEqual(path.read_bytes(), expected_bytes)
        self.assertEqual(mcp.after_sha256, digest(path))
        self.assertEqual(mcp.readback_sha256, mcp.after_sha256)
        self.assertFalse(mcp.purchase_authorized)

        # Compare the shared explicit save/update operation, including stale writes.
        path.unlink()
        cli_created = await self.cli(
            "kicad_tooling.parts",
            McpPurchasingPreferencesResult,
            "--project",
            "controller",
            "--save-preferences",
            "--boards",
            "10",
            "--spare-percent",
            "10",
            "--spare-minimum",
            "3",
        )
        original = path.read_bytes()
        path.unlink()
        async with Client(create_server(self.root, allow_edits=True), mode="legacy") as client:
            created = await self.call(
                client,
                "save_parts_preferences",
                McpPurchasingPreferencesResult,
                {
                    "project_id": "controller",
                    "preferences": cli_created.preferences.model_dump(mode="json"),
                },
            )
            self.assertEqual(cli_created, created)
            self.assertEqual(path.read_bytes(), original)
            cli_updated = await self.cli(
                "kicad_tooling.parts",
                McpPurchasingPreferencesResult,
                "--project",
                "controller",
                "--save-preferences",
                "--boards",
                "20",
                "--expected-sha256",
                created.after_sha256,
            )
            updated_bytes = path.read_bytes()
            path.write_bytes(original)
            updated = await self.call(
                client,
                "save_parts_preferences",
                McpPurchasingPreferencesResult,
                {
                    "project_id": "controller",
                    "preferences": cli_updated.preferences.model_dump(mode="json"),
                    "expected_sha256": created.after_sha256,
                },
            )
            self.assertEqual(cli_updated, updated)
            self.assertEqual(path.read_bytes(), updated_bytes)
            rejected_cli = await self.cli_process(
                "kicad_tooling.parts",
                "--project",
                "controller",
                "--save-preferences",
                "--boards",
                "30",
                "--expected-sha256",
                created.after_sha256,
            )
            self.assertEqual(rejected_cli.returncode, 2)
            rejected_mcp = await client.call_tool(
                "save_parts_preferences",
                {
                    "project_id": "controller",
                    "preferences": {"boards": 30},
                    "expected_sha256": created.after_sha256,
                },
            )
            self.assertTrue(rejected_mcp.is_error)
            self.assertIn("Source hash mismatch", rejected_cli.stderr)
            self.assertIn("Source hash mismatch", str(rejected_mcp.content))
            self.assertEqual(path.read_bytes(), updated_bytes)

    async def test_parts_quantities_and_native_failure_parity(self) -> None:
        native = self.native_evidence()
        write_model(
            self.island / "docs/purchasing.json",
            PurchasingPreferences(
                boards=4,
                spare_percent=10,
                spare_minimum=3,
            ),
        )
        cli = await self.cli(
            "kicad_tooling.parts",
            PurchasingReport,
            "--project",
            "controller",
            "--native-summary",
            str(native),
            "--boards",
            "10",
            "--output",
            str(self.root / "build/parts/cli-quantities"),
        )
        async with Client(create_server(self.root, allow_exports=True), mode="legacy") as client:
            mcp = await self.call(
                client,
                "prepare_parts",
                PurchasingReport,
                {
                    "project_id": "controller",
                    "view_id": "mcp-quantities",
                    "boards": 10,
                    "native_summary": native.relative_to(self.root).as_posix(),
                },
            )
        self.receipt_equal(cli, mcp, "receipt_dir")
        self.assertIsNotNone(mcp.plan)
        self.assertEqual(mcp.plan.lines[0].quantity, 23)
        self.assertEqual(mcp.plan.excluded_references, ("C1",))
        self.assertEqual(mcp.native_status, "FAIL")
        self.assertEqual(mcp.status, "READY_FOR_ORDER_REVIEW")
        self.assertFalse(mcp.purchase_authorized)
        self.assertFalse(mcp.build_authorized)
        for name in ("bom.csv", "digikey.csv", "netlist.xml"):
            self.assertEqual(
                (Path(cli.receipt_dir) / name).read_bytes(),
                (Path(mcp.receipt_dir) / name).read_bytes(),
            )

    async def test_parts_stale_evidence_parity(self) -> None:
        native = self.native_evidence()
        schematic = self.island / "kicad/controller.kicad_sch"
        schematic.write_text(schematic.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        cli = await self.cli(
            "kicad_tooling.parts",
            PurchasingReport,
            "--project",
            "controller",
            "--native-summary",
            str(native),
            "--output",
            str(self.root / "build/parts/cli-stale"),
            expected_exit=1,
        )
        async with Client(create_server(self.root, allow_exports=True), mode="legacy") as client:
            mcp = await self.call(
                client,
                "prepare_parts",
                PurchasingReport,
                {
                    "project_id": "controller",
                    "view_id": "mcp-stale",
                    "native_summary": native.relative_to(self.root).as_posix(),
                },
            )
        self.receipt_equal(cli, mcp, "receipt_dir")
        self.assertEqual(mcp.status, "BLOCKED")
        self.assertIsNone(mcp.plan)
        self.assertTrue(mcp.issues)
        self.assertFalse((Path(mcp.receipt_dir) / "digikey.csv").exists())


if __name__ == "__main__":
    unittest.main()
