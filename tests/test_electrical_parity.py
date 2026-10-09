"""CLI/protocol electrical parity, source authority and bounded input regressions."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree as ET

from mcp import Client

from kicad_tooling.hwrepo import electrical_setup, mcp_electrical, mcp_files
from kicad_tooling.hwrepo.contracts import read_model, repo_path, write_model
from kicad_tooling.hwrepo.electrical import regular_input_bytes, selected_config, simulation_cases
from kicad_tooling.hwrepo.electrical_runner import analyze
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    ContractCoachReport,
    ElectricalAnalysisContract,
    ElectricalAnalysisReport,
    ElectricalInputInventory,
    ElectricalSetupReport,
    ElectricalSuiteReport,
    ExcludedTestAccess,
    GroundDomain,
    GroundingAnalysis,
    I2cPullupAnalysis,
    MosfetOperatingState,
    MosfetVoltageInterval,
    NetlistContract,
    PcbAccessAnalysis,
    PcbReturnDomainRequirement,
    PcbReturnEndpointRequirement,
    PcbReturnPathsAnalysis,
    PinConnectivityAnalysis,
    PinRelationshipRule,
    ProjectVerificationReport,
    RequiredTestAccess,
    TemplateDoctorReport,
    ValidationSummary,
)
from kicad_tooling.hwrepo.models import (
    TestAccessAnalysis as AccessAnalysis,
)
from kicad_tooling.hwrepo.models import (
    TestAccessEndpointRequirement as AccessEndpointRequirement,
)
from kicad_tooling.hwrepo.models import (
    TestAccessProbeEnvelope as AccessProbeEnvelope,
)
from kicad_tooling.hwrepo.spice import expanded_deck
from kicad_tooling.validate import hashes
from tests import test_contract_coach as coach_fixture
from tests.support import initialize_git
from tests.test_component_power_ratings import (
    netlist as component_power_netlist,
)
from tests.test_component_power_ratings import (
    requirement as component_power_requirement,
)
from tests.test_component_voltage_ratings import (
    netlist as component_voltage_netlist,
)
from tests.test_component_voltage_ratings import (
    requirement as component_voltage_requirement,
)
from tests.test_connector_contact_ratings import (
    contact as connector_contact,
)
from tests.test_connector_contact_ratings import (
    native_netlist_xml as connector_contact_netlist_xml,
)
from tests.test_connector_contact_ratings import (
    requirement as connector_contact_requirement,
)
from tests.test_contract_coach import fake_executable
from tests.test_control_inputs import control_netlist, control_requirement
from tests.test_digital_peer_voltages import (
    observed as digital_peer_netlist,
)
from tests.test_digital_peer_voltages import (
    requirement as digital_peer_requirement,
)
from tests.test_electrical import (
    ISLAND,
    NA,
    PROJECT,
    can_split_termination_requirement,
    i2c_pullup_array_netlist,
    i2c_pullup_array_requirement,
    i2c_pullup_requirement,
    i2c_pullup_voltage_requirement,
    i2c_pullup_window_requirement,
    i2c_series_pullup_netlist,
    i2c_series_pullup_requirement,
    install_fixture,
    power_connectivity_netlist,
    power_connectivity_requirement,
    rs485_netlist,
    rs485_requirement,
    serial_peer_netlist,
    serial_peer_requirement,
    spi_requirement,
    usb_c_netlist,
    usb_c_requirement,
)
from tests.test_mosfet_stress import multi_device_netlist as mosfet_stress_multi_device_netlist
from tests.test_mosfet_stress import (
    multi_device_requirement as mosfet_stress_multi_device_requirement,
)
from tests.test_source_parity import source_bytes


def contract_netlist_xml(observed: NetlistContract) -> str:
    root = ET.Element("export")
    components = ET.SubElement(root, "components")
    library_pins: dict[tuple[str, str], dict[str, str]] = {}
    library_pin_types: dict[tuple[str, str], dict[str, str]] = {}
    symbols = observed.component_symbols
    for reference, component in observed.components.items():
        symbol = symbols[reference]
        library, part = symbol.split(":", maxsplit=1)
        library_pins.setdefault((library, part), {})
        library_pin_types.setdefault((library, part), {})
        entry = ET.SubElement(components, "comp", ref=reference)
        ET.SubElement(entry, "value").text = component.value
        ET.SubElement(entry, "footprint").text = component.footprint
        if component.part_id is not None:
            fields = ET.SubElement(entry, "fields")
            ET.SubElement(fields, "field", name="PART_ID").text = component.part_id
        if reference in observed.dnp_components:
            ET.SubElement(entry, "property", name="dnp", value="true")
        ET.SubElement(entry, "libsource", lib=library, part=part)
        units = ET.SubElement(entry, "units")
        unit = ET.SubElement(units, "unit", name="A")
        pins = ET.SubElement(unit, "pins")
        for number in observed.component_pin_numbers.get(reference, ()):
            ET.SubElement(pins, "pin", num=number)
            library_pins[(library, part)][number] = observed.pin_functions.get(
                f"{reference}.{number}", number
            )
            library_pin_types[(library, part)][number] = observed.pin_electrical_types.get(
                f"{reference}.{number}", "passive"
            )
    libparts = ET.SubElement(root, "libparts")
    for (library, part), pin_functions in sorted(library_pins.items()):
        libpart = ET.SubElement(libparts, "libpart", lib=library, part=part)
        pins = ET.SubElement(libpart, "pins")
        for number, name in sorted(pin_functions.items()):
            ET.SubElement(
                pins,
                "pin",
                num=number,
                name=name,
                type=library_pin_types[(library, part)].get(number, "passive"),
            )
    nets = ET.SubElement(root, "nets")
    for net_name, assignments in sorted(observed.nets.items()):
        net = ET.SubElement(nets, "net", name=net_name)
        for pin in assignments:
            reference, number = pin.rsplit(".", 1)
            ET.SubElement(net, "node", ref=reference, pin=number)
    return ET.tostring(root, encoding="unicode")


def four_port_db9_netlist(*, isolated_returns: bool) -> NetlistContract:
    """Build synthetic DB9 netlist evidence for common or isolated returns."""
    references = tuple(f"J{index}" for index in range(1, 5))
    return_nets = (
        {f"RETURN_PORT_{index}": (f"J{index}.7", f"J{index}.9") for index in range(1, 5)}
        if isolated_returns
        else {"COMMON_RETURN": tuple(f"J{index}.{pin}" for index in range(1, 5) for pin in (7, 9))}
    )
    return NetlistContract(
        components={
            reference: ComponentContract(value="DB9", footprint="Synthetic:DB9")
            for reference in references
        },
        nets=return_nets,
        component_symbols={reference: "Synthetic:DB9" for reference in references},
        component_pin_numbers={
            reference: tuple(str(pin) for pin in range(1, 10)) for reference in references
        },
        pin_functions={
            f"{reference}.{pin}": "GND" if pin in {7, 9} else str(pin)
            for reference in references
            for pin in range(1, 10)
        },
    )


def testpoint_board_source() -> str:
    return (
        '(kicad_pcb (version 20250114) (net 0 "") (net 1 "+3V3") (net 2 "OTHER") '
        '(footprint "TestPoint:TestPoint_Pad_D1.0mm" (layer "F.Cu") '
        '(property "Reference" "TP1") '
        '(pad "1" smd circle (at 0 0) (size 1 1) '
        '(layers "F.Cu" "F.Mask") (net 1 "+3V3"))) '
        '(footprint "Synthetic:Obstacle" (layer "F.Cu") (at 1 0) '
        '(property "Reference" "TP2") '
        '(pad "1" smd circle (at 0 0) (size 1 1) '
        '(layers "F.Cu" "F.Mask") (net 2 "OTHER"))))'
    )


class ElectricalParityTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.fixture = coach_fixture.ContractCoachTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root
        self.mcp_root = self.root.parent / "mcp-repository"
        shutil.copytree(self.root, self.mcp_root)

    async def cli(self, module: str, *arguments: str) -> subprocess.CompletedProcess[str]:
        return await asyncio.to_thread(
            subprocess.run,
            (
                sys.executable,
                "-B",
                "-I",
                "-m",
                module,
                "--root",
                str(self.root),
                *arguments,
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

    def configured(self, *, simulation: bool = False, grounding: bool = False) -> None:
        for root in (self.root, self.mcp_root):
            contract = install_fixture(root)
            contract = contract.model_copy(
                update={
                    "grounding": GroundingAnalysis(
                        basis="Synthetic independently authored pin review",
                        domains=(GroundDomain(net="PILOT_C", pins=("R1.2", "R3.2")),),
                    )
                    if grounding
                    else NA,
                    "high_frequency": NA,
                    **({} if simulation else {"power": NA}),
                }
            )
            write_model(root / ISLAND / "tests/electrical.json", contract)

    async def test_init_and_capture_match_cli_without_approving_requirements(self) -> None:
        before = source_bytes(self.root)
        process = await self.cli("kicad_tooling.electrical", "--project", PROJECT, "--init")
        self.assertEqual(process.returncode, 0, process.stderr + process.stdout)
        cli_setup = ElectricalSetupReport.model_validate_json(process.stdout)
        async with Client(create_server(self.mcp_root, allow_edits=True), mode="legacy") as client:
            result = await client.call_tool("init_electrical", {"project_id": PROJECT})
            self.assertFalse(result.is_error, result.content)
            mcp_setup = ElectricalSetupReport.model_validate_json(
                json.dumps(result.structured_content)
            )
            again = await client.call_tool("init_electrical", {"project_id": PROJECT})
            self.assertTrue(again.is_error)
        self.assertEqual(cli_setup, mcp_setup)
        self.assertFalse(mcp_setup.build_authorized)
        self.assertEqual(source_bytes(self.root), source_bytes(self.mcp_root))
        after = source_bytes(self.root)
        self.assertEqual(
            {name for name in before if before[name] != after[name]},
            {f"{ISLAND}/tests/contract.json"},
        )
        self.assertEqual(set(after) - set(before), {f"{ISLAND}/tests/electrical.json"})
        contract = read_model(self.root / cli_setup.contract, ElectricalAnalysisContract)
        self.assertEqual(
            [
                contract.grounding.mode,
                contract.pcb_return_paths.mode,
                contract.pin_connectivity.mode if contract.pin_connectivity else None,
                contract.i2c_pullups.mode if contract.i2c_pullups else None,
                contract.can_termination.mode if contract.can_termination else None,
                contract.usb_c.mode if contract.usb_c else None,
                contract.spi.mode if contract.spi else None,
                contract.serial_peers.mode if contract.serial_peers else None,
                contract.rs485.mode if contract.rs485 else None,
                contract.control_inputs.mode if contract.control_inputs else None,
                contract.test_access.mode if contract.test_access else None,
                contract.power.mode,
                contract.high_frequency.mode,
            ],
            ["pending"] * 13,
        )
        name = f"{ISLAND}/tests/draft.cir"
        for root in (self.root, self.mcp_root):
            (root / name).write_text(
                "Synthetic unreviewed model\nR1 in 0 1k\n.end\n", encoding="utf-8"
            )
        before = source_bytes(self.root)
        process = await self.cli(
            "kicad_tooling.electrical",
            "--project",
            PROJECT,
            "--capture-inputs",
            "--model",
            name,
            "--output",
            "build/electrical-inputs/parity",
        )
        self.assertEqual(process.returncode, 0, process.stderr + process.stdout)
        cli_capture = ElectricalInputInventory.model_validate_json(process.stdout)
        async with Client(
            create_server(self.mcp_root, allow_exports=True), mode="legacy"
        ) as client:
            result = await client.call_tool(
                "capture_electrical_inputs",
                {
                    "project_id": PROJECT,
                    "view_id": "parity",
                    "models": [name],
                },
            )
            self.assertFalse(result.is_error, result.content)
            mcp_capture = ElectricalInputInventory.model_validate_json(
                json.dumps(result.structured_content)
            )
            collision = await client.call_tool(
                "capture_electrical_inputs",
                {
                    "project_id": PROJECT,
                    "view_id": "parity",
                    "models": [name],
                },
            )
            self.assertTrue(collision.is_error)
        self.assertEqual(
            cli_capture.model_copy(update={"run_directory": ""}),
            mcp_capture.model_copy(update={"run_directory": ""}),
        )
        self.assertEqual(mcp_capture.status, "UNREVIEWED")
        self.assertFalse(mcp_capture.build_authorized)
        self.assertEqual(mcp_capture.model_sha256, {name: digest(self.root / name)})
        self.assertEqual(source_bytes(self.root), before)
        self.assertEqual(source_bytes(self.mcp_root), before)

    async def test_saved_native_analysis_is_root_relative_and_preserves_native_failure(
        self,
    ) -> None:
        self.configured(grounding=True)
        before = source_bytes(self.root)
        summary = "build/native/controller/summary.json"
        process = await self.cli(
            "kicad_tooling.electrical",
            "--project",
            PROJECT,
            "--native-summary",
            summary,
            "--output",
            "build/electrical/saved",
        )
        self.assertEqual(process.returncode, 0, process.stderr + process.stdout)
        cli_report = ElectricalAnalysisReport.model_validate_json(process.stdout)
        async with Client(create_server(self.mcp_root, allow_checks=True), mode="legacy") as client:
            result = await client.call_tool(
                "analyze_electrical",
                {
                    "project_id": PROJECT,
                    "view_id": "saved",
                    "native_summary": summary,
                },
            )
        self.assertFalse(result.is_error, result.content)
        mcp_report = ElectricalAnalysisReport.model_validate_json(
            json.dumps(result.structured_content)
        )
        self.assertEqual(cli_report.checks, mcp_report.checks)
        self.assertEqual(cli_report.input_sha256, mcp_report.input_sha256)
        for report in (cli_report, mcp_report):
            self.assertEqual(report.status, "PASS")
            self.assertFalse(report.build_authorized)
            self.assertEqual(report.commands, {})
            evidence = read_model(
                Path(report.run_directory) / "netlist-evidence.json", ContractCoachReport
            )
            self.assertEqual(evidence.native_status, "FAIL")
            self.assertEqual(evidence.review_state, "UNREVIEWED")
            self.assertFalse(evidence.build_authorized)
        self.assertEqual(source_bytes(self.root), before)
        self.assertEqual(source_bytes(self.mcp_root), before)

    async def test_pcb_return_path_contract_matches_cli_and_mcp_for_pass_and_fault(self) -> None:
        self.configured()
        requirement = PcbReturnPathsAnalysis(
            basis="Synthetic independently reviewed connector return pinout",
            domains=(
                PcbReturnDomainRequirement(
                    id="serial-returns",
                    basis="Synthetic DB9 common-return requirement",
                    topology="direct",
                    endpoints=(
                        PcbReturnEndpointRequirement(
                            pad="J1.7", net="0V_PWM", footprint="Synthetic:DB9"
                        ),
                        PcbReturnEndpointRequirement(
                            pad="J2.7", net="0V_PWM", footprint="Synthetic:DB9"
                        ),
                    ),
                ),
            ),
        )
        board_source = (
            '(kicad_pcb (version 20250114) (net 0 "") (net 1 "0V_PWM") '
            '(footprint "Synthetic:DB9" (layer "F.Cu") (property "Reference" "J1") '
            '(pad "7" thru_hole circle (at 0 0) (size 1 1) '
            '(layers "*.Cu" "*.Mask") (net 1 "0V_PWM"))) '
            '(footprint "Synthetic:DB9" (layer "F.Cu") (property "Reference" "J2") '
            '(pad "7" thru_hole circle (at 2 0) (size 1 1) '
            '(layers "*.Cu" "*.Mask") (net 1 "0V_PWM"))))'
        )
        config = selected_config(self.root, PROJECT)
        for root in (self.root, self.mcp_root):
            contract_path = root / ISLAND / "tests/electrical.json"
            contract = read_model(contract_path, ElectricalAnalysisContract).model_copy(
                update={"pcb_return_paths": requirement}
            )
            write_model(contract_path, contract)
            board_path = repo_path(root, config.project).with_suffix(".kicad_pcb")
            board_path.write_text(board_source, encoding="utf-8")

        fake_bin = self.root.parent / "fake-pcb-docker"
        fake_bin.mkdir()
        fake_docker = fake_executable(
            fake_bin / "docker",
            "from __future__ import annotations\n"
            "import hashlib, json, os, sys\n"
            "from pathlib import Path\n"
            "args = sys.argv[1:]\n"
            "work = Path(next(arg[:-len(':/work:ro')] for arg in args if arg.endswith(':/work:ro')))\n"
            "output = Path(next(arg[:-len(':/output:rw')] for arg in args if arg.endswith(':/output:rw')))\n"
            "board = work / args[-2].removeprefix('/work/')\n"
            "snapshot = output / args[-1].removeprefix('/output/')\n"
            "connected = os.environ.get('FAKE_PCB_CONNECTIVITY') == 'connected'\n"
            "group = ['J1.7', 'J2.7'] if connected else None\n"
            "rows = []\n"
            "for name in ('J1.7', 'J2.7'):\n"
            "    rows.append({'pad': name, 'net': '0V_PWM', 'footprint': 'Synthetic:DB9', "
            "'dnp': False, 'connected_pads': group or [name], 'connected_zones': [], "
            "'connected_islands': []})\n"
            "data = {'schema_version': '2', 'board_sha256': hashlib.sha256(board.read_bytes()).hexdigest(), "
            f"'kicad_version': {config.kicad_version!r}, "
            "'zones_refilled': True, 'pads': rows, 'net_ties': [], 'zones': []}\n"
            "snapshot.write_text(json.dumps(data, sort_keys=True), encoding='utf-8')\n",
        )
        before = source_bytes(self.root)

        async def analyze_pair(view: str, connected: bool):
            with patch.dict(
                os.environ,
                {
                    "PATH": str(fake_docker.parent) + os.pathsep + os.environ.get("PATH", ""),
                    "FAKE_PCB_CONNECTIVITY": "connected" if connected else "disconnected",
                },
            ):
                process = await self.cli(
                    "kicad_tooling.electrical",
                    "--project",
                    PROJECT,
                    "--output",
                    f"build/electrical/{view}",
                )
                expected_exit = 0 if connected else 1
                self.assertEqual(process.returncode, expected_exit, process.stderr + process.stdout)
                cli_report = ElectricalAnalysisReport.model_validate_json(process.stdout)
                async with Client(
                    create_server(self.mcp_root, allow_checks=True), mode="legacy"
                ) as client:
                    result = await client.call_tool(
                        "analyze_electrical",
                        {"project_id": PROJECT, "view_id": view},
                    )
                self.assertFalse(result.is_error, result.content)
                mcp_report = ElectricalAnalysisReport.model_validate_json(
                    json.dumps(result.structured_content)
                )
            self.assertEqual(cli_report.checks, mcp_report.checks)
            self.assertEqual(cli_report.input_sha256, mcp_report.input_sha256)
            wanted = "PASS" if connected else "FAIL"
            for report in (cli_report, mcp_report):
                self.assertEqual(report.status, wanted)
                check = next(
                    row
                    for row in report.checks
                    if row.id == "pcb-return-paths/serial-returns/connectivity"
                )
                self.assertEqual(check.status, wanted)
                self.assertIn("pcb-connectivity", report.commands)

        await analyze_pair("pcb-return-pass", True)
        await analyze_pair("pcb-return-fault", False)
        self.assertEqual(source_bytes(self.root), before)
        self.assertEqual(source_bytes(self.mcp_root), before)

    async def test_bus_requirements_match_cli_and_mcp_analysis(self) -> None:
        self.configured()
        netlist_xml = (
            "<export><components>"
            '<comp ref="U1"><value>I2C target</value>'
            '<libsource lib="Synthetic" part="I2cTarget"/>'
            '<units><unit name="A"><pins><pin num="1"/><pin num="2"/></pins></unit></units>'
            "</comp>"
            '<comp ref="R1"><value>4.7k</value><libsource lib="Device" part="R"/>'
            '<units><unit name="A"><pins><pin num="1"/><pin num="2"/></pins></unit></units>'
            "</comp>"
            '<comp ref="R2"><value>4.7k</value><libsource lib="Device" part="R"/>'
            '<units><unit name="A"><pins><pin num="1"/><pin num="2"/></pins></unit></units>'
            "</comp>"
            '<comp ref="R3"><value>4.7k</value><libsource lib="Device" part="R"/>'
            '<units><unit name="A"><pins><pin num="1"/><pin num="2"/></pins></unit></units>'
            "</comp>"
            '<comp ref="U2"><value>CAN transceiver</value>'
            '<libsource lib="Synthetic" part="CanTransceiver"/>'
            '<units><unit name="A"><pins><pin num="1"/><pin num="2"/></pins></unit></units>'
            "</comp>"
            '<comp ref="R4"><value>60R</value><libsource lib="Device" part="R"/>'
            '<units><unit name="A"><pins><pin num="1"/><pin num="2"/></pins></unit></units>'
            "</comp>"
            '<comp ref="R5"><value>60R</value><libsource lib="Device" part="R"/>'
            '<units><unit name="A"><pins><pin num="1"/><pin num="2"/></pins></unit></units>'
            "</comp>"
            '<comp ref="C1"><value>100pF</value><footprint>Synthetic:CAP</footprint>'
            '<libsource lib="Synthetic" part="CanMidpointCapacitor"/>'
            '<units><unit name="A"><pins><pin num="1"/><pin num="2"/></pins></unit></units>'
            "</comp>"
            '<comp ref="C2"><value>4.7uF</value><footprint>Synthetic:CAP</footprint>'
            '<libsource lib="Device" part="C"/>'
            '<units><unit name="A"><pins><pin num="1"/><pin num="2"/></pins></unit></units>'
            "</comp>"
            '<comp ref="J9"><value>USB-C receptacle</value>'
            '<libsource lib="Synthetic" part="UsbCReceptacle"/>'
            '<units><unit name="A"><pins><pin num="1"/><pin num="2"/><pin num="3"/>'
            '<pin num="4"/><pin num="5"/></pins></unit></units></comp>'
            '<comp ref="U9"><value>System connector</value>'
            '<libsource lib="Synthetic" part="SystemConnector"/>'
            '<units><unit name="A"><pins><pin num="1"/><pin num="5"/></pins></unit></units>'
            "</comp>"
            '<comp ref="D9"><value>USB protection</value><footprint>Package_DFN:DFN-6</footprint>'
            '<libsource lib="Synthetic" part="UsbProtection"/>'
            '<units><unit name="A"><pins><pin num="1"/><pin num="2"/></pins></unit></units>'
            "</comp>"
            '<comp ref="R6"><value>56k</value><libsource lib="Device" part="R"/>'
            '<units><unit name="A"><pins><pin num="1"/><pin num="2"/></pins></unit></units>'
            "</comp>"
            '<comp ref="R7"><value>56k</value><libsource lib="Device" part="R"/>'
            '<units><unit name="A"><pins><pin num="1"/><pin num="2"/></pins></unit></units>'
            "</comp>"
            '<comp ref="U10"><value>Synthetic SPI controller</value>'
            "<footprint>Package_QFP:LQFP-32</footprint>"
            '<libsource lib="Synthetic" part="SpiController"/>'
            '<units><unit name="A"><pins><pin num="1"/><pin num="2"/><pin num="3"/>'
            '<pin num="4"/><pin num="5"/></pins></unit></units></comp>'
            '<comp ref="U11"><value>Synthetic SPI peripheral</value>'
            "<footprint>Package_SO:SOIC-8</footprint>"
            '<libsource lib="Synthetic" part="SpiPeripheral"/>'
            '<units><unit name="A"><pins><pin num="1"/><pin num="2"/><pin num="3"/>'
            '<pin num="4"/></pins></unit></units></comp>'
            '<comp ref="U12"><value>Synthetic write-only peripheral</value>'
            "<footprint>Package_SO:SOIC-8</footprint>"
            '<libsource lib="Synthetic" part="SpiWriteOnly"/>'
            '<units><unit name="A"><pins><pin num="1"/><pin num="2"/><pin num="4"/>'
            "</pins></unit></units></comp>"
            "</components><libparts>"
            '<libpart lib="Synthetic" part="I2cTarget"><pins>'
            '<pin num="1" name="SDA" type="passive"/>'
            '<pin num="2" name="SCL" type="passive"/></pins></libpart>'
            '<libpart lib="Device" part="R"><pins>'
            '<pin num="1" name="1" type="passive"/>'
            '<pin num="2" name="2" type="passive"/></pins></libpart>'
            '<libpart lib="Synthetic" part="CanTransceiver"><pins>'
            '<pin num="1" name="CANH" type="passive"/>'
            '<pin num="2" name="CANL" type="passive"/></pins></libpart>'
            '<libpart lib="Synthetic" part="CanMidpointCapacitor"><pins>'
            '<pin num="1" name="MIDPOINT" type="passive"/>'
            '<pin num="2" name="GND" type="passive"/></pins></libpart>'
            '<libpart lib="Device" part="C"><pins>'
            '<pin num="1" name="~" type="passive"/>'
            '<pin num="2" name="~" type="passive"/></pins></libpart>'
            '<libpart lib="Synthetic" part="UsbCReceptacle"><pins>'
            '<pin num="1" name="VBUS" type="passive"/>'
            '<pin num="2" name="GND" type="passive"/>'
            '<pin num="3" name="GND" type="passive"/>'
            '<pin num="4" name="CC1" type="passive"/>'
            '<pin num="5" name="CC2" type="passive"/></pins></libpart>'
            '<libpart lib="Synthetic" part="SystemConnector"><pins>'
            '<pin num="1" name="VBUS" type="passive"/>'
            '<pin num="5" name="GND" type="passive"/></pins></libpart>'
            '<libpart lib="Synthetic" part="UsbProtection"><pins>'
            '<pin num="1" name="CC1" type="passive"/>'
            '<pin num="2" name="GND" type="passive"/></pins></libpart>'
            '<libpart lib="Synthetic" part="SpiController"><pins>'
            '<pin num="1" name="SCK" type="passive"/>'
            '<pin num="2" name="MOSI" type="passive"/>'
            '<pin num="3" name="MISO" type="passive"/>'
            '<pin num="4" name="CS0" type="passive"/>'
            '<pin num="5" name="CS1" type="passive"/></pins></libpart>'
            '<libpart lib="Synthetic" part="SpiPeripheral"><pins>'
            '<pin num="1" name="SCK" type="passive"/>'
            '<pin num="2" name="MOSI" type="passive"/>'
            '<pin num="3" name="MISO" type="passive"/>'
            '<pin num="4" name="CS" type="passive"/></pins></libpart>'
            '<libpart lib="Synthetic" part="SpiWriteOnly"><pins>'
            '<pin num="1" name="SCK" type="passive"/>'
            '<pin num="2" name="MOSI" type="passive"/>'
            '<pin num="4" name="CS" type="passive"/></pins></libpart>'
            "</libparts><nets>"
            '<net name="I2C_SDA"><node ref="U1" pin="1"/>'
            '<node ref="R1" pin="1"/><node ref="R2" pin="1"/></net>'
            '<net name="I2C_SCL"><node ref="U1" pin="2"/><node ref="R3" pin="1"/></net>'
            '<net name="+3V3"><node ref="R1" pin="2"/><node ref="R2" pin="2"/>'
            '<node ref="R3" pin="2"/></net>'
            '<net name="CAN_H"><node ref="U2" pin="1"/><node ref="R4" pin="1"/></net>'
            '<net name="CAN_L"><node ref="U2" pin="2"/><node ref="R5" pin="1"/></net>'
            '<net name="CAN_TERM_MID"><node ref="R4" pin="2"/><node ref="R5" pin="2"/>'
            '<node ref="C1" pin="1"/></net>'
            '<net name="CC1"><node ref="J9" pin="4"/><node ref="D9" pin="1"/>'
            '<node ref="R6" pin="1"/></net>'
            '<net name="CC2"><node ref="J9" pin="5"/><node ref="R7" pin="1"/></net>'
            '<net name="VBUS_PORT"><node ref="J9" pin="1"/><node ref="C2" pin="1"/></net>'
            '<net name="VBUS_SYSTEM"><node ref="U9" pin="1"/></net>'
            '<net name="GND"><node ref="J9" pin="2"/><node ref="J9" pin="3"/>'
            '<node ref="U9" pin="5"/><node ref="D9" pin="2"/><node ref="C1" pin="2"/>'
            '<node ref="C2" pin="2"/></net>'
            '<net name="+5V"><node ref="R6" pin="2"/><node ref="R7" pin="2"/></net>'
            '<net name="SPI_SCK"><node ref="U10" pin="1"/><node ref="U11" pin="1"/>'
            '<node ref="U12" pin="1"/></net>'
            '<net name="SPI_MOSI"><node ref="U10" pin="2"/><node ref="U11" pin="2"/>'
            '<node ref="U12" pin="2"/></net>'
            '<net name="SPI_MISO"><node ref="U10" pin="3"/><node ref="U11" pin="3"/></net>'
            '<net name="SPI_CS0"><node ref="U10" pin="4"/><node ref="U11" pin="4"/></net>'
            '<net name="SPI_CS1"><node ref="U10" pin="5"/><node ref="U12" pin="4"/></net>'
            "</nets></export>"
        )
        spi = spi_requirement(
            device2_miso="not_present",
            controller_reference="U10",
            device_references=("U11", "U12"),
            device2_symbol="Synthetic:SpiWriteOnly",
        )
        pullups = i2c_pullup_requirement()
        tolerance_window = (
            i2c_pullup_window_requirement(
                maximum_per_resistor_tolerance_percent=5.0,
                resistor_tolerance_basis="Synthetic resistor tolerance for every pull-up element",
            )
            .buses[0]
            .sda.electrical_window
        )
        self.assertIsNotNone(tolerance_window)
        bus = pullups.buses[0]
        pullups = pullups.model_copy(
            update={
                "buses": (
                    bus.model_copy(
                        update={
                            "sda": bus.sda.model_copy(
                                update={"electrical_window": tolerance_window}
                            ),
                            "scl": bus.scl.model_copy(
                                update={"electrical_window": tolerance_window}
                            ),
                        }
                    ),
                )
            }
        )
        for root in (self.root, self.mcp_root):
            contract_path = root / ISLAND / "tests/electrical.json"
            contract = read_model(contract_path, ElectricalAnalysisContract)
            write_model(
                contract_path,
                contract.model_copy(
                    update={
                        "pin_connectivity": NA,
                        "i2c_pullups": pullups,
                        "can_termination": can_split_termination_requirement(),
                        "usb_c": usb_c_requirement(
                            connector="J9",
                            board_component="U9",
                            protection_reference="D9",
                            resistor_references=("R6", "R7"),
                            vbus_capacitance=True,
                            vbus_capacitor_reference="C2",
                            vbus_capacitor_footprint="Synthetic:CAP",
                        ),
                        "spi": spi,
                    }
                ),
            )
            native = root / "build/native/controller"
            netlist = native / "netlist.xml"
            netlist.write_text(netlist_xml, encoding="utf-8")
            summary_path = native / "summary.json"
            summary = read_model(summary_path, ValidationSummary)
            write_model(
                summary_path,
                summary.model_copy(
                    update={
                        "artifacts_sha256": {
                            **summary.artifacts_sha256,
                            "netlist.xml": digest(netlist),
                        }
                    }
                ),
            )

        summary_arg = "build/native/controller/summary.json"
        process = await self.cli(
            "kicad_tooling.electrical",
            "--project",
            PROJECT,
            "--native-summary",
            summary_arg,
            "--output",
            "build/electrical/i2c-contract-pass",
        )
        if process.returncode:
            failed = ElectricalAnalysisReport.model_validate_json(process.stdout)
            evidence = read_model(
                Path(failed.run_directory) / "netlist-evidence.json", ContractCoachReport
            )
            self.fail(f"native netlist evidence blocked: {evidence.issues}")
        self.assertEqual(process.returncode, 0, process.stderr + process.stdout)
        cli_report = ElectricalAnalysisReport.model_validate_json(process.stdout)
        async with Client(create_server(self.mcp_root, allow_checks=True), mode="legacy") as client:
            result = await client.call_tool(
                "analyze_electrical",
                {
                    "project_id": PROJECT,
                    "view_id": "i2c-contract-pass",
                    "native_summary": summary_arg,
                },
            )
        self.assertFalse(result.is_error, result.content)
        mcp_report = ElectricalAnalysisReport.model_validate_json(
            json.dumps(result.structured_content)
        )
        self.assertEqual(cli_report.checks, mcp_report.checks)
        checks = {item.id: item for item in cli_report.checks}
        self.assertEqual(checks["i2c-pullup/control/sda"].observed, 2_350)
        self.assertEqual(checks["i2c-pullup/control/scl"].observed, 4_700)
        self.assertEqual(
            checks["i2c-pullup/control/sda/electrical-window/minimum-sink-resistance"].status,
            "PASS",
        )
        self.assertEqual(
            checks["i2c-pullup/control/sda/electrical-window/maximum-rise-resistance"].status,
            "PASS",
        )
        self.assertEqual(checks["can-termination/fieldbus/local"].status, "PASS")
        self.assertEqual(checks["can-termination/fieldbus/local/midpoint-capacitor"].status, "PASS")
        self.assertEqual(checks["usb-c/host-port/connector-pins"].status, "PASS")
        self.assertEqual(checks["usb-c/host-port/cc1-attachment"].status, "PASS")
        self.assertEqual(checks["usb-c/host-port/protection/D9"].status, "PASS")
        self.assertEqual(checks["usb-c/host-port/vbus-capacitance"].status, "PASS")
        self.assertEqual(checks["usb-c/host-port/vbus-capacitance"].observed, 4_700)

        self.assertEqual(checks["spi/control/controller-identity"].status, "PASS")
        self.assertEqual(checks["spi/control/device/sensor/route/sck"].status, "PASS")
        self.assertEqual(checks["spi/control/device/memory/route/miso"].status, "NOT_APPLICABLE")

        faulty_netlist_xml = (
            netlist_xml.replace('<comp ref="R1"><value>4.7k', '<comp ref="R1"><value>1k')
            .replace('<comp ref="R2"><value>4.7k', '<comp ref="R2"><value>1k')
            .replace('<comp ref="R4"><value>60R', '<comp ref="R4"><value>100R')
            .replace('<comp ref="C1"><value>100pF', '<comp ref="C1"><value>120pF')
            .replace('<comp ref="C2"><value>4.7uF', '<comp ref="C2"><value>2.2uF')
            .replace('<comp ref="R6"><value>56k', '<comp ref="R6"><value>100k')
            .replace(
                '<net name="SPI_CS1"><node ref="U10" pin="5"/><node ref="U12" pin="4"/></net>',
                '<net name="SPI_CS1"><node ref="U10" pin="5"/></net>'
                '<net name="WRONG_CS"><node ref="U12" pin="4"/></net>',
            )
        )
        for root in (self.root, self.mcp_root):
            native = root / "build/native/controller"
            netlist = native / "netlist.xml"
            netlist.write_text(faulty_netlist_xml, encoding="utf-8")
            summary_path = native / "summary.json"
            summary = read_model(summary_path, ValidationSummary)
            write_model(
                summary_path,
                summary.model_copy(
                    update={
                        "artifacts_sha256": {
                            **summary.artifacts_sha256,
                            "netlist.xml": digest(netlist),
                        }
                    }
                ),
            )
        process = await self.cli(
            "kicad_tooling.electrical",
            "--project",
            PROJECT,
            "--native-summary",
            summary_arg,
            "--output",
            "build/electrical/i2c-contract-fault",
        )
        self.assertEqual(process.returncode, 1, process.stderr + process.stdout)
        cli_fault = ElectricalAnalysisReport.model_validate_json(process.stdout)
        async with Client(create_server(self.mcp_root, allow_checks=True), mode="legacy") as client:
            result = await client.call_tool(
                "analyze_electrical",
                {
                    "project_id": PROJECT,
                    "view_id": "i2c-contract-fault",
                    "native_summary": summary_arg,
                },
            )
        self.assertFalse(result.is_error, result.content)
        mcp_fault = ElectricalAnalysisReport.model_validate_json(
            json.dumps(result.structured_content)
        )
        self.assertEqual(cli_fault.checks, mcp_fault.checks)
        fault_checks = {item.id: item for item in cli_fault.checks}
        self.assertEqual(fault_checks["i2c-pullup/control/sda"].status, "FAIL")
        self.assertEqual(fault_checks["i2c-pullup/control/sda"].observed, 500)
        self.assertEqual(fault_checks["can-termination/fieldbus/local"].status, "FAIL")
        self.assertEqual(
            fault_checks["can-termination/fieldbus/local/midpoint-capacitor"].status, "FAIL"
        )
        self.assertEqual(fault_checks["usb-c/host-port/cc1-attachment"].status, "FAIL")
        self.assertEqual(fault_checks["usb-c/host-port/vbus-capacitance"].status, "FAIL")
        self.assertEqual(fault_checks["usb-c/host-port/vbus-capacitance"].observed, 2_200)
        self.assertEqual(fault_checks["spi/control/device/memory/pins"].status, "FAIL")

    async def test_i2c_array_pullups_match_cli_and_mcp_for_pass_and_fault(self) -> None:
        self.configured()
        requirement = i2c_pullup_array_requirement()

        def install_netlist(observed: NetlistContract) -> None:
            serialized = contract_netlist_xml(observed)
            for root in (self.root, self.mcp_root):
                contract_path = root / ISLAND / "tests/electrical.json"
                contract = read_model(contract_path, ElectricalAnalysisContract)
                write_model(
                    contract_path,
                    contract.model_copy(update={"i2c_pullups": requirement}),
                )
                native = root / "build/native/controller"
                netlist = native / "netlist.xml"
                netlist.write_text(serialized, encoding="utf-8")
                summary_path = native / "summary.json"
                summary = read_model(summary_path, ValidationSummary)
                write_model(
                    summary_path,
                    summary.model_copy(
                        update={
                            "artifacts_sha256": {
                                **summary.artifacts_sha256,
                                "netlist.xml": digest(netlist),
                            }
                        }
                    ),
                )

        async def analyze_both(
            view_id: str,
        ) -> tuple[ElectricalAnalysisReport, ElectricalAnalysisReport, int]:
            summary = "build/native/controller/summary.json"
            process = await self.cli(
                "kicad_tooling.electrical",
                "--project",
                PROJECT,
                "--native-summary",
                summary,
                "--output",
                f"build/electrical/{view_id}",
            )
            cli_report = ElectricalAnalysisReport.model_validate_json(process.stdout)
            async with Client(
                create_server(self.mcp_root, allow_checks=True), mode="legacy"
            ) as client:
                result = await client.call_tool(
                    "analyze_electrical",
                    {
                        "project_id": PROJECT,
                        "view_id": view_id,
                        "native_summary": summary,
                    },
                )
            self.assertFalse(result.is_error, result.content)
            mcp_report = ElectricalAnalysisReport.model_validate_json(
                json.dumps(result.structured_content)
            )
            self.assertEqual(cli_report.checks, mcp_report.checks)
            return cli_report, mcp_report, process.returncode

        install_netlist(i2c_pullup_array_netlist())
        cli_pass, _, pass_returncode = await analyze_both("i2c-array-pass")
        self.assertEqual(pass_returncode, 0)
        pass_checks = {item.id: item for item in cli_pass.checks}
        for line in ("sda", "scl"):
            self.assertEqual(pass_checks[f"i2c-pullup/array-bus/{line}"].status, "PASS")
            self.assertEqual(pass_checks[f"i2c-pullup/array-bus/{line}"].observed, 4_700)

        observed_fault = i2c_pullup_array_netlist()
        components = dict(observed_fault.components)
        components["RN1"] = ComponentContract(value="4x10k", footprint="Synthetic:RA4")
        install_netlist(observed_fault.model_copy(update={"components": components}))
        cli_fault, _, fault_returncode = await analyze_both("i2c-array-fault")
        self.assertEqual(fault_returncode, 1)
        fault_checks = {item.id: item for item in cli_fault.checks}
        for line in ("sda", "scl"):
            check = fault_checks[f"i2c-pullup/array-bus/{line}"]
            self.assertEqual(check.status, "FAIL")
            self.assertIn("RN1 value is 4x10k; expected 4x4.7k", check.detail)

    async def test_i2c_voltage_compatibility_matches_cli_and_mcp_for_pass_and_fault(self) -> None:
        self.configured()

        def install_netlist(observed: NetlistContract, requirement: I2cPullupAnalysis) -> None:
            serialized = contract_netlist_xml(observed)
            for root in (self.root, self.mcp_root):
                contract_path = root / ISLAND / "tests/electrical.json"
                contract = read_model(contract_path, ElectricalAnalysisContract)
                write_model(
                    contract_path,
                    contract.model_copy(update={"i2c_pullups": requirement}),
                )
                native = root / "build/native/controller"
                netlist = native / "netlist.xml"
                netlist.write_text(serialized, encoding="utf-8")
                summary_path = native / "summary.json"
                summary = read_model(summary_path, ValidationSummary)
                write_model(
                    summary_path,
                    summary.model_copy(
                        update={
                            "artifacts_sha256": {
                                **summary.artifacts_sha256,
                                "netlist.xml": digest(netlist),
                            }
                        }
                    ),
                )

        async def analyze_both(
            view_id: str,
        ) -> tuple[ElectricalAnalysisReport, ElectricalAnalysisReport, int]:
            summary = "build/native/controller/summary.json"
            process = await self.cli(
                "kicad_tooling.electrical",
                "--project",
                PROJECT,
                "--native-summary",
                summary,
                "--output",
                f"build/electrical/{view_id}",
            )
            cli_report = ElectricalAnalysisReport.model_validate_json(process.stdout)
            async with Client(
                create_server(self.mcp_root, allow_checks=True), mode="legacy"
            ) as client:
                result = await client.call_tool(
                    "analyze_electrical",
                    {
                        "project_id": PROJECT,
                        "view_id": view_id,
                        "native_summary": summary,
                    },
                )
            self.assertFalse(result.is_error, result.content)
            mcp_report = ElectricalAnalysisReport.model_validate_json(
                json.dumps(result.structured_content)
            )
            self.assertEqual(cli_report.checks, mcp_report.checks)
            return cli_report, mcp_report, process.returncode

        observed = i2c_series_pullup_netlist()
        install_netlist(observed, i2c_pullup_voltage_requirement())
        pass_report, _, pass_returncode = await analyze_both("i2c-voltage-pass")
        self.assertEqual(pass_returncode, 0)
        self.assertIn(f"{ISLAND}/tests/electrical.json", pass_report.input_sha256)
        pass_checks = {item.id: item for item in pass_report.checks}
        for line in ("sda", "scl"):
            check = pass_checks[f"i2c-pullup/series-bus/{line}/voltage-compatibility"]
            self.assertEqual(check.status, "PASS")
            self.assertEqual(check.observed, 3.3)

        install_netlist(
            observed,
            i2c_pullup_voltage_requirement(maximum_input_voltage_v=3.2),
        )
        fault_report, _, fault_returncode = await analyze_both("i2c-voltage-fault")
        self.assertEqual(fault_returncode, 1)
        fault_checks = {item.id: item for item in fault_report.checks}
        for pin, line in (("U1.1", "sda"), ("U1.2", "scl")):
            check = fault_checks[f"i2c-pullup/series-bus/{line}/voltage-compatibility"]
            self.assertEqual(check.status, "FAIL")
            self.assertIn(f"{pin} maximum bus voltage 3.2 V", check.detail)

    async def test_i2c_pullup_electrical_window_matches_cli_and_mcp(self) -> None:
        self.configured()

        def install_netlist(observed: NetlistContract, requirement: I2cPullupAnalysis) -> None:
            serialized = contract_netlist_xml(observed)
            for root in (self.root, self.mcp_root):
                contract_path = root / ISLAND / "tests/electrical.json"
                contract = read_model(contract_path, ElectricalAnalysisContract)
                write_model(
                    contract_path,
                    contract.model_copy(update={"i2c_pullups": requirement}),
                )
                native = root / "build/native/controller"
                netlist = native / "netlist.xml"
                netlist.write_text(serialized, encoding="utf-8")
                summary_path = native / "summary.json"
                summary = read_model(summary_path, ValidationSummary)
                write_model(
                    summary_path,
                    summary.model_copy(
                        update={
                            "artifacts_sha256": {
                                **summary.artifacts_sha256,
                                "netlist.xml": digest(netlist),
                            }
                        }
                    ),
                )

        async def analyze_both(view_id: str) -> tuple[ElectricalAnalysisReport, int]:
            summary = "build/native/controller/summary.json"
            process = await self.cli(
                "kicad_tooling.electrical",
                "--project",
                PROJECT,
                "--native-summary",
                summary,
                "--output",
                f"build/electrical/{view_id}",
            )
            cli_report = ElectricalAnalysisReport.model_validate_json(process.stdout)
            async with Client(
                create_server(self.mcp_root, allow_checks=True), mode="legacy"
            ) as client:
                result = await client.call_tool(
                    "analyze_electrical",
                    {
                        "project_id": PROJECT,
                        "view_id": view_id,
                        "native_summary": summary,
                    },
                )
            self.assertFalse(result.is_error, result.content)
            mcp_report = ElectricalAnalysisReport.model_validate_json(
                json.dumps(result.structured_content)
            )
            self.assertEqual(cli_report.checks, mcp_report.checks)
            return cli_report, process.returncode

        observed = i2c_series_pullup_netlist()
        install_netlist(observed, i2c_pullup_window_requirement())
        pass_report, pass_returncode = await analyze_both("i2c-window-pass")
        self.assertEqual(pass_returncode, 0)
        pass_checks = {item.id: item for item in pass_report.checks}
        for line in ("sda", "scl"):
            for bound in ("minimum-sink-resistance", "maximum-rise-resistance"):
                self.assertEqual(
                    pass_checks[f"i2c-pullup/series-bus/{line}/electrical-window/{bound}"].status,
                    "PASS",
                )

        install_netlist(
            observed,
            i2c_pullup_window_requirement(maximum_bus_capacitance_pf=100.0),
        )
        fault_report, fault_returncode = await analyze_both("i2c-window-fault")
        self.assertEqual(fault_returncode, 1)
        fault_checks = {item.id: item for item in fault_report.checks}
        for line in ("sda", "scl"):
            check = fault_checks[
                f"i2c-pullup/series-bus/{line}/electrical-window/maximum-rise-resistance"
            ]
            self.assertEqual(check.status, "FAIL")
            self.assertIn("3540.66Ω", check.detail)

    async def test_i2c_series_pullups_match_cli_and_mcp_for_pass_and_fault(self) -> None:
        self.configured()
        requirement = i2c_series_pullup_requirement()

        def install_netlist(observed: NetlistContract) -> None:
            serialized = contract_netlist_xml(observed)
            for root in (self.root, self.mcp_root):
                contract_path = root / ISLAND / "tests/electrical.json"
                contract = read_model(contract_path, ElectricalAnalysisContract)
                write_model(
                    contract_path,
                    contract.model_copy(update={"i2c_pullups": requirement}),
                )
                native = root / "build/native/controller"
                netlist = native / "netlist.xml"
                netlist.write_text(serialized, encoding="utf-8")
                summary_path = native / "summary.json"
                summary = read_model(summary_path, ValidationSummary)
                write_model(
                    summary_path,
                    summary.model_copy(
                        update={
                            "artifacts_sha256": {
                                **summary.artifacts_sha256,
                                "netlist.xml": digest(netlist),
                            }
                        }
                    ),
                )

        async def analyze_both(view_id: str) -> tuple[ElectricalAnalysisReport, int]:
            summary = "build/native/controller/summary.json"
            process = await self.cli(
                "kicad_tooling.electrical",
                "--project",
                PROJECT,
                "--native-summary",
                summary,
                "--output",
                f"build/electrical/{view_id}",
            )
            cli_report = ElectricalAnalysisReport.model_validate_json(process.stdout)
            async with Client(
                create_server(self.mcp_root, allow_checks=True), mode="legacy"
            ) as client:
                result = await client.call_tool(
                    "analyze_electrical",
                    {
                        "project_id": PROJECT,
                        "view_id": view_id,
                        "native_summary": summary,
                    },
                )
            self.assertFalse(result.is_error, result.content)
            mcp_report = ElectricalAnalysisReport.model_validate_json(
                json.dumps(result.structured_content)
            )
            self.assertEqual(cli_report.checks, mcp_report.checks)
            return cli_report, process.returncode

        install_netlist(i2c_series_pullup_netlist())
        passed, pass_returncode = await analyze_both("i2c-series-pass")
        self.assertEqual(pass_returncode, 0)
        pass_checks = {item.id: item for item in passed.checks}
        self.assertEqual(pass_checks["i2c-pullup/series-bus/sda/series/sda-chain"].status, "PASS")
        self.assertEqual(pass_checks["i2c-pullup/series-bus/sda"].observed, 4_700)

        install_netlist(i2c_series_pullup_netlist(first_value="2k"))
        fault, fault_returncode = await analyze_both("i2c-series-fault")
        self.assertEqual(fault_returncode, 1)
        fault_checks = {item.id: item for item in fault.checks}
        self.assertEqual(fault_checks["i2c-pullup/series-bus/sda/series/sda-chain"].status, "FAIL")
        self.assertEqual(fault_checks["i2c-pullup/series-bus/sda"].status, "FAIL")

    async def test_usb_c_vbus_path_matches_cli_and_mcp_for_pass_and_fault(self) -> None:
        self.configured()
        requirement = usb_c_requirement(vbus_path=True)

        def install_netlist(observed: NetlistContract) -> None:
            serialized = contract_netlist_xml(observed)
            for root in (self.root, self.mcp_root):
                contract_path = root / ISLAND / "tests/electrical.json"
                contract = read_model(contract_path, ElectricalAnalysisContract)
                write_model(contract_path, contract.model_copy(update={"usb_c": requirement}))
                native = root / "build/native/controller"
                netlist = native / "netlist.xml"
                netlist.write_text(serialized, encoding="utf-8")
                summary_path = native / "summary.json"
                summary = read_model(summary_path, ValidationSummary)
                write_model(
                    summary_path,
                    summary.model_copy(
                        update={
                            "artifacts_sha256": {
                                **summary.artifacts_sha256,
                                "netlist.xml": digest(netlist),
                            }
                        }
                    ),
                )

        async def analyze_both(view_id: str) -> tuple[ElectricalAnalysisReport, int]:
            summary = "build/native/controller/summary.json"
            process = await self.cli(
                "kicad_tooling.electrical",
                "--project",
                PROJECT,
                "--native-summary",
                summary,
                "--output",
                f"build/electrical/{view_id}",
            )
            cli_report = ElectricalAnalysisReport.model_validate_json(process.stdout)
            async with Client(
                create_server(self.mcp_root, allow_checks=True), mode="legacy"
            ) as client:
                result = await client.call_tool(
                    "analyze_electrical",
                    {
                        "project_id": PROJECT,
                        "view_id": view_id,
                        "native_summary": summary,
                    },
                )
            self.assertFalse(result.is_error, result.content)
            mcp_report = ElectricalAnalysisReport.model_validate_json(
                json.dumps(result.structured_content)
            )
            self.assertEqual(cli_report.checks, mcp_report.checks)
            return cli_report, process.returncode

        install_netlist(usb_c_netlist(vbus_path=True))
        passed, pass_returncode = await analyze_both("usb-c-vbus-path-pass")
        self.assertEqual(pass_returncode, 0)
        pass_checks = {item.id: item for item in passed.checks}
        self.assertEqual(pass_checks["usb-c/host-port/vbus-path/input-path"].status, "PASS")

        observed_fault = usb_c_netlist(vbus_path=True)
        nets = {
            net: tuple(pin for pin in pins if pin != "U3.3")
            for net, pins in observed_fault.nets.items()
        }
        nets["VBUS_WRONG"] = ("U3.3",)
        install_netlist(observed_fault.model_copy(update={"nets": nets}))
        fault, fault_returncode = await analyze_both("usb-c-vbus-path-fault")
        self.assertEqual(fault_returncode, 1)
        fault_checks = {item.id: item for item in fault.checks}
        path_check = fault_checks["usb-c/host-port/vbus-path/input-path"]
        self.assertEqual(path_check.status, "FAIL")
        self.assertIn("U3.3", path_check.detail)

    async def test_connector_pin_relationships_match_cli_and_mcp_analysis(self) -> None:
        self.configured(grounding=True)
        for root in (self.root, self.mcp_root):
            contract_path = root / ISLAND / "tests/electrical.json"
            contract = read_model(contract_path, ElectricalAnalysisContract)
            self.assertIsInstance(contract.grounding, GroundingAnalysis)
            grounding = contract.grounding.model_copy(
                update={
                    "domains": (
                        *contract.grounding.domains,
                        GroundDomain(net="GND", pins=("J1.9", "J2.9", "J3.9")),
                    ),
                    "exempt_components": {
                        **contract.grounding.exempt_components,
                        "J4": "Synthetic connector fixture has no reviewed ground pins",
                    },
                }
            )
            pin_connectivity = PinConnectivityAnalysis(
                basis="Synthetic approved connector power pinout",
                rules=(
                    PinRelationshipRule(
                        id="port-power",
                        basis="Three ports share the same supply rail",
                        topology="common_net",
                        pins=("J1.1", "J2.1", "J3.1"),
                        net="+5V",
                    ),
                    PinRelationshipRule(
                        id="unused-pin",
                        basis="Synthetic assembly leaves this optional connector pin unused",
                        topology="unconnected",
                        pins=("J4.2",),
                    ),
                ),
            )
            write_model(
                contract_path,
                contract.model_copy(
                    update={"grounding": grounding, "pin_connectivity": pin_connectivity}
                ),
            )
            native = root / "build/native/controller"
            netlist = native / "netlist.xml"
            observed = netlist.read_text(encoding="utf-8")
            observed = observed.replace(
                "</components>",
                '<comp ref="J1"><value>Test</value></comp>'
                '<comp ref="J2"><value>Test</value></comp>'
                '<comp ref="J3"><value>Test</value></comp>'
                '<comp ref="J4"><value>Test</value></comp></components>',
            ).replace(
                "</nets>",
                '<net name="GND"><node ref="J1" pin="9"/><node ref="J2" pin="9"/>'
                '<node ref="J3" pin="9"/></net>'
                '<net name="USB1_GND"><node ref="J1" pin="4"/></net>'
                '<net name="USB2_GND"><node ref="J2" pin="4"/></net>'
                '<net name="USB3_GND"><node ref="J3" pin="4"/></net>'
                '<net name="+5V"><node ref="J1" pin="1"/>'
                '<node ref="J2" pin="1"/></net>'
                '<net name="PORT3_PWR"><node ref="J3" pin="1"/></net></nets>',
            )
            netlist.write_text(observed, encoding="utf-8")
            summary_path = native / "summary.json"
            summary = read_model(summary_path, ValidationSummary)
            write_model(
                summary_path,
                summary.model_copy(
                    update={
                        "artifacts_sha256": {
                            **summary.artifacts_sha256,
                            "netlist.xml": digest(netlist),
                        }
                    }
                ),
            )
        summary = "build/native/controller/summary.json"
        process = await self.cli(
            "kicad_tooling.electrical",
            "--project",
            PROJECT,
            "--native-summary",
            summary,
            "--output",
            "build/electrical/split-returns",
        )
        self.assertEqual(process.returncode, 1, process.stderr + process.stdout)
        cli_report = ElectricalAnalysisReport.model_validate_json(process.stdout)
        async with Client(create_server(self.mcp_root, allow_checks=True), mode="legacy") as client:
            result = await client.call_tool(
                "analyze_electrical",
                {
                    "project_id": PROJECT,
                    "view_id": "split-returns",
                    "native_summary": summary,
                },
            )
        self.assertFalse(result.is_error, result.content)
        mcp_report = ElectricalAnalysisReport.model_validate_json(
            json.dumps(result.structured_content)
        )
        self.assertEqual(cli_report.checks, mcp_report.checks)
        for report in (cli_report, mcp_report):
            self.assertEqual(report.status, "FAIL")
            checks = {row.id: row for row in report.checks}
            self.assertEqual(checks["grounding/GND"].status, "PASS")
            self.assertEqual(checks["grounding/component-coverage"].status, "PASS")
            self.assertEqual(checks["grounding/return-net-review"].status, "FAIL")
            self.assertIn("J1.4", checks["grounding/return-net-review"].detail)
            self.assertIn("USB3_GND", checks["grounding/return-net-review"].detail)
            self.assertEqual(checks["pin-connectivity/port-power"].status, "FAIL")
            self.assertIn("J3.1", checks["pin-connectivity/port-power"].detail)
            unused_pin = checks["pin-connectivity/unused-pin"]
            self.assertEqual(unused_pin.status, "FAIL")
            self.assertIn("missing symbol pin inventory=['J4']", unused_pin.detail)

    async def test_db9_grounding_requirement_matrix_matches_cli_and_mcp(self) -> None:
        self.configured(grounding=True)
        all_returns = tuple(f"J{index}.{pin}" for index in range(1, 5) for pin in (7, 9))
        requirements = {
            "common": GroundingAnalysis(
                basis="Synthetic approved DB9 pinout requires all return contacts on one domain",
                domains=(GroundDomain(net="COMMON_RETURN", pins=all_returns),),
            ),
            "isolated": GroundingAnalysis(
                basis="Synthetic approved DB9 pinout requires one isolated domain per connector",
                domains=tuple(
                    GroundDomain(net=f"RETURN_PORT_{index}", pins=(f"J{index}.7", f"J{index}.9"))
                    for index in range(1, 5)
                ),
            ),
        }
        cases = (
            ("split-against-common", True, "common", "FAIL"),
            ("common-against-common", False, "common", "PASS"),
            ("split-against-isolated", True, "isolated", "PASS"),
            ("common-against-isolated", False, "isolated", "FAIL"),
        )

        for case_id, isolated_returns, requirement_id, expected_status in cases:
            observed = four_port_db9_netlist(isolated_returns=isolated_returns)
            serialized = contract_netlist_xml(observed)
            for root in (self.root, self.mcp_root):
                contract_path = root / ISLAND / "tests/electrical.json"
                contract = read_model(contract_path, ElectricalAnalysisContract)
                write_model(
                    contract_path,
                    contract.model_copy(update={"grounding": requirements[requirement_id]}),
                )
                native = root / "build/native/controller"
                netlist = native / "netlist.xml"
                netlist.write_text(serialized, encoding="utf-8")
                summary_path = native / "summary.json"
                summary = read_model(summary_path, ValidationSummary)
                write_model(
                    summary_path,
                    summary.model_copy(
                        update={
                            "artifacts_sha256": {
                                **summary.artifacts_sha256,
                                "netlist.xml": digest(netlist),
                            }
                        }
                    ),
                )

            summary_arg = "build/native/controller/summary.json"
            process = await self.cli(
                "kicad_tooling.electrical",
                "--project",
                PROJECT,
                "--native-summary",
                summary_arg,
                "--output",
                f"build/electrical/db9-{case_id}",
            )
            expected_returncode = 0 if expected_status == "PASS" else 1
            self.assertEqual(
                process.returncode, expected_returncode, process.stderr + process.stdout
            )
            cli_report = ElectricalAnalysisReport.model_validate_json(process.stdout)
            async with Client(
                create_server(self.mcp_root, allow_checks=True), mode="legacy"
            ) as client:
                result = await client.call_tool(
                    "analyze_electrical",
                    {
                        "project_id": PROJECT,
                        "view_id": f"db9-{case_id}",
                        "native_summary": summary_arg,
                    },
                )
            self.assertFalse(result.is_error, result.content)
            mcp_report = ElectricalAnalysisReport.model_validate_json(
                json.dumps(result.structured_content)
            )
            self.assertEqual(cli_report.checks, mcp_report.checks)
            for report in (cli_report, mcp_report):
                self.assertEqual(report.status, expected_status)
                checks = {item.id: item for item in report.checks}
                self.assertEqual(checks["grounding/component-coverage"].status, "PASS")
                if requirement_id == "common":
                    self.assertEqual(checks["grounding/COMMON_RETURN"].status, expected_status)
                else:
                    for index in range(1, 5):
                        self.assertEqual(
                            checks[f"grounding/RETURN_PORT_{index}"].status, expected_status
                        )
                if isolated_returns:
                    self.assertEqual(
                        checks["grounding/return-net-review"].status,
                        "FAIL" if requirement_id == "common" else "PASS",
                    )

    async def test_serial_peer_requirements_match_cli_and_mcp_analysis(self) -> None:
        self.configured()
        requirement = serial_peer_requirement(endpoint_reference="U10", peer_reference="U11")
        netlist_xml = (
            "<export><components>"
            '<comp ref="U10"><value>UART endpoint A</value>'
            "<footprint>Connector_Generic:Conn_01x03</footprint>"
            '<libsource lib="Synthetic" part="UartEndpoint"/>'
            '<units><unit name="A"><pins><pin num="1"/><pin num="2"/><pin num="3"/></pins></unit></units>'
            "</comp>"
            '<comp ref="U11"><value>UART endpoint B</value>'
            "<footprint>Connector_Generic:Conn_01x03</footprint>"
            '<libsource lib="Synthetic" part="UartEndpoint"/>'
            '<units><unit name="A"><pins><pin num="1"/><pin num="2"/><pin num="3"/></pins></unit></units>'
            "</comp></components><libparts>"
            '<libpart lib="Synthetic" part="UartEndpoint"><pins>'
            '<pin num="1" name="TX" type="passive"/>'
            '<pin num="2" name="RX" type="passive"/>'
            '<pin num="3" name="GND" type="passive"/>'
            "</pins></libpart></libparts><nets>"
            '<net name="UART_TX"><node ref="U10" pin="1"/><node ref="U11" pin="2"/></net>'
            '<net name="UART_RX"><node ref="U10" pin="2"/><node ref="U11" pin="1"/></net>'
            '<net name="GND"><node ref="U10" pin="3"/><node ref="U11" pin="3"/></net>'
            "</nets></export>"
        )
        for root in (self.root, self.mcp_root):
            contract_path = root / ISLAND / "tests/electrical.json"
            contract = read_model(contract_path, ElectricalAnalysisContract)
            write_model(contract_path, contract.model_copy(update={"serial_peers": requirement}))
            native = root / "build/native/controller"
            netlist = native / "netlist.xml"
            netlist.write_text(netlist_xml, encoding="utf-8")
            summary_path = native / "summary.json"
            summary = read_model(summary_path, ValidationSummary)
            write_model(
                summary_path,
                summary.model_copy(
                    update={
                        "artifacts_sha256": {
                            **summary.artifacts_sha256,
                            "netlist.xml": digest(netlist),
                        }
                    }
                ),
            )

        summary_arg = "build/native/controller/summary.json"
        process = await self.cli(
            "kicad_tooling.electrical",
            "--project",
            PROJECT,
            "--native-summary",
            summary_arg,
            "--output",
            "build/electrical/serial-peer-pass",
        )
        self.assertEqual(process.returncode, 0, process.stderr + process.stdout)
        cli_report = ElectricalAnalysisReport.model_validate_json(process.stdout)
        async with Client(create_server(self.mcp_root, allow_checks=True), mode="legacy") as client:
            result = await client.call_tool(
                "analyze_electrical",
                {
                    "project_id": PROJECT,
                    "view_id": "serial-peer-pass",
                    "native_summary": summary_arg,
                },
            )
        self.assertFalse(result.is_error, result.content)
        mcp_report = ElectricalAnalysisReport.model_validate_json(
            json.dumps(result.structured_content)
        )
        self.assertEqual(cli_report.checks, mcp_report.checks)
        checks = {row.id: row for row in cli_report.checks}
        self.assertEqual(checks["serial/console-link/route/a_tx_to_b_rx"].status, "PASS")
        self.assertEqual(checks["serial/console-link/route/b_tx_to_a_rx"].status, "PASS")
        self.assertEqual(checks["serial/console-link/reference"].status, "PASS")

        voltage_fault_requirement = serial_peer_requirement(peer_output_high_maximum_v=5.0)
        for root in (self.root, self.mcp_root):
            contract_path = root / ISLAND / "tests/electrical.json"
            contract = read_model(contract_path, ElectricalAnalysisContract)
            write_model(
                contract_path,
                contract.model_copy(update={"serial_peers": voltage_fault_requirement}),
            )
        process = await self.cli(
            "kicad_tooling.electrical",
            "--project",
            PROJECT,
            "--native-summary",
            summary_arg,
            "--output",
            "build/electrical/serial-voltage-fault",
        )
        self.assertEqual(process.returncode, 1, process.stderr + process.stdout)
        cli_voltage_fault = ElectricalAnalysisReport.model_validate_json(process.stdout)
        async with Client(create_server(self.mcp_root, allow_checks=True), mode="legacy") as client:
            result = await client.call_tool(
                "analyze_electrical",
                {
                    "project_id": PROJECT,
                    "view_id": "serial-voltage-fault",
                    "native_summary": summary_arg,
                },
            )
        self.assertFalse(result.is_error, result.content)
        mcp_voltage_fault = ElectricalAnalysisReport.model_validate_json(
            json.dumps(result.structured_content)
        )
        self.assertEqual(cli_voltage_fault.checks, mcp_voltage_fault.checks)
        voltage_checks = {row.id: row for row in cli_voltage_fault.checks}
        self.assertEqual(
            voltage_checks["serial/console-link/logic-voltage/b_tx_to_a_rx"].status,
            "FAIL",
        )

        for root in (self.root, self.mcp_root):
            contract_path = root / ISLAND / "tests/electrical.json"
            contract = read_model(contract_path, ElectricalAnalysisContract)
            write_model(contract_path, contract.model_copy(update={"serial_peers": requirement}))

        faulty_netlist_xml = netlist_xml.replace(
            '<net name="UART_TX"><node ref="U10" pin="1"/><node ref="U11" pin="2"/></net>'
            '<net name="UART_RX"><node ref="U10" pin="2"/><node ref="U11" pin="1"/></net>',
            '<net name="UART_TX"><node ref="U10" pin="1"/><node ref="U11" pin="1"/></net>'
            '<net name="UART_RX"><node ref="U10" pin="2"/><node ref="U11" pin="2"/></net>',
        )
        for root in (self.root, self.mcp_root):
            native = root / "build/native/controller"
            netlist = native / "netlist.xml"
            netlist.write_text(faulty_netlist_xml, encoding="utf-8")
            summary_path = native / "summary.json"
            summary = read_model(summary_path, ValidationSummary)
            write_model(
                summary_path,
                summary.model_copy(
                    update={
                        "artifacts_sha256": {
                            **summary.artifacts_sha256,
                            "netlist.xml": digest(netlist),
                        }
                    }
                ),
            )
        process = await self.cli(
            "kicad_tooling.electrical",
            "--project",
            PROJECT,
            "--native-summary",
            summary_arg,
            "--output",
            "build/electrical/serial-peer-fault",
        )
        self.assertEqual(process.returncode, 1, process.stderr + process.stdout)
        cli_fault = ElectricalAnalysisReport.model_validate_json(process.stdout)
        async with Client(create_server(self.mcp_root, allow_checks=True), mode="legacy") as client:
            result = await client.call_tool(
                "analyze_electrical",
                {
                    "project_id": PROJECT,
                    "view_id": "serial-peer-fault",
                    "native_summary": summary_arg,
                },
            )
        self.assertFalse(result.is_error, result.content)
        mcp_fault = ElectricalAnalysisReport.model_validate_json(
            json.dumps(result.structured_content)
        )
        self.assertEqual(cli_fault.checks, mcp_fault.checks)
        fault_checks = {row.id: row for row in cli_fault.checks}
        self.assertEqual(fault_checks["serial/console-link/route/a_tx_to_b_rx"].status, "FAIL")
        self.assertEqual(fault_checks["serial/console-link/route/b_tx_to_a_rx"].status, "FAIL")

    async def test_serial_peer_bonded_reference_matches_cli_and_mcp_for_pass_and_fault(
        self,
    ) -> None:
        self.configured()
        requirement = serial_peer_requirement(reference_policy="bonded")
        summary_arg = "build/native/controller/summary.json"

        async def evaluate_both(
            observed: NetlistContract, view_id: str
        ) -> ElectricalAnalysisReport:
            netlist_xml = contract_netlist_xml(observed)
            for root in (self.root, self.mcp_root):
                contract_path = root / ISLAND / "tests/electrical.json"
                contract = read_model(contract_path, ElectricalAnalysisContract)
                write_model(
                    contract_path,
                    contract.model_copy(update={"serial_peers": requirement}),
                )
                native = root / "build/native/controller"
                netlist = native / "netlist.xml"
                netlist.write_text(netlist_xml, encoding="utf-8")
                summary_path = native / "summary.json"
                summary = read_model(summary_path, ValidationSummary)
                write_model(
                    summary_path,
                    summary.model_copy(
                        update={
                            "artifacts_sha256": {
                                **summary.artifacts_sha256,
                                "netlist.xml": digest(netlist),
                            }
                        }
                    ),
                )

            process = await self.cli(
                "kicad_tooling.electrical",
                "--project",
                PROJECT,
                "--native-summary",
                summary_arg,
                "--output",
                f"build/electrical/{view_id}",
            )
            expected_returncode = 0 if view_id.endswith("control") else 1
            self.assertEqual(
                expected_returncode, process.returncode, process.stderr + process.stdout
            )
            cli_report = ElectricalAnalysisReport.model_validate_json(process.stdout)
            async with Client(
                create_server(self.mcp_root, allow_checks=True), mode="legacy"
            ) as client:
                result = await client.call_tool(
                    "analyze_electrical",
                    {
                        "project_id": PROJECT,
                        "view_id": view_id,
                        "native_summary": summary_arg,
                    },
                )
            self.assertFalse(result.is_error, result.content)
            mcp_report = ElectricalAnalysisReport.model_validate_json(
                json.dumps(result.structured_content)
            )
            self.assertEqual(cli_report.checks, mcp_report.checks)
            return cli_report

        control = await evaluate_both(serial_peer_netlist(requirement), "serial-bond-control")
        self.assertEqual(
            {item.id: item for item in control.checks}["serial/console-link/reference"].status,
            "PASS",
        )
        fault = await evaluate_both(
            serial_peer_netlist(requirement, fault="bond-wrong-net"),
            "serial-bond-fault",
        )
        reference_check = {item.id: item for item in fault.checks}["serial/console-link/reference"]
        self.assertEqual(reference_check.status, "FAIL")
        self.assertIn("R3.2 is on FLOATING_GND; expected GND_B", reference_check.detail)

    async def test_digital_peer_voltage_requirements_match_cli_and_mcp(self) -> None:
        self.configured()
        netlist_xml = contract_netlist_xml(digital_peer_netlist())
        summary_arg = "build/native/controller/summary.json"
        for root in (self.root, self.mcp_root):
            contract_path = root / ISLAND / "tests/electrical.json"
            contract = read_model(contract_path, ElectricalAnalysisContract)
            write_model(
                contract_path,
                contract.model_copy(update={"digital_peer_voltages": digital_peer_requirement()}),
            )
            native = root / "build/native/controller"
            netlist = native / "netlist.xml"
            netlist.write_text(netlist_xml, encoding="utf-8")
            summary_path = native / "summary.json"
            summary = read_model(summary_path, ValidationSummary)
            write_model(
                summary_path,
                summary.model_copy(
                    update={
                        "artifacts_sha256": {
                            **summary.artifacts_sha256,
                            "netlist.xml": digest(netlist),
                        }
                    }
                ),
            )

        process = await self.cli(
            "kicad_tooling.electrical",
            "--project",
            PROJECT,
            "--native-summary",
            summary_arg,
            "--output",
            "build/electrical/digital-peer-pass",
        )
        self.assertEqual(process.returncode, 0, process.stderr + process.stdout)
        cli_pass = ElectricalAnalysisReport.model_validate_json(process.stdout)
        async with Client(create_server(self.mcp_root, allow_checks=True), mode="legacy") as client:
            result = await client.call_tool(
                "analyze_electrical",
                {
                    "project_id": PROJECT,
                    "view_id": "digital-peer-pass",
                    "native_summary": summary_arg,
                },
            )
        self.assertFalse(result.is_error, result.content)
        mcp_pass = ElectricalAnalysisReport.model_validate_json(
            json.dumps(result.structured_content)
        )
        self.assertEqual(cli_pass.checks, mcp_pass.checks)
        checks = {row.id: row for row in cli_pass.checks}
        self.assertEqual(checks["digital-peer-voltage/spi-mosi/compatibility"].status, "PASS")

        for root in (self.root, self.mcp_root):
            contract_path = root / ISLAND / "tests/electrical.json"
            contract = read_model(contract_path, ElectricalAnalysisContract)
            write_model(
                contract_path,
                contract.model_copy(
                    update={
                        "digital_peer_voltages": digital_peer_requirement(output_high_maximum_v=5.0)
                    }
                ),
            )
        process = await self.cli(
            "kicad_tooling.electrical",
            "--project",
            PROJECT,
            "--native-summary",
            summary_arg,
            "--output",
            "build/electrical/digital-peer-fault",
        )
        self.assertEqual(process.returncode, 1, process.stderr + process.stdout)
        cli_fault = ElectricalAnalysisReport.model_validate_json(process.stdout)
        async with Client(create_server(self.mcp_root, allow_checks=True), mode="legacy") as client:
            result = await client.call_tool(
                "analyze_electrical",
                {
                    "project_id": PROJECT,
                    "view_id": "digital-peer-fault",
                    "native_summary": summary_arg,
                },
            )
        self.assertFalse(result.is_error, result.content)
        mcp_fault = ElectricalAnalysisReport.model_validate_json(
            json.dumps(result.structured_content)
        )
        self.assertEqual(cli_fault.checks, mcp_fault.checks)
        fault_checks = {row.id: row for row in cli_fault.checks}
        self.assertEqual(
            fault_checks["digital-peer-voltage/spi-mosi/compatibility"].status,
            "FAIL",
        )

    async def test_component_voltage_rating_requirement_matches_cli_and_mcp(self) -> None:
        self.configured()
        netlist_xml = contract_netlist_xml(component_voltage_netlist())
        summary_arg = "build/native/controller/summary.json"
        for root in (self.root, self.mcp_root):
            contract_path = root / ISLAND / "tests/electrical.json"
            contract = read_model(contract_path, ElectricalAnalysisContract)
            write_model(
                contract_path,
                contract.model_copy(
                    update={"component_voltage_ratings": component_voltage_requirement()}
                ),
            )
            native = root / "build/native/controller"
            netlist = native / "netlist.xml"
            netlist.write_text(netlist_xml, encoding="utf-8")
            summary_path = native / "summary.json"
            summary = read_model(summary_path, ValidationSummary)
            write_model(
                summary_path,
                summary.model_copy(
                    update={
                        "artifacts_sha256": {
                            **summary.artifacts_sha256,
                            "netlist.xml": digest(netlist),
                        }
                    }
                ),
            )

        process = await self.cli(
            "kicad_tooling.electrical",
            "--project",
            PROJECT,
            "--native-summary",
            summary_arg,
            "--output",
            "build/electrical/component-rating-pass",
        )
        self.assertEqual(process.returncode, 0, process.stderr + process.stdout)
        cli_pass = ElectricalAnalysisReport.model_validate_json(process.stdout)
        async with Client(create_server(self.mcp_root, allow_checks=True), mode="legacy") as client:
            result = await client.call_tool(
                "analyze_electrical",
                {
                    "project_id": PROJECT,
                    "view_id": "component-rating-pass",
                    "native_summary": summary_arg,
                },
            )
        self.assertFalse(result.is_error, result.content)
        mcp_pass = ElectricalAnalysisReport.model_validate_json(
            json.dumps(result.structured_content)
        )
        self.assertEqual(cli_pass.checks, mcp_pass.checks)
        checks = {row.id: row for row in cli_pass.checks}
        self.assertEqual(
            checks["component-voltage-rating/input-capacitor/utilization"].status,
            "PASS",
        )

        for root in (self.root, self.mcp_root):
            contract_path = root / ISLAND / "tests/electrical.json"
            contract = read_model(contract_path, ElectricalAnalysisContract)
            write_model(
                contract_path,
                contract.model_copy(
                    update={
                        "component_voltage_ratings": component_voltage_requirement(
                            maximum_expected_voltage_v=15.0
                        )
                    }
                ),
            )
        process = await self.cli(
            "kicad_tooling.electrical",
            "--project",
            PROJECT,
            "--native-summary",
            summary_arg,
            "--output",
            "build/electrical/component-rating-fault",
        )
        self.assertEqual(process.returncode, 1, process.stderr + process.stdout)
        cli_fault = ElectricalAnalysisReport.model_validate_json(process.stdout)
        async with Client(create_server(self.mcp_root, allow_checks=True), mode="legacy") as client:
            result = await client.call_tool(
                "analyze_electrical",
                {
                    "project_id": PROJECT,
                    "view_id": "component-rating-fault",
                    "native_summary": summary_arg,
                },
            )
        self.assertFalse(result.is_error, result.content)
        mcp_fault = ElectricalAnalysisReport.model_validate_json(
            json.dumps(result.structured_content)
        )
        self.assertEqual(cli_fault.checks, mcp_fault.checks)
        fault_checks = {row.id: row for row in cli_fault.checks}
        self.assertEqual(
            fault_checks["component-voltage-rating/input-capacitor/utilization"].status,
            "FAIL",
        )

    async def test_mosfet_state_stress_requirement_matches_cli_and_mcp(self) -> None:
        self.configured()
        netlist_xml = contract_netlist_xml(mosfet_stress_multi_device_netlist())
        summary_arg = "build/native/controller/summary.json"
        for root in (self.root, self.mcp_root):
            contract_path = root / ISLAND / "tests/electrical.json"
            contract = read_model(contract_path, ElectricalAnalysisContract)
            write_model(
                contract_path,
                contract.model_copy(
                    update={"mosfet_stress": mosfet_stress_multi_device_requirement()}
                ),
            )
            native = root / "build/native/controller"
            netlist = native / "netlist.xml"
            netlist.write_text(netlist_xml, encoding="utf-8")
            summary_path = native / "summary.json"
            summary = read_model(summary_path, ValidationSummary)
            write_model(
                summary_path,
                summary.model_copy(
                    update={
                        "artifacts_sha256": {
                            **summary.artifacts_sha256,
                            "netlist.xml": digest(netlist),
                        }
                    }
                ),
            )

        process = await self.cli(
            "kicad_tooling.electrical",
            "--project",
            PROJECT,
            "--native-summary",
            summary_arg,
            "--output",
            "build/electrical/mosfet-stress-pass",
        )
        self.assertEqual(process.returncode, 0, process.stderr + process.stdout)
        cli_pass = ElectricalAnalysisReport.model_validate_json(process.stdout)
        async with Client(create_server(self.mcp_root, allow_checks=True), mode="legacy") as client:
            result = await client.call_tool(
                "analyze_electrical",
                {
                    "project_id": PROJECT,
                    "view_id": "mosfet-stress-pass",
                    "native_summary": summary_arg,
                },
            )
        self.assertFalse(result.is_error, result.content)
        mcp_pass = ElectricalAnalysisReport.model_validate_json(
            json.dumps(result.structured_content)
        )
        self.assertEqual(cli_pass.checks, mcp_pass.checks)
        checks = {row.id: row for row in cli_pass.checks}
        self.assertEqual(checks["mosfet-stress/switch-q1/state-on/vds"].status, "PASS")
        self.assertEqual(checks["mosfet-stress/switch-q1/state-on/vgs"].status, "PASS")
        self.assertEqual(checks["mosfet-stress/switch-q2/state-on/vds"].status, "PASS")
        self.assertEqual(checks["mosfet-stress/switch-q2/state-on/vgs"].status, "PASS")

        stressed = mosfet_stress_multi_device_requirement()
        on = MosfetOperatingState(
            id="on",
            net_potentials={
                **stressed.states[1].net_potentials,
                "D_NET": MosfetVoltageInterval(minimum_v=80.0, maximum_v=80.0),
                "G_NET": MosfetVoltageInterval(minimum_v=25.0, maximum_v=25.0),
                "S_NET": MosfetVoltageInterval(minimum_v=0.0, maximum_v=0.0),
            },
        )
        stressed = stressed.model_copy(update={"states": (stressed.states[0], on)})
        for root in (self.root, self.mcp_root):
            contract_path = root / ISLAND / "tests/electrical.json"
            contract = read_model(contract_path, ElectricalAnalysisContract)
            write_model(contract_path, contract.model_copy(update={"mosfet_stress": stressed}))

        process = await self.cli(
            "kicad_tooling.electrical",
            "--project",
            PROJECT,
            "--native-summary",
            summary_arg,
            "--output",
            "build/electrical/mosfet-stress-fault",
        )
        self.assertEqual(process.returncode, 1, process.stderr + process.stdout)
        cli_fault = ElectricalAnalysisReport.model_validate_json(process.stdout)
        async with Client(create_server(self.mcp_root, allow_checks=True), mode="legacy") as client:
            result = await client.call_tool(
                "analyze_electrical",
                {
                    "project_id": PROJECT,
                    "view_id": "mosfet-stress-fault",
                    "native_summary": summary_arg,
                },
            )
        self.assertFalse(result.is_error, result.content)
        mcp_fault = ElectricalAnalysisReport.model_validate_json(
            json.dumps(result.structured_content)
        )
        self.assertEqual(cli_fault.checks, mcp_fault.checks)
        fault_checks = {row.id: row for row in cli_fault.checks}
        self.assertEqual(fault_checks["mosfet-stress/switch-q1/state-on/vds"].status, "FAIL")
        self.assertEqual(fault_checks["mosfet-stress/switch-q1/state-on/vgs"].status, "FAIL")
        self.assertEqual(fault_checks["mosfet-stress/switch-q2/state-on/vds"].status, "PASS")
        self.assertEqual(fault_checks["mosfet-stress/switch-q2/state-on/vgs"].status, "PASS")

    async def test_component_power_rating_requirement_matches_cli_and_mcp(self) -> None:
        self.configured()
        netlist_xml = contract_netlist_xml(component_power_netlist())
        summary_arg = "build/native/controller/summary.json"
        for root in (self.root, self.mcp_root):
            contract_path = root / ISLAND / "tests/electrical.json"
            contract = read_model(contract_path, ElectricalAnalysisContract)
            write_model(
                contract_path,
                contract.model_copy(
                    update={"component_power_ratings": component_power_requirement()}
                ),
            )
            native = root / "build/native/controller"
            netlist = native / "netlist.xml"
            netlist.write_text(netlist_xml, encoding="utf-8")
            summary_path = native / "summary.json"
            summary = read_model(summary_path, ValidationSummary)
            write_model(
                summary_path,
                summary.model_copy(
                    update={
                        "artifacts_sha256": {
                            **summary.artifacts_sha256,
                            "netlist.xml": digest(netlist),
                        }
                    }
                ),
            )

        process = await self.cli(
            "kicad_tooling.electrical",
            "--project",
            PROJECT,
            "--native-summary",
            summary_arg,
            "--output",
            "build/electrical/component-power-rating-pass",
        )
        self.assertEqual(process.returncode, 0, process.stderr + process.stdout)
        cli_pass = ElectricalAnalysisReport.model_validate_json(process.stdout)
        async with Client(create_server(self.mcp_root, allow_checks=True), mode="legacy") as client:
            result = await client.call_tool(
                "analyze_electrical",
                {
                    "project_id": PROJECT,
                    "view_id": "component-power-rating-pass",
                    "native_summary": summary_arg,
                },
            )
        self.assertFalse(result.is_error, result.content)
        mcp_pass = ElectricalAnalysisReport.model_validate_json(
            json.dumps(result.structured_content)
        )
        self.assertEqual(cli_pass.checks, mcp_pass.checks)
        checks = {row.id: row for row in cli_pass.checks}
        self.assertEqual(
            checks["component-power-rating/sense-resistor/utilization"].status,
            "PASS",
        )

        for root in (self.root, self.mcp_root):
            contract_path = root / ISLAND / "tests/electrical.json"
            contract = read_model(contract_path, ElectricalAnalysisContract)
            write_model(
                contract_path,
                contract.model_copy(
                    update={
                        "component_power_ratings": component_power_requirement(
                            maximum_expected_power_w=0.21
                        )
                    }
                ),
            )
        process = await self.cli(
            "kicad_tooling.electrical",
            "--project",
            PROJECT,
            "--native-summary",
            summary_arg,
            "--output",
            "build/electrical/component-power-rating-fault",
        )
        self.assertEqual(process.returncode, 1, process.stderr + process.stdout)
        cli_fault = ElectricalAnalysisReport.model_validate_json(process.stdout)
        async with Client(create_server(self.mcp_root, allow_checks=True), mode="legacy") as client:
            result = await client.call_tool(
                "analyze_electrical",
                {
                    "project_id": PROJECT,
                    "view_id": "component-power-rating-fault",
                    "native_summary": summary_arg,
                },
            )
        self.assertFalse(result.is_error, result.content)
        mcp_fault = ElectricalAnalysisReport.model_validate_json(
            json.dumps(result.structured_content)
        )
        self.assertEqual(cli_fault.checks, mcp_fault.checks)

    async def test_connector_contact_rating_requirement_matches_cli_and_mcp(self) -> None:
        self.configured()
        netlist_xml = connector_contact_netlist_xml()
        summary_arg = "build/native/controller/summary.json"
        for root in (self.root, self.mcp_root):
            contract_path = root / ISLAND / "tests/electrical.json"
            contract = read_model(contract_path, ElectricalAnalysisContract)
            write_model(
                contract_path,
                contract.model_copy(
                    update={"connector_contact_ratings": connector_contact_requirement()}
                ),
            )
            native = root / "build/native/controller"
            netlist = native / "netlist.xml"
            netlist.write_text(netlist_xml, encoding="utf-8")
            summary_path = native / "summary.json"
            summary = read_model(summary_path, ValidationSummary)
            write_model(
                summary_path,
                summary.model_copy(
                    update={
                        "artifacts_sha256": {
                            **summary.artifacts_sha256,
                            "netlist.xml": digest(netlist),
                        }
                    }
                ),
            )

        process = await self.cli(
            "kicad_tooling.electrical",
            "--project",
            PROJECT,
            "--native-summary",
            summary_arg,
            "--output",
            "build/electrical/connector-contact-rating-pass",
        )
        self.assertEqual(process.returncode, 0, process.stderr + process.stdout)
        cli_pass = ElectricalAnalysisReport.model_validate_json(process.stdout)
        async with Client(create_server(self.mcp_root, allow_checks=True), mode="legacy") as client:
            result = await client.call_tool(
                "analyze_electrical",
                {
                    "project_id": PROJECT,
                    "view_id": "connector-contact-rating-pass",
                    "native_summary": summary_arg,
                },
            )
        self.assertFalse(result.is_error, result.content)
        mcp_pass = ElectricalAnalysisReport.model_validate_json(
            json.dumps(result.structured_content)
        )
        self.assertEqual(cli_pass.checks, mcp_pass.checks)
        checks = {row.id: row for row in cli_pass.checks}
        self.assertEqual(
            checks[
                "connector-contact-rating/host-connector/contact-vbus-contact/utilization"
            ].status,
            "PASS",
        )

        for root in (self.root, self.mcp_root):
            contract_path = root / ISLAND / "tests/electrical.json"
            contract = read_model(contract_path, ElectricalAnalysisContract)
            write_model(
                contract_path,
                contract.model_copy(
                    update={
                        "connector_contact_ratings": connector_contact_requirement(
                            contacts=(connector_contact(maximum_expected_current_a=1.61),)
                        )
                    }
                ),
            )

        process = await self.cli(
            "kicad_tooling.electrical",
            "--project",
            PROJECT,
            "--native-summary",
            summary_arg,
            "--output",
            "build/electrical/connector-contact-rating-fault",
        )
        self.assertEqual(process.returncode, 1, process.stderr + process.stdout)
        cli_fault = ElectricalAnalysisReport.model_validate_json(process.stdout)
        async with Client(create_server(self.mcp_root, allow_checks=True), mode="legacy") as client:
            result = await client.call_tool(
                "analyze_electrical",
                {
                    "project_id": PROJECT,
                    "view_id": "connector-contact-rating-fault",
                    "native_summary": summary_arg,
                },
            )
        self.assertFalse(result.is_error, result.content)
        mcp_fault = ElectricalAnalysisReport.model_validate_json(
            json.dumps(result.structured_content)
        )
        self.assertEqual(cli_fault.checks, mcp_fault.checks)
        fault_checks = {row.id: row for row in cli_fault.checks}
        self.assertEqual(
            fault_checks[
                "connector-contact-rating/host-connector/contact-vbus-contact/utilization"
            ].status,
            "FAIL",
        )

    async def test_rs485_contract_matches_cli_and_mcp_for_pass_and_fault(self) -> None:
        self.configured()
        requirement = rs485_requirement()
        observed = rs485_netlist(requirement)
        for root in (self.root, self.mcp_root):
            contract_path = root / ISLAND / "tests/electrical.json"
            contract = read_model(contract_path, ElectricalAnalysisContract)
            write_model(contract_path, contract.model_copy(update={"rs485": requirement}))
            native = root / "build/native/controller"
            netlist = native / "netlist.xml"
            netlist.write_text(contract_netlist_xml(observed), encoding="utf-8")
            summary_path = native / "summary.json"
            summary = read_model(summary_path, ValidationSummary)
            write_model(
                summary_path,
                summary.model_copy(
                    update={
                        "artifacts_sha256": {
                            **summary.artifacts_sha256,
                            "netlist.xml": digest(netlist),
                        }
                    }
                ),
            )

        summary_arg = "build/native/controller/summary.json"
        process = await self.cli(
            "kicad_tooling.electrical",
            "--project",
            PROJECT,
            "--native-summary",
            summary_arg,
            "--output",
            "build/electrical/rs485-pass",
        )
        self.assertEqual(process.returncode, 0, process.stderr + process.stdout)
        cli_report = ElectricalAnalysisReport.model_validate_json(process.stdout)
        async with Client(create_server(self.mcp_root, allow_checks=True), mode="legacy") as client:
            result = await client.call_tool(
                "analyze_electrical",
                {
                    "project_id": PROJECT,
                    "view_id": "rs485-pass",
                    "native_summary": summary_arg,
                },
            )
        self.assertFalse(result.is_error, result.content)
        mcp_report = ElectricalAnalysisReport.model_validate_json(
            json.dumps(result.structured_content)
        )
        self.assertEqual(cli_report.checks, mcp_report.checks)
        checks = {row.id: row for row in cli_report.checks}
        self.assertEqual(checks["rs485/fieldbus/pair/shared/membership"].status, "PASS")
        self.assertEqual(checks["rs485/fieldbus/pair/shared/termination/local-end"].status, "PASS")
        self.assertEqual(checks["rs485/fieldbus/pair/shared/bias"].status, "PASS")

        faulty = contract_netlist_xml(rs485_netlist(requirement, fault="termination-dnp"))
        for root in (self.root, self.mcp_root):
            native = root / "build/native/controller"
            netlist = native / "netlist.xml"
            netlist.write_text(faulty, encoding="utf-8")
            summary_path = native / "summary.json"
            summary = read_model(summary_path, ValidationSummary)
            write_model(
                summary_path,
                summary.model_copy(
                    update={
                        "artifacts_sha256": {
                            **summary.artifacts_sha256,
                            "netlist.xml": digest(netlist),
                        }
                    }
                ),
            )
        process = await self.cli(
            "kicad_tooling.electrical",
            "--project",
            PROJECT,
            "--native-summary",
            summary_arg,
            "--output",
            "build/electrical/rs485-fault",
        )
        self.assertEqual(process.returncode, 1, process.stderr + process.stdout)
        cli_fault = ElectricalAnalysisReport.model_validate_json(process.stdout)
        async with Client(create_server(self.mcp_root, allow_checks=True), mode="legacy") as client:
            result = await client.call_tool(
                "analyze_electrical",
                {
                    "project_id": PROJECT,
                    "view_id": "rs485-fault",
                    "native_summary": summary_arg,
                },
            )
        self.assertFalse(result.is_error, result.content)
        mcp_fault = ElectricalAnalysisReport.model_validate_json(
            json.dumps(result.structured_content)
        )
        self.assertEqual(cli_fault.checks, mcp_fault.checks)
        fault_checks = {row.id: row for row in cli_fault.checks}
        self.assertEqual(
            fault_checks["rs485/fieldbus/pair/shared/termination/local-end"].status,
            "FAIL",
        )

    async def test_power_connectivity_matches_cli_and_mcp_for_pass_and_fault(self) -> None:
        self.configured()
        requirement = power_connectivity_requirement()
        observed = power_connectivity_netlist()
        for root in (self.root, self.mcp_root):
            contract_path = root / ISLAND / "tests/electrical.json"
            contract = read_model(contract_path, ElectricalAnalysisContract)
            write_model(
                contract_path, contract.model_copy(update={"power_connectivity": requirement})
            )
            native = root / "build/native/controller"
            netlist = native / "netlist.xml"
            netlist.write_text(contract_netlist_xml(observed), encoding="utf-8")
            summary_path = native / "summary.json"
            summary = read_model(summary_path, ValidationSummary)
            write_model(
                summary_path,
                summary.model_copy(
                    update={
                        "artifacts_sha256": {
                            **summary.artifacts_sha256,
                            "netlist.xml": digest(netlist),
                        }
                    }
                ),
            )

        summary_arg = "build/native/controller/summary.json"
        process = await self.cli(
            "kicad_tooling.electrical",
            "--project",
            PROJECT,
            "--native-summary",
            summary_arg,
            "--output",
            "build/electrical/power-connectivity-pass",
        )
        self.assertEqual(process.returncode, 0, process.stderr + process.stdout)
        cli_report = ElectricalAnalysisReport.model_validate_json(process.stdout)
        async with Client(create_server(self.mcp_root, allow_checks=True), mode="legacy") as client:
            result = await client.call_tool(
                "analyze_electrical",
                {
                    "project_id": PROJECT,
                    "view_id": "power-connectivity-pass",
                    "native_summary": summary_arg,
                },
            )
        self.assertFalse(result.is_error, result.content)
        mcp_report = ElectricalAnalysisReport.model_validate_json(
            json.dumps(result.structured_content)
        )
        self.assertEqual(cli_report.checks, mcp_report.checks)
        checks = {row.id: row for row in cli_report.checks}
        self.assertEqual(
            checks["power-connectivity/supply/source/approved-inputs"].status,
            "PASS",
        )
        self.assertEqual(
            checks["power-connectivity/supply/load/load"].status,
            "PASS",
        )

        faulty = contract_netlist_xml(power_connectivity_netlist(fault="load-wrong-net"))
        for root in (self.root, self.mcp_root):
            native = root / "build/native/controller"
            netlist = native / "netlist.xml"
            netlist.write_text(faulty, encoding="utf-8")
            summary_path = native / "summary.json"
            summary = read_model(summary_path, ValidationSummary)
            write_model(
                summary_path,
                summary.model_copy(
                    update={
                        "artifacts_sha256": {
                            **summary.artifacts_sha256,
                            "netlist.xml": digest(netlist),
                        }
                    }
                ),
            )
        failed = await self.cli(
            "kicad_tooling.electrical",
            "--project",
            PROJECT,
            "--native-summary",
            summary_arg,
            "--output",
            "build/electrical/power-connectivity-fault",
        )
        self.assertEqual(failed.returncode, 1, failed.stderr + failed.stdout)
        cli_failed = ElectricalAnalysisReport.model_validate_json(failed.stdout)
        async with Client(create_server(self.mcp_root, allow_checks=True), mode="legacy") as client:
            result = await client.call_tool(
                "analyze_electrical",
                {
                    "project_id": PROJECT,
                    "view_id": "power-connectivity-fault",
                    "native_summary": summary_arg,
                },
            )
        self.assertFalse(result.is_error, result.content)
        mcp_failed = ElectricalAnalysisReport.model_validate_json(
            json.dumps(result.structured_content)
        )
        self.assertEqual(cli_failed.checks, mcp_failed.checks)
        fault_checks = {row.id: row for row in cli_failed.checks}
        self.assertEqual(
            fault_checks["power-connectivity/supply/load/load"].status,
            "FAIL",
        )

    async def test_control_input_requirements_match_cli_mcp_and_retained_evidence(self) -> None:
        self.configured()
        requirement = control_requirement()
        access_requirement = AccessAnalysis(
            basis="Synthetic service procedure and interface pin review",
            pcb_accessibility=NA,
            decisions=(
                RequiredTestAccess(
                    mode="required",
                    id="reset-access",
                    basis="Factory service requires access to reset",
                    net="RESET_N",
                    endpoints=(
                        AccessEndpointRequirement(
                            kind="programming_connector",
                            reference="J1",
                            symbol="Synthetic:DB9",
                            footprint="Connector:Dsub-9_Male",
                            pin="J1.9",
                            electrical_type="passive",
                        ),
                    ),
                ),
                ExcludedTestAccess(
                    mode="not_required",
                    id="hazardous-node",
                    basis="Synthetic safety review",
                    net="HV_OUT",
                    reason="The hazardous synthetic node is excluded from service probing.",
                ),
            ),
        )
        observed = control_netlist()
        for root in (self.root, self.mcp_root):
            contract_path = root / ISLAND / "tests/electrical.json"
            contract = read_model(contract_path, ElectricalAnalysisContract)
            write_model(
                contract_path,
                contract.model_copy(
                    update={"control_inputs": requirement, "test_access": access_requirement}
                ),
            )
            native = root / "build/native/controller"
            netlist = native / "netlist.xml"
            netlist.write_text(contract_netlist_xml(observed), encoding="utf-8")
            summary_path = native / "summary.json"
            summary = read_model(summary_path, ValidationSummary)
            write_model(
                summary_path,
                summary.model_copy(
                    update={
                        "artifacts_sha256": {
                            **summary.artifacts_sha256,
                            "netlist.xml": digest(netlist),
                        }
                    }
                ),
            )

        summary_arg = "build/native/controller/summary.json"
        process = await self.cli(
            "kicad_tooling.electrical",
            "--project",
            PROJECT,
            "--native-summary",
            summary_arg,
            "--output",
            "build/electrical/control-inputs-pass",
        )
        self.assertEqual(process.returncode, 0, process.stderr + process.stdout)
        cli_report = ElectricalAnalysisReport.model_validate_json(process.stdout)
        async with Client(create_server(self.mcp_root, allow_checks=True), mode="legacy") as client:
            result = await client.call_tool(
                "analyze_electrical",
                {
                    "project_id": PROJECT,
                    "view_id": "control-inputs-pass",
                    "native_summary": summary_arg,
                },
            )
        self.assertFalse(result.is_error, result.content)
        mcp_report = ElectricalAnalysisReport.model_validate_json(
            json.dumps(result.structured_content)
        )
        self.assertEqual(cli_report.checks, mcp_report.checks)
        checks = {row.id: row for row in cli_report.checks}
        self.assertEqual(checks["control-inputs/main-reset/endpoints"].status, "PASS")
        self.assertEqual(checks["control-inputs/main-reset/drivers"].status, "PASS")
        self.assertEqual(checks["control-inputs/main-reset/bias"].status, "PASS")
        self.assertEqual(checks["test-access/schematic/reset-access"].status, "PASS")
        self.assertEqual(checks["test-access/schematic/hazardous-node"].status, "NOT_APPLICABLE")
        faulty = contract_netlist_xml(control_netlist(fault="extra-output"))
        for root in (self.root, self.mcp_root):
            native = root / "build/native/controller"
            netlist = native / "netlist.xml"
            netlist.write_text(faulty, encoding="utf-8")
            summary_path = native / "summary.json"
            summary = read_model(summary_path, ValidationSummary)
            write_model(
                summary_path,
                summary.model_copy(
                    update={
                        "artifacts_sha256": {
                            **summary.artifacts_sha256,
                            "netlist.xml": digest(netlist),
                        }
                    }
                ),
            )
        failed = await self.cli(
            "kicad_tooling.electrical",
            "--project",
            PROJECT,
            "--native-summary",
            summary_arg,
            "--output",
            "build/electrical/control-inputs-fault",
        )
        self.assertEqual(failed.returncode, 1, failed.stderr + failed.stdout)
        cli_failed = ElectricalAnalysisReport.model_validate_json(failed.stdout)
        async with Client(create_server(self.mcp_root, allow_checks=True), mode="legacy") as client:
            result = await client.call_tool(
                "analyze_electrical",
                {
                    "project_id": PROJECT,
                    "view_id": "control-inputs-fault",
                    "native_summary": summary_arg,
                },
            )
        self.assertFalse(result.is_error, result.content)
        mcp_failed = ElectricalAnalysisReport.model_validate_json(
            json.dumps(result.structured_content)
        )
        self.assertEqual(cli_failed.checks, mcp_failed.checks)
        fault_checks = {row.id: row for row in cli_failed.checks}
        self.assertEqual(fault_checks["control-inputs/main-reset/drivers"].status, "FAIL")

    async def test_pcb_test_access_schematic_and_board_stages_match_cli_and_mcp(self) -> None:
        self.configured()
        access = AccessAnalysis(
            basis="Synthetic manufacturing access requirements",
            pcb_accessibility=PcbAccessAnalysis(
                basis="Synthetic probe pad must be placed and mask-open"
            ),
            decisions=(
                RequiredTestAccess(
                    mode="required",
                    id="logic-rail",
                    basis="Synthetic fixture measures the logic rail",
                    net="+3V3",
                    endpoints=(
                        AccessEndpointRequirement(
                            kind="test_point",
                            reference="TP1",
                            symbol="TestPoint:TestPoint",
                            footprint="TestPoint:TestPoint_Pad_D1.0mm",
                            pin="TP1.1",
                            electrical_type="passive",
                            approach_side="front",
                            probe_envelope=AccessProbeEnvelope(
                                tip_diameter_mm=0.8,
                                clearance_mm=0.1,
                            ),
                        ),
                    ),
                ),
            ),
        )
        for root in (self.root, self.mcp_root):
            contract_path = root / ISLAND / "tests/electrical.json"
            contract = read_model(contract_path, ElectricalAnalysisContract)
            write_model(contract_path, contract.model_copy(update={"test_access": access}))
            config = selected_config(root, PROJECT)
            board_path = repo_path(root, config.project).with_suffix(".kicad_pcb")
            board_path.write_text(testpoint_board_source(), encoding="utf-8")
            native = root / "build/native/controller"
            netlist = native / "netlist.xml"
            netlist.write_text(contract_netlist_xml(control_netlist()), encoding="utf-8")
            summary_path = native / "summary.json"
            summary = read_model(summary_path, ValidationSummary)
            current_hashes = hashes(root, config.source_roots)
            summary_checks = dict(summary.checks)
            for check_id in ("source_scope", "source_unchanged"):
                summary_checks[check_id] = summary_checks[check_id].model_copy(
                    update={"source_hashes": current_hashes}
                )
            write_model(
                summary_path,
                summary.model_copy(
                    update={
                        "checks": summary_checks,
                        "artifacts_sha256": {
                            **summary.artifacts_sha256,
                            "netlist.xml": digest(netlist),
                        },
                    }
                ),
            )

        fake_bin = self.root.parent / "fake-access-probe"
        fake_bin.mkdir()
        fake_docker = fake_executable(
            fake_bin / "docker",
            "from __future__ import annotations\n"
            "import hashlib, json, os, sys\n"
            "from pathlib import Path\n"
            "args = sys.argv[1:]\n"
            "work = Path(next(arg[:-len(':/work:ro')] for arg in args if arg.endswith(':/work:ro')))\n"
            "output = Path(next(arg[:-len(':/output:rw')] for arg in args if arg.endswith(':/output:rw')))\n"
            "board = work / args[-3].removeprefix('/work/')\n"
            "snapshot = output / args[-2].removeprefix('/output/')\n"
            "request = output / args[-1].removeprefix('/output/')\n"
            "rows = json.loads(request.read_text(encoding='utf-8'))['requests']\n"
            "distance = int(os.environ['FAKE_ACCESS_DISTANCE_NM'])\n"
            "data = {'schema_version': '10', 'board_sha256': hashlib.sha256(board.read_bytes()).hexdigest(), "
            f"'kicad_version': {config.kicad_version!r}, "
            "'zones_refilled': True, 'pads': ["
            "{'pad': 'TP1.1', 'net': '+3V3', 'footprint': 'TestPoint:TestPoint_Pad_D1.0mm', 'dnp': False, 'connected_pads': ['TP1.1'], 'connected_vias': [], 'connected_zones': [], 'connected_islands': [], 'positions_nm': [[0, 0]]}, "
            "{'pad': 'TP2.1', 'net': 'OTHER', 'footprint': 'Synthetic:Obstacle', 'dnp': False, 'connected_pads': ['TP2.1'], 'connected_vias': [], 'connected_zones': [], 'connected_islands': [], 'positions_nm': [[500000, 0]]}], "
            "'vias': [], 'net_ties': [], 'zones': [], 'tracks': [], 'copper_layers': ['F.Cu', 'B.Cu'], 'access_probe_observations': ["
            "{'endpoint': item['endpoint'], 'side': item['side'], 'target_net': item['net'], 'target_exposed': True, 'obstacle': 'TP2.1', 'obstacle_net': 'OTHER', 'distance_nm': distance, 'target_aperture_shape': 'circle', 'target_aperture_diameter_nm': 1000000} for item in rows], "
            "'access_probe_requests_sha256': hashlib.sha256(request.read_bytes()).hexdigest()}\n"
            "snapshot.write_text(json.dumps(data, sort_keys=True), encoding='utf-8')\n",
        )
        self.assertTrue(fake_docker.exists())
        summary_arg = "build/native/controller/summary.json"

        async def analyze_pair(view: str, distance_nm: int, expected: str) -> None:
            with patch.dict(
                os.environ,
                {
                    "PATH": str(fake_bin) + os.pathsep + os.environ.get("PATH", ""),
                    "FAKE_ACCESS_DISTANCE_NM": str(distance_nm),
                },
            ):
                process = await self.cli(
                    "kicad_tooling.electrical",
                    "--project",
                    PROJECT,
                    "--native-summary",
                    summary_arg,
                    "--output",
                    f"build/electrical/{view}",
                )
                self.assertEqual(
                    process.returncode,
                    0 if expected == "PASS" else 1,
                    process.stderr + process.stdout,
                )
                cli_report = ElectricalAnalysisReport.model_validate_json(process.stdout)
                async with Client(
                    create_server(self.mcp_root, allow_checks=True), mode="legacy"
                ) as client:
                    result = await client.call_tool(
                        "analyze_electrical",
                        {
                            "project_id": PROJECT,
                            "view_id": view,
                            "native_summary": summary_arg,
                        },
                    )
            self.assertFalse(result.is_error, result.content)
            mcp_report = ElectricalAnalysisReport.model_validate_json(
                json.dumps(result.structured_content)
            )
            self.assertEqual(cli_report.checks, mcp_report.checks)
            self.assertEqual(set(cli_report.commands), set(mcp_report.commands))
            for report in (cli_report, mcp_report):
                check = next(
                    row
                    for row in report.checks
                    if row.id == "test-access/pcb-probe-envelope/logic-rail"
                )
                self.assertEqual(check.status, expected)
                self.assertIn("target mask aperture is 1 mm", check.detail)
                self.assertIn("required tip-plus-clearance diameter is 1 mm", check.detail)
                self.assertIn("pcb-connectivity", report.commands)

        await analyze_pair("pcb-test-access-pass", 500_000, "PASS")
        await analyze_pair("pcb-test-access-fault", 499_999, "FAIL")

    async def test_external_fixed_simulator_success_and_wrong_version_match_cli(self) -> None:
        self.configured(simulation=True)
        before = source_bytes(self.root)
        binary = self.root.parent / "external-bin"
        binary.mkdir()
        waveform = (
            "Title: synthetic\nFlags: real\nNo. Variables: 2\nNo. Points: 4\n"
            "Variables:\n0 time time\n1 v(out) voltage\nValues:\n"
            "0 0\n0\n1 0.001\n4.9\n2 0.004\n4.95\n3 0.005\n5\n"
        )
        executable = fake_executable(
            binary / "ngspice",
            (
                "from pathlib import Path\nimport sys\n"
                "if sys.argv[1:] == ['--version']:\n    print('ngspice-47')\n"
                "else:\n"
                f"    Path('waveforms.raw').write_text({waveform!r})\n"
                "    print('Synthetic simulator progress')\n"
                "    print('check0 = 4.95' if Path.cwd().name == 'startup' else "
                "'check0 = 0.05\\ncheck1 = 0.25\\ncheck2 = 4.95')\n"
            ),
        )
        self.assertFalse(executable.is_relative_to(self.root))
        with patch.dict(
            os.environ, {"PATH": str(binary) + os.pathsep + os.environ.get("PATH", "")}
        ):
            async with Client(
                create_server(self.mcp_root, allow_checks=True), mode="legacy"
            ) as client:
                for view, version, status in (
                    ("simulation", "47", "PASS"),
                    ("wrong-version", "46", "FAIL"),
                ):
                    if version == "46":
                        fake_executable(binary / "ngspice", "print('ngspice-46')\n")
                    process = await self.cli(
                        "kicad_tooling.electrical",
                        "--project",
                        PROJECT,
                        "--output",
                        f"build/electrical/{view}",
                    )
                    self.assertEqual(
                        process.returncode,
                        0 if status == "PASS" else 1,
                        process.stderr + process.stdout,
                    )
                    cli_report = ElectricalAnalysisReport.model_validate_json(process.stdout)
                    result = await client.call_tool(
                        "analyze_electrical", {"project_id": PROJECT, "view_id": view}
                    )
                    self.assertFalse(result.is_error, result.content)
                    mcp_report = ElectricalAnalysisReport.model_validate_json(
                        json.dumps(result.structured_content)
                    )
                    self.assertEqual(cli_report.checks, mcp_report.checks)
                    self.assertEqual(cli_report.input_sha256, mcp_report.input_sha256)
                    for report in (cli_report, mcp_report):
                        self.assertEqual(report.status, status)
                        self.assertFalse(report.build_authorized)
                        if status == "PASS":
                            self.assertIn(
                                "Synthetic simulator progress", report.commands["startup"].stdout
                            )
                            self.assertEqual(
                                set(report.commands), {"version", "startup", "steady-state"}
                            )
                        else:
                            self.assertTrue(any(row.status == "NOT_RUN" for row in report.checks))
                            self.assertTrue(
                                (
                                    Path(report.run_directory) / "ngspice-version.command.json"
                                ).is_file()
                            )
        self.assertEqual(source_bytes(self.root), before)
        self.assertEqual(source_bytes(self.mcp_root), before)

    async def test_scope_selection_preserves_mixed_outcomes_like_ci(self) -> None:
        self.configured()
        process = await self.cli(
            "kicad_tooling.ci", "--electrical", "--tag", "training", "--project", PROJECT
        )
        self.assertEqual(process.returncode, 1, process.stderr + process.stdout)
        cli_report = ElectricalSuiteReport.model_validate_json(process.stdout)
        async with Client(create_server(self.mcp_root, allow_checks=True), mode="legacy") as client:
            result = await client.call_tool(
                "check_electrical_scope", {"tags": ["training"], "project_ids": [PROJECT]}
            )
            self.assertFalse(result.is_error, result.content)
            mcp_report = ElectricalSuiteReport.model_validate_json(
                json.dumps(result.structured_content)
            )
            invalid = await client.call_tool(
                "check_electrical_scope", {"project_ids": ["missing-project"]}
            )
            self.assertTrue(invalid.is_error)
        self.assertEqual(
            [(row.project_id, row.status, row.checks) for row in cli_report.projects],
            [(row.project_id, row.status, row.checks) for row in mcp_report.projects],
        )
        self.assertFalse(mcp_report.build_authorized)
        self.assertEqual(mcp_report.status, "FAIL")
        self.assertEqual({row.status for row in mcp_report.projects}, {"PASS", "NOT_CONFIGURED"})

    async def test_doctor_and_verification_electrical_preflight_match_cli(self) -> None:
        self.configured(simulation=True)
        for root in (self.root, self.mcp_root):
            initialize_git(root)
        binary = self.root.parent / "electrical-preflight-bin"
        binary.mkdir()
        fake_executable(binary / "ngspice", "print('ngspice-46')\n")
        fake_executable(binary / "kicad-cli", f"print({self.fixture.config.kicad_version!r})\n")
        with patch.dict(
            os.environ, {"PATH": str(binary) + os.pathsep + os.environ.get("PATH", "")}
        ):
            process = await self.cli(
                "kicad_tooling.template",
                "doctor",
                "--electrical",
                "--project-id",
                PROJECT,
                "--runner",
                "local",
            )
            self.assertEqual(process.returncode, 1, process.stderr + process.stdout)
            cli_doctor = TemplateDoctorReport.model_validate_json(process.stdout)
            process = await self.cli(
                "kicad_tooling.verify",
                "--project",
                PROJECT,
                "--depth",
                "electrical",
                "--runner",
                "local",
            )
            self.assertEqual(process.returncode, 1, process.stderr + process.stdout)
            cli_check = ProjectVerificationReport.model_validate_json(process.stdout)
            async with Client(
                create_server(self.mcp_root, allow_checks=True), mode="legacy"
            ) as client:
                result = await client.call_tool(
                    "doctor", {"project_id": PROJECT, "electrical": True, "runner": "local"}
                )
                self.assertFalse(result.is_error, result.content)
                mcp_doctor = TemplateDoctorReport.model_validate_json(
                    json.dumps(result.structured_content)
                )
                result = await client.call_tool(
                    "check_project",
                    {"project_id": PROJECT, "depth": "electrical", "runner": "local"},
                )
                self.assertFalse(result.is_error, result.content)
                mcp_check = ProjectVerificationReport.model_validate_json(
                    json.dumps(result.structured_content)
                )
        self.assertEqual(
            [(row.id, row.status, row.observed) for row in cli_doctor.checks],
            [(row.id, row.status, row.observed) for row in mcp_doctor.checks],
        )
        for report in (cli_doctor, mcp_doctor):
            self.assertEqual(report.status, "FAIL")
            self.assertTrue(report.electrical_requested)
            self.assertTrue(report.native_requested)
            self.assertTrue(
                any(row.status == "FAIL" and "ngspice" in row.id for row in report.checks)
            )
        for report in (cli_check, mcp_check):
            self.assertEqual(report.status, "FAIL")
            self.assertEqual(report.depth, "electrical")
            self.assertFalse(report.build_authorized)
            self.assertIsNone(report.native)
            self.assertIsNone(report.electrical)
            self.assertIsNotNone(report.doctor)
            self.assertTrue(report.doctor.electrical_requested)

    async def test_capability_gates_and_file_only_nested_contract_schema(self) -> None:
        gates = {
            "init_electrical": "allow_edits",
            "capture_electrical_inputs": "allow_exports",
            "analyze_electrical": "allow_checks",
            "check_electrical_scope": "allow_checks",
        }
        for flag in (None, "allow_edits", "allow_exports", "allow_checks"):
            async with Client(
                create_server(self.mcp_root, **({flag: True} if flag else {})), mode="legacy"
            ) as client:
                tools = {tool.name: tool for tool in (await client.list_tools()).tools}
                for name, required in gates.items():
                    self.assertEqual(name in tools, flag == required, (name, flag))
                    if name in tools:
                        properties = tools[name].input_schema["properties"]
                        self.assertFalse(
                            {"root", "output", "cli", "ngspice", "contract"} & set(properties)
                        )
                if flag == "allow_exports":
                    bad = await client.call_tool(
                        "capture_electrical_inputs",
                        {
                            "project_id": PROJECT,
                            "view_id": "wrong-model-type",
                            "models": [1],
                        },
                    )
                    self.assertTrue(bad.is_error)
                    self.assertFalse((self.mcp_root / "build/electrical-inputs").exists())

    async def test_typed_sidecar_and_local_models_allow_reviewed_edits_only(self) -> None:
        self.configured(simulation=True)
        sidecar = self.mcp_root / ISLAND / "tests/electrical.json"
        before = sidecar.read_bytes()
        async with Client(create_server(self.mcp_root, allow_edits=True), mode="legacy") as client:
            result = await client.call_tool(
                "read_project_file", {"project_id": PROJECT, "path": "tests/electrical.json"}
            )
            self.assertFalse(result.is_error, result.content)
            for old, new in (
                (f'"project_id": "{PROJECT}"', '"project_id": "another-project"'),
                ('"schema_version": "1"', '"schema_version": "1", "unknown": true'),
            ):
                result = await client.call_tool(
                    "apply_project_edit",
                    {
                        "project_id": PROJECT,
                        "path": "tests/electrical.json",
                        "expected_sha256": digest(sidecar),
                        "old_text": old,
                        "new_text": new,
                    },
                )
                self.assertTrue(result.is_error, result.content)
                self.assertEqual(sidecar.read_bytes(), before)
            old = '"ngspice_version": "47"'
            result = await client.call_tool(
                "apply_project_edit",
                {
                    "project_id": PROJECT,
                    "path": "tests/electrical.json",
                    "expected_sha256": digest(sidecar),
                    "old_text": old,
                    "new_text": '"ngspice_version": "48"',
                },
            )
            self.assertFalse(result.is_error, result.content)
            self.assertIn("--depth electrical", result.structured_content["next_command"])
            changed = read_model(sidecar, ElectricalAnalysisContract)
            self.assertEqual(changed.ngspice_version, "48")
            self.assertEqual(
                changed.power,
                read_model(
                    self.root / ISLAND / "tests/electrical.json", ElectricalAnalysisContract
                ).power,
            )
            approved_sidecar = sidecar.read_bytes()
            model = "tests/electrical/startup.cir"
            read = mcp_files.read_project_file(self.mcp_root, PROJECT, model)
            result = await client.call_tool(
                "apply_project_edit",
                {
                    "project_id": PROJECT,
                    "path": model,
                    "expected_sha256": read.sha256,
                    "old_text": read.text.splitlines()[0],
                    "new_text": "* Explicit reviewed model note",
                },
            )
            self.assertFalse(result.is_error, result.content)
            self.assertEqual(sidecar.read_bytes(), approved_sidecar)
            stale = await client.call_tool(
                "apply_project_edit",
                {
                    "project_id": PROJECT,
                    "path": model,
                    "expected_sha256": read.sha256,
                    "old_text": "* Explicit reviewed model note",
                    "new_text": "* Stale replacement",
                },
            )
            self.assertTrue(stale.is_error)
        report = analyze(self.mcp_root, PROJECT)
        self.assertEqual(report.status, "FAIL")
        self.assertIn("stale reviewed model hash", report.checks[-1].detail)

    async def test_model_and_artifact_boundaries_reject_paths_without_writes(self) -> None:
        for value in (
            "../outside.cir",
            "/tmp/outside.cir",
            "README.md",
            "build/model.cir",
            "examples/projects/another-project/model.cir",
        ):
            with self.subTest(value=value), self.assertRaises((OSError, ValueError)):
                mcp_electrical.capture_electrical_inputs(
                    self.mcp_root, PROJECT, "invalid-model", (value,)
                )
        self.assertFalse((self.mcp_root / "build/electrical-inputs").exists())
        linked = self.mcp_root / ISLAND / "tests/linked.cir"
        linked.symlink_to(self.root / "README.md")
        with self.assertRaises(ValueError):
            mcp_electrical.capture_electrical_inputs(
                self.mcp_root,
                PROJECT,
                "linked-model",
                (linked.relative_to(self.mcp_root).as_posix(),),
            )
        with self.assertRaises(ValueError):
            mcp_files.read_project_file(self.mcp_root, PROJECT, "tests/linked.cir")
        for value in ("README.md", "../outside.json", "/tmp/summary.json"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                mcp_electrical.analyze_electrical(self.mcp_root, PROJECT, "bad-evidence", value)
        self.assertFalse((self.mcp_root / "build/electrical").exists())

    @unittest.skipIf(os.name == "nt", "POSIX FIFO")
    def test_nonregular_model_rejected_before_open_and_stale_deck_rejected(self) -> None:
        contract = install_fixture(self.root)
        case = simulation_cases(contract)[0]
        path = self.root / case.deck
        original = path.read_bytes()
        path.write_bytes(original + b"\n* source changed after review\n")
        with self.assertRaisesRegex(ValueError, "Stale reviewed model hash"):
            expanded_deck(self.root, case)
        path.unlink()
        os.mkfifo(path)
        with patch("kicad_tooling.hwrepo.electrical.os.open") as opened:
            with self.assertRaisesRegex(ValueError, "regular"):
                regular_input_bytes(path)
            with self.assertRaisesRegex(ValueError, "regular"):
                electrical_setup.capture_inputs(self.root, PROJECT, (case.deck,))
            opened.assert_not_called()
        report = analyze(self.root, PROJECT)
        self.assertEqual(report.status, "FAIL")
        self.assertIn("regular", report.checks[-1].detail)


if __name__ == "__main__":
    unittest.main()
