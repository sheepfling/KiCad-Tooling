"""Self-contained CLI/MCP parity for source-bound I2C and UART lint coverage."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from mcp import Client

from kicad_tooling.hwrepo.contracts import write_model
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    AnalysisPending,
    CatalogPaths,
    CheckEvidence,
    CommandEvidence,
    ComponentContract,
    ComponentIdentity,
    DesignLintReport,
    ElectricalAnalysisContract,
    I2cPullupAnalysis,
    I2cPullupArrayChannelRequirement,
    I2cPullupArrayRequirement,
    I2cPullupBusRequirement,
    I2cPullupLineRequirement,
    IgnoredChecks,
    PcbValidationContract,
    ProjectDiscovery,
    ProjectKind,
    ProjectManifest,
    ProjectTestContract,
    SerialDirectPeerRequirement,
    SerialEndpointRequirement,
    SerialPeerAnalysis,
    SerialPeerLinkRequirement,
    SerialPinNetRequirement,
    ToolchainRecord,
    ToolchainsCatalog,
    ToolSurfaceReport,
    ValidationSummary,
)
from kicad_tooling.validate import hashes

PROJECT_ID = "i2c-parity-fixture"
KICAD_VERSION = "10.0.5"
TOOLCHAIN_IMAGE = "synthetic-kicad:10.0.5"
NETLIST_CONTROL = """<export>
  <components>
    <comp ref="U1"><value>Synthetic two-wire target</value>
      <libsource lib="Synthetic" part="I2cTarget"/></comp>
    <comp ref="J1"><value>Synthetic mapped endpoint A</value><footprint>Synthetic:Header</footprint>
      <libsource lib="Synthetic" part="SerialHeader"/></comp>
    <comp ref="J2"><value>Synthetic mapped endpoint B</value><footprint>Synthetic:Header</footprint>
      <libsource lib="Synthetic" part="SerialHeader"/></comp>
    <comp ref="J3"><value>Synthetic unmapped endpoint</value><footprint>Synthetic:Header</footprint>
      <libsource lib="Synthetic" part="SerialHeader"/></comp>
    <comp ref="RN1"><value>4x4.7k</value><footprint>Synthetic:RA4</footprint>
      <libsource lib="Synthetic" part="ResistorArray"/></comp>
  </components>
  <libparts>
    <libpart lib="Synthetic" part="I2cTarget"><pins>
      <pin num="1" name="SDA" type="passive"/>
      <pin num="2" name="SCL" type="passive"/>
    </pins></libpart>
    <libpart lib="Synthetic" part="SerialHeader"><pins>
      <pin num="1" name="TX" type="passive"/>
      <pin num="2" name="RX" type="passive"/>
    </pins></libpart>
    <libpart lib="Synthetic" part="ResistorArray"><pins>
      <pin num="1" name="1" type="passive"/>
      <pin num="2" name="2" type="passive"/>
      <pin num="3" name="3" type="passive"/>
      <pin num="4" name="4" type="passive"/>
    </pins></libpart>
  </libparts>
  <nets>
    <net name="I2C_SDA"><node ref="U1" pin="1"/><node ref="RN1" pin="1"/></net>
    <net name="I2C_SCL"><node ref="U1" pin="2"/><node ref="RN1" pin="3"/></net>
    <net name="+3V3"><node ref="RN1" pin="2"/><node ref="RN1" pin="4"/></net>
    <net name="SERIAL_A_TX"><node ref="J1" pin="1"/><node ref="J2" pin="2"/></net>
    <net name="SERIAL_A_RX"><node ref="J1" pin="2"/><node ref="J2" pin="1"/></net>
    <net name="SERIAL_B_TX"><node ref="J3" pin="1"/></net>
    <net name="SERIAL_B_RX"><node ref="J3" pin="2"/></net>
  </nets>
</export>
"""


def alternate_function_serial_netlist() -> str:
    """Exercise UART-labeled nets on generic MCU package-pin functions."""
    netlist = NETLIST_CONTROL.replace('name="SDA"', 'name="PA2"').replace(
        'name="SCL"', 'name="PA3"'
    )
    netlist = netlist.replace(
        '<net name="I2C_SDA"><node ref="U1" pin="1"/><node ref="RN1" pin="1"/></net>',
        '<net name="UART_TX"><node ref="U1" pin="1"/><node ref="J3" pin="1"/></net>',
    )
    netlist = netlist.replace(
        '<net name="I2C_SCL"><node ref="U1" pin="2"/><node ref="RN1" pin="3"/></net>',
        '<net name="UART_RX"><node ref="U1" pin="2"/><node ref="J3" pin="2"/></net>',
    )
    return netlist


def labelled_generic_uart_reference_netlist(*, split_reference: bool) -> str:
    """Synthetic direct UART segment with generic IC pin functions."""
    references = (
        '<net name="GND_A"><node ref="U1" pin="9"/><node ref="U2" pin="9"/></net>'
        if not split_reference
        else '<net name="GND_A"><node ref="U1" pin="9"/></net>'
        '<net name="GND_B"><node ref="U2" pin="9"/></net>'
    )
    return f"""<export>
  <components>
    <comp ref="U1"><value>Synthetic translator</value><footprint>Package:UART-TX</footprint>
      <libsource lib="Synthetic" part="UartTransmitter"/></comp>
    <comp ref="U2"><value>Synthetic serial bridge</value><footprint>Package:UART-RX</footprint>
      <libsource lib="Synthetic" part="UartReceiver"/></comp>
  </components>
  <libparts>
    <libpart lib="Synthetic" part="UartTransmitter"><pins>
      <pin num="1" name="B2" type="tri_state"/><pin num="2" name="B1" type="tri_state"/>
      <pin num="8" name="VDD" type="power_in"/><pin num="9" name="GND" type="power_in"/>
    </pins></libpart>
    <libpart lib="Synthetic" part="UartReceiver"><pins>
      <pin num="1" name="ADBUS0" type="bidirectional"/>
      <pin num="2" name="ADBUS1" type="bidirectional"/>
      <pin num="8" name="VDD" type="power_in"/><pin num="9" name="GND" type="power_in"/>
    </pins></libpart>
  </libparts>
  <nets>
    <net name="Compute module/UART.0.TX"><node ref="U1" pin="1"/><node ref="U2" pin="2"/></net>
    <net name="Compute module/UART.0.RX"><node ref="U1" pin="2"/><node ref="U2" pin="1"/></net>
    <net name="+3V3"><node ref="U1" pin="8"/><node ref="U2" pin="8"/></net>
    {references}
  </nets>
</export>
"""


NETLIST_MISSING_ARRAY = """<export>
  <components>
    <comp ref="U1"><value>Synthetic two-wire target</value>
      <libsource lib="Synthetic" part="I2cTarget"/></comp>
    <comp ref="J1"><value>Synthetic mapped endpoint A</value><footprint>Synthetic:Header</footprint>
      <libsource lib="Synthetic" part="SerialHeader"/></comp>
    <comp ref="J2"><value>Synthetic mapped endpoint B</value><footprint>Synthetic:Header</footprint>
      <libsource lib="Synthetic" part="SerialHeader"/></comp>
    <comp ref="J3"><value>Synthetic unmapped endpoint</value><footprint>Synthetic:Header</footprint>
      <libsource lib="Synthetic" part="SerialHeader"/></comp>
  </components>
  <libparts>
    <libpart lib="Synthetic" part="I2cTarget"><pins>
      <pin num="1" name="SDA" type="passive"/>
      <pin num="2" name="SCL" type="passive"/>
    </pins></libpart>
    <libpart lib="Synthetic" part="SerialHeader"><pins>
      <pin num="1" name="TX" type="passive"/>
      <pin num="2" name="RX" type="passive"/>
    </pins></libpart>
  </libparts>
  <nets>
    <net name="I2C_SDA"><node ref="U1" pin="1"/></net>
    <net name="I2C_SCL"><node ref="U1" pin="2"/></net>
    <net name="SERIAL_A_TX"><node ref="J1" pin="1"/><node ref="J2" pin="2"/></net>
    <net name="SERIAL_A_RX"><node ref="J1" pin="2"/><node ref="J2" pin="1"/></net>
    <net name="SERIAL_B_TX"><node ref="J3" pin="1"/></net>
    <net name="SERIAL_B_RX"><node ref="J3" pin="2"/></net>
  </nets>
</export>
"""


def dual_uart_reference_netlist(*, split_first_return: bool) -> str:
    """Synthetic dual-UART MCU netlist with one optional split connector return."""
    first_return = "GND_B" if split_first_return else "GND_A"
    first_return_node = "" if split_first_return else '<node ref="J1" pin="4"/>'
    split_return_net = (
        f'<net name="{first_return}"><node ref="J1" pin="4"/></net>' if split_first_return else ""
    )
    return f"""<export>
  <components>
    <comp ref="U1"><value>Synthetic two-wire target</value>
      <footprint>Synthetic:Controller</footprint>
      <libsource lib="Synthetic" part="DualUartI2cTarget"/></comp>
    <comp ref="J1"><value>Synthetic mapped endpoint A</value><footprint>Synthetic:Header</footprint>
      <libsource lib="Synthetic" part="SerialHeaderPower"/></comp>
    <comp ref="J2"><value>Synthetic mapped endpoint B</value><footprint>Synthetic:Header</footprint>
      <libsource lib="Synthetic" part="SerialHeaderPower"/></comp>
    <comp ref="J3"><value>Synthetic unmapped endpoint</value><footprint>Synthetic:Header</footprint>
      <libsource lib="Synthetic" part="SerialHeader"/></comp>
    <comp ref="RN1"><value>4x4.7k</value><footprint>Synthetic:RA4</footprint>
      <libsource lib="Synthetic" part="ResistorArray"/></comp>
  </components>
  <libparts>
    <libpart lib="Synthetic" part="DualUartI2cTarget"><pins>
      <pin num="1" name="SDA" type="passive"/>
      <pin num="2" name="SCL" type="passive"/>
      <pin num="3" name="VDD" type="power_in"/>
      <pin num="4" name="GND" type="power_in"/>
      <pin num="5" name="UART1_TX" type="output"/>
      <pin num="6" name="UART1_RX" type="input"/>
      <pin num="7" name="UART2_TX" type="output"/>
      <pin num="8" name="UART2_RX" type="input"/>
    </pins></libpart>
    <libpart lib="Synthetic" part="SerialHeaderPower"><pins>
      <pin num="1" name="TX" type="output"/>
      <pin num="2" name="RX" type="input"/>
      <pin num="3" name="VDD" type="passive"/>
      <pin num="4" name="GND" type="passive"/>
    </pins></libpart>
    <libpart lib="Synthetic" part="SerialHeader"><pins>
      <pin num="1" name="TX" type="passive"/>
      <pin num="2" name="RX" type="passive"/>
    </pins></libpart>
    <libpart lib="Synthetic" part="ResistorArray"><pins>
      <pin num="1" name="1" type="passive"/>
      <pin num="2" name="2" type="passive"/>
      <pin num="3" name="3" type="passive"/>
      <pin num="4" name="4" type="passive"/>
    </pins></libpart>
  </libparts>
  <nets>
    <net name="I2C_SDA"><node ref="U1" pin="1"/><node ref="RN1" pin="1"/></net>
    <net name="I2C_SCL"><node ref="U1" pin="2"/><node ref="RN1" pin="3"/></net>
    <net name="+3V3"><node ref="U1" pin="3"/><node ref="RN1" pin="2"/>
      <node ref="RN1" pin="4"/><node ref="J1" pin="3"/><node ref="J2" pin="3"/></net>
    <net name="UART1_TX"><node ref="U1" pin="5"/><node ref="J1" pin="2"/></net>
    <net name="UART1_RX"><node ref="U1" pin="6"/><node ref="J1" pin="1"/></net>
    <net name="UART2_TX"><node ref="U1" pin="7"/><node ref="J2" pin="2"/></net>
    <net name="UART2_RX"><node ref="U1" pin="8"/><node ref="J2" pin="1"/></net>
    <net name="GND_A"><node ref="U1" pin="4"/><node ref="J2" pin="4"/>
      {first_return_node}</net>
    {split_return_net}
    <net name="SERIAL_B_TX"><node ref="J3" pin="1"/></net>
    <net name="SERIAL_B_RX"><node ref="J3" pin="2"/></net>
  </nets>
</export>
"""


def dual_uart_separate_reference_map() -> SerialPeerAnalysis:
    """Record an intentionally separate reference for one direct UART port."""
    controller = SerialEndpointRequirement(
        id="controller-uart1",
        reference="U1",
        symbol="Synthetic:DualUartI2cTarget",
        footprint="Synthetic:Controller",
        logic_domain="3V3",
        tx=SerialPinNetRequirement(pin="U1.5", net="UART1_TX"),
        rx=SerialPinNetRequirement(pin="U1.6", net="UART1_RX"),
        reference_pins=(SerialPinNetRequirement(pin="U1.4", net="GND_A"),),
    )
    header = SerialEndpointRequirement(
        id="header-uart1",
        reference="J1",
        symbol="Synthetic:SerialHeaderPower",
        footprint="Synthetic:Header",
        logic_domain="3V3",
        tx=SerialPinNetRequirement(pin="J1.1", net="UART1_RX"),
        rx=SerialPinNetRequirement(pin="J1.2", net="UART1_TX"),
        reference_pins=(SerialPinNetRequirement(pin="J1.4", net="GND_B"),),
    )
    return SerialPeerAnalysis(
        basis="Synthetic project-reviewed isolated UART reference domains",
        links=(
            SerialPeerLinkRequirement(
                id="controller-uart1-header",
                basis="Synthetic direct UART endpoint map",
                endpoint=controller,
                peer=SerialDirectPeerRequirement(mode="direct", endpoint=header),
                reference_policy="separate_nets",
            ),
        ),
    )


def electrical_contract() -> ElectricalAnalysisContract:
    """State the intended pull-up topology independently of the netlist fixture."""
    pullups = I2cPullupAnalysis(
        basis="Synthetic I2C interface requirement authored for parity regression",
        buses=(
            I2cPullupBusRequirement(
                id="main",
                basis="Synthetic two-wire target interface",
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
                basis="Synthetic resistor-array channel map",
                channels=(
                    I2cPullupArrayChannelRequirement(
                        id="sda",
                        signal_pin="RN1.1",
                        rail_pin="RN1.2",
                        signal_net="I2C_SDA",
                        rail_net="+3V3",
                        resistance_ohms=4_700,
                        basis="Synthetic channel 1 mapping",
                    ),
                    I2cPullupArrayChannelRequirement(
                        id="scl",
                        signal_pin="RN1.3",
                        rail_pin="RN1.4",
                        signal_net="I2C_SCL",
                        rail_net="+3V3",
                        resistance_ohms=4_700,
                        basis="Synthetic channel 2 mapping",
                    ),
                ),
            ),
        ),
    )
    endpoint_a = SerialEndpointRequirement(
        id="endpoint-a",
        reference="J1",
        symbol="Synthetic:SerialHeader",
        footprint="Synthetic:Header",
        logic_domain="3V3",
        tx=SerialPinNetRequirement(pin="J1.1", net="SERIAL_A_TX"),
        rx=SerialPinNetRequirement(pin="J1.2", net="SERIAL_A_RX"),
    )
    endpoint_b = SerialEndpointRequirement(
        id="endpoint-b",
        reference="J2",
        symbol="Synthetic:SerialHeader",
        footprint="Synthetic:Header",
        logic_domain="3V3",
        tx=SerialPinNetRequirement(pin="J2.1", net="SERIAL_A_RX"),
        rx=SerialPinNetRequirement(pin="J2.2", net="SERIAL_A_TX"),
    )
    serial_peers = SerialPeerAnalysis(
        basis="Synthetic reviewed UART peer map for parity coverage",
        links=(
            SerialPeerLinkRequirement(
                id="mapped-console",
                basis="Synthetic two-connector direct UART link",
                endpoint=endpoint_a,
                peer=SerialDirectPeerRequirement(mode="direct", endpoint=endpoint_b),
                reference_policy="not_applicable",
            ),
        ),
    )
    return ElectricalAnalysisContract(
        project_id=PROJECT_ID,
        ngspice_version="not run by synthetic parity fixture",
        grounding=AnalysisPending(reason="Grounding is outside this synthetic fixture."),
        i2c_pullups=pullups,
        serial_peers=serial_peers,
        power=AnalysisPending(reason="Power analysis is outside this synthetic fixture."),
        high_frequency=AnalysisPending(
            reason="High-frequency analysis is outside this synthetic fixture."
        ),
    )


class DesignLintI2cParityTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="design-lint-i2c-parity-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve() / "repository"
        self.island = self.root / "projects" / PROJECT_ID
        self.source = self.island / "source" / "fixture.json"
        self.native = self.root / "build" / "native" / PROJECT_ID
        self.summary_path = self.native / "summary.json"
        self.netlist_path = self.native / "netlist.xml"
        self.root.mkdir(parents=True)
        self.source.parent.mkdir(parents=True)
        self.native.mkdir(parents=True)
        self._write_repository_configuration()
        self.source.write_text(
            json.dumps({"fixture": "synthetic", "scenario": "control"}) + "\n",
            encoding="utf-8",
        )
        write_model(self.island / "tests" / "contract.json", self._project_contract())
        write_model(self.island / "tests" / "electrical.json", electrical_contract())

    def _project_contract(self) -> ProjectTestContract:
        return ProjectTestContract(
            validation=PcbValidationContract(
                kind=ProjectKind.PCB,
                components={
                    "U1": ComponentContract(value="Synthetic two-wire target", footprint=""),
                    "J1": ComponentContract(
                        value="Synthetic mapped endpoint A", footprint="Synthetic:Header"
                    ),
                    "J2": ComponentContract(
                        value="Synthetic mapped endpoint B", footprint="Synthetic:Header"
                    ),
                    "J3": ComponentContract(
                        value="Synthetic unmapped endpoint", footprint="Synthetic:Header"
                    ),
                    "RN1": ComponentContract(value="4x4.7k", footprint="Synthetic:RA4"),
                },
                nets={
                    "I2C_SDA": ("U1.1", "RN1.1"),
                    "I2C_SCL": ("U1.2", "RN1.3"),
                    "+3V3": ("RN1.2", "RN1.4"),
                    "SERIAL_A_TX": ("J1.1", "J2.2"),
                    "SERIAL_A_RX": ("J1.2", "J2.1"),
                    "SERIAL_B_TX": ("J3.1",),
                    "SERIAL_B_RX": ("J3.2",),
                },
                expected_ignored_checks=IgnoredChecks(erc=(), drc=()),
            ),
            electrical="tests/electrical.json",
        )

    def _write_repository_configuration(self) -> None:
        (self.root / "catalog").mkdir(parents=True, exist_ok=True)
        (self.island / "tests").mkdir(parents=True, exist_ok=True)
        catalogs = CatalogPaths(
            parts="catalog/parts.json",
            interfaces="catalog/interfaces.json",
            libraries="catalog/libraries.json",
            toolchains="catalog/toolchains.json",
            release_policies="catalog/release-policies.json",
        )
        write_model(
            self.root / "catalog" / "projects.json",
            ProjectDiscovery(catalogs=catalogs, project_roots=("projects",), project_depth=1),
        )
        write_model(
            self.root / "catalog" / "toolchains.json",
            ToolchainsCatalog(
                schema_version="1",
                toolchains=(
                    ToolchainRecord(
                        id="synthetic-kicad-10-0-5",
                        kicad_version=KICAD_VERSION,
                        image=TOOLCHAIN_IMAGE,
                        desktop_edit_policy="Synthetic fixture only",
                        installer_source="Synthetic fixture only",
                        migration_policy="Synthetic fixture only",
                    ),
                ),
            ),
        )
        write_model(
            self.island / "project.json",
            ProjectManifest(
                id=PROJECT_ID,
                kind=ProjectKind.PCB,
                status="training_fixture",
                assurance_profile="training",
                toolchain_id="synthetic-kicad-10-0-5",
                project="design.kicad_pro",
                source_roots=("source",),
                required_inputs=("source/fixture.json",),
                component_identity=ComponentIdentity(required=False, part_ids=()),
            ),
        )

    def _write_native_evidence(
        self, *, missing_array: bool, netlist_xml: str | None = None
    ) -> None:
        scenario = "missing-pull-up-array" if missing_array else "mapped-array-control"
        if netlist_xml is not None:
            scenario = "alternate-function-uart-labels"
        self.source.write_text(
            json.dumps({"fixture": "synthetic", "scenario": scenario}) + "\n",
            encoding="utf-8",
        )
        self.netlist_path.write_text(
            netlist_xml
            if netlist_xml is not None
            else NETLIST_MISSING_ARRAY
            if missing_array
            else NETLIST_CONTROL,
            encoding="utf-8",
        )
        command = CommandEvidence(
            argv=("synthetic-netlist-fixture", scenario),
            started_utc="2026-09-30T00:00:00+00:00",
            returncode=0,
        )
        write_model(self.native / "netlist.command.json", command)
        source_hashes = hashes(self.root, (f"projects/{PROJECT_ID}/source",))
        write_model(
            self.summary_path,
            ValidationSummary(
                timestamp_utc="2026-09-30T00:00:00+00:00",
                checked_commit="SYNTHETIC_FIXTURE_NOT_A_RELEASE_COMMIT",
                project_id=PROJECT_ID,
                project_kind=ProjectKind.PCB,
                checks={
                    "source_scope": CheckEvidence(status="PASS", source_hashes=source_hashes),
                    "source_unchanged": CheckEvidence(status="PASS", source_hashes=source_hashes),
                    "toolchain": CheckEvidence(
                        status="PASS",
                        observed_version=KICAD_VERSION,
                        image=TOOLCHAIN_IMAGE,
                    ),
                    "netlist": CheckEvidence(
                        status="FAIL" if missing_array else "PASS",
                        returncode=0,
                        error=("Synthetic missing-array fault" if missing_array else None),
                    ),
                },
                status="FAIL" if missing_array else "PASS",
                artifacts_sha256={
                    "netlist.xml": digest(self.netlist_path),
                    "netlist.command.json": digest(self.native / "netlist.command.json"),
                },
            ),
        )

    async def _inspect_both_surfaces(self, client: Client) -> DesignLintReport:
        native_relative = self.summary_path.relative_to(self.root).as_posix()
        mcp_result = await client.call_tool(
            "inspect_design_lint",
            {"project_id": PROJECT_ID, "native_summary": native_relative},
        )
        self.assertFalse(mcp_result.is_error, mcp_result.content)
        self.assertIsNotNone(mcp_result.structured_content)
        mcp_report = DesignLintReport.model_validate_json(json.dumps(mcp_result.structured_content))

        process = await asyncio.to_thread(
            subprocess.run,
            (
                sys.executable,
                "-I",
                "-B",
                "-m",
                "kicad_tooling.design_lint",
                "--root",
                str(self.root),
                "--project",
                PROJECT_ID,
                "--native-summary",
                str(self.summary_path),
                "--format",
                "json",
            ),
            cwd=self.root.parent,
            env=os.environ.copy(),
            text=True,
            capture_output=True,
            check=False,
            timeout=60,
        )
        self.assertIn(process.returncode, (0, 1), process.stderr + process.stdout)
        cli_report = DesignLintReport.model_validate_json(process.stdout)
        self.assertEqual(process.returncode, int(cli_report.status != "PASS"), process.stderr)
        self.assertEqual(cli_report, mcp_report)
        return mcp_report

    async def _check_surface_registration(self) -> None:
        process = await asyncio.to_thread(
            subprocess.run,
            (
                sys.executable,
                "-I",
                "-B",
                "-m",
                "kicad_tooling.surface",
                "--root",
                str(self.root),
                "--require-live-mcp",
                "--format",
                "json",
            ),
            cwd=self.root.parent,
            env=os.environ.copy(),
            text=True,
            capture_output=True,
            check=False,
            timeout=60,
        )
        self.assertEqual(process.returncode, 0, process.stderr + process.stdout)
        surface = ToolSurfaceReport.model_validate_json(process.stdout)
        self.assertEqual(surface.parity_status, "PASS", surface.issues)
        self.assertEqual(surface.mcp_verification, "LIVE")

    async def test_mapped_array_control_and_missing_array_fault_match_cli_and_mcp(self) -> None:
        async with Client(create_server(self.root), mode="legacy") as client:
            self._write_native_evidence(missing_array=False)
            control = await self._inspect_both_surfaces(client)
            self.assertEqual(control.i2c_pullup_heuristic_coverage.status, "COMPLETE")
            self.assertEqual(
                control.i2c_pullup_heuristic_coverage.netlist_sha256,
                digest(self.netlist_path),
            )
            self.assertEqual(
                control.i2c_pullup_heuristic_coverage.entries[0].check_ids,
                ("i2c-pullup/main/sda", "i2c-pullup/main/scl"),
            )
            self.assertNotIn("bus.i2c_missing_pullup", {item.rule_id for item in control.findings})
            serial_findings = [
                item for item in control.findings if item.rule_id == "bus.serial_unmapped_peer"
            ]
            self.assertEqual(
                tuple(item.subject for item in serial_findings),
                ("J3: serial-peer map coverage (TX/RX)",),
            )
            self.assertIn("not listed in the project serial-peer map", serial_findings[0].message)
            self.assertEqual(
                serial_findings[0].evidence["electrical_contract_path"],
                (f"projects/{PROJECT_ID}/tests/electrical.json",),
            )
            self.assertEqual(
                serial_findings[0].evidence["electrical_contract_sha256"],
                (digest(self.island / "tests" / "electrical.json"),),
            )

            self._write_native_evidence(missing_array=True)
            fault = await self._inspect_both_surfaces(client)
            self.assertEqual(fault.i2c_pullup_heuristic_coverage.status, "OPEN")
            self.assertEqual(
                fault.i2c_pullup_heuristic_coverage.netlist_sha256,
                digest(self.netlist_path),
            )
            self.assertIn("bus.i2c_missing_pullup", {item.rule_id for item in fault.findings})
            self.assertEqual(
                tuple(
                    item.subject
                    for item in fault.findings
                    if item.rule_id == "bus.serial_unmapped_peer"
                ),
                ("J3: serial-peer map coverage (TX/RX)",),
            )
            await self._check_surface_registration()

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
        from tests.test_electrical_parity import contract_netlist_xml
        from tests.test_serial_peer_reference_review import (
            bonded_serial_reference_netlist,
            serial_peer_map,
        )

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


if __name__ == "__main__":
    unittest.main()
