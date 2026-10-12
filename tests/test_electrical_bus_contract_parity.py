"""CLI/MCP parity for combined authored bus contracts."""

from __future__ import annotations

import asyncio
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from mcp import Client

from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    ContractCoachReport,
    ElectricalAnalysisContract,
    ElectricalAnalysisReport,
    ValidationSummary,
)
from tests import electrical_i2c_support as i2c_support
from tests.electrical_can_support import can_split_termination_requirement
from tests.electrical_parity_support import ElectricalParityHarness, parity_harness  # noqa: F401
from tests.electrical_simulation_support import ISLAND, NA, PROJECT
from tests.electrical_spi_support import spi_requirement
from tests.electrical_usb_c_support import usb_c_requirement

pytestmark = [
    pytest.mark.template_checkout,
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.parity_lint,
    pytest.mark.slow,
]


def _netlist_fixture() -> str:
    return (
        Path(__file__).parent / "fixtures/electrical/multi-bus-contract-parity/netlist.xml"
    ).read_text(encoding="utf-8")


def _faulty_bus_netlist(source: str) -> str:
    root = ET.fromstring(source)
    replacements = {
        "R1": "1k",
        "R2": "1k",
        "R4": "100R",
        "C1": "120pF",
        "C2": "2.2uF",
        "R6": "100k",
    }
    components = {
        component.get("ref"): component for component in root.findall("./components/comp")
    }
    if set(replacements) - set(components):
        raise ValueError("Synthetic multi-bus fixture is missing a fault-target component")
    for reference, value in replacements.items():
        value_node = components[reference].find("value")
        if value_node is None:
            raise ValueError(f"Synthetic fault target {reference} has no value")
        value_node.text = value
    nets = root.find("nets")
    if nets is None:
        raise ValueError("Synthetic multi-bus fixture has no nets")
    spi_cs1 = next((net for net in nets.findall("net") if net.get("name") == "SPI_CS1"), None)
    if spi_cs1 is None:
        raise ValueError("Synthetic multi-bus fixture has no SPI_CS1 net")
    moved = [
        node
        for node in spi_cs1.findall("node")
        if node.get("ref") == "U12" and node.get("pin") == "4"
    ]
    if len(moved) != 1:
        raise ValueError("Synthetic fault target U12.4 must occur once on SPI_CS1")
    spi_cs1.remove(moved[0])
    wrong_cs = ET.SubElement(nets, "net", {"name": "WRONG_CS"})
    wrong_cs.append(moved[0])
    return ET.tostring(root, encoding="unicode")


async def _run_bus_requirements_match_cli_and_mcp_analysis(parity: ElectricalParityHarness) -> None:
    parity.configured()
    netlist_xml = _netlist_fixture()
    spi = spi_requirement(
        device2_miso="not_present",
        controller_reference="U10",
        device_references=("U11", "U12"),
        device2_symbol="Synthetic:SpiWriteOnly",
    )
    pullups = i2c_support.i2c_pullup_requirement()
    tolerance_window = (
        i2c_support.i2c_pullup_window_requirement(
            maximum_per_resistor_tolerance_percent=5.0,
            resistor_tolerance_basis="Synthetic resistor tolerance for every pull-up element",
        )
        .buses[0]
        .sda.electrical_window
    )
    assert tolerance_window is not None
    bus = pullups.buses[0]
    pullups = pullups.model_copy(
        update={
            "buses": (
                bus.model_copy(
                    update={
                        "sda": bus.sda.model_copy(update={"electrical_window": tolerance_window}),
                        "scl": bus.scl.model_copy(update={"electrical_window": tolerance_window}),
                    }
                ),
            )
        }
    )
    for root in (parity.root, parity.mcp_root):
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
                    "artifacts_sha256": {**summary.artifacts_sha256, "netlist.xml": digest(netlist)}
                }
            ),
        )
    summary_arg = "build/native/controller/summary.json"
    process = await parity.cli(
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
        raise AssertionError(f"native netlist evidence blocked: {evidence.issues}")
    assert process.returncode == 0, process.stderr + process.stdout
    cli_report = ElectricalAnalysisReport.model_validate_json(process.stdout)
    async with Client(create_server(parity.mcp_root, allow_checks=True), mode="legacy") as client:
        result = await client.call_tool(
            "analyze_electrical",
            {"project_id": PROJECT, "view_id": "i2c-contract-pass", "native_summary": summary_arg},
        )
    assert not result.is_error, result.content
    mcp_report = ElectricalAnalysisReport.model_validate_json(json.dumps(result.structured_content))
    assert cli_report.checks == mcp_report.checks
    checks = {item.id: item for item in cli_report.checks}
    assert checks["i2c-pullup/control/sda"].observed == 2350
    assert checks["i2c-pullup/control/scl"].observed == 4700
    assert (
        checks["i2c-pullup/control/sda/electrical-window/minimum-sink-resistance"].status == "PASS"
    )
    assert (
        checks["i2c-pullup/control/sda/electrical-window/maximum-rise-resistance"].status == "PASS"
    )
    assert checks["can-termination/fieldbus/local"].status == "PASS"
    assert checks["can-termination/fieldbus/local/midpoint-capacitor"].status == "PASS"
    assert checks["usb-c/host-port/connector-pins"].status == "PASS"
    assert checks["usb-c/host-port/cc1-attachment"].status == "PASS"
    assert checks["usb-c/host-port/protection/D9"].status == "PASS"
    assert checks["usb-c/host-port/vbus-capacitance"].status == "PASS"
    assert checks["usb-c/host-port/vbus-capacitance"].observed == 4700
    assert checks["spi/control/controller-identity"].status == "PASS"
    assert checks["spi/control/device/sensor/route/sck"].status == "PASS"
    assert checks["spi/control/device/memory/route/miso"].status == "NOT_APPLICABLE"
    faulty_netlist_xml = _faulty_bus_netlist(netlist_xml)
    for root in (parity.root, parity.mcp_root):
        native = root / "build/native/controller"
        netlist = native / "netlist.xml"
        netlist.write_text(faulty_netlist_xml, encoding="utf-8")
        summary_path = native / "summary.json"
        summary = read_model(summary_path, ValidationSummary)
        write_model(
            summary_path,
            summary.model_copy(
                update={
                    "artifacts_sha256": {**summary.artifacts_sha256, "netlist.xml": digest(netlist)}
                }
            ),
        )
    process = await parity.cli(
        "kicad_tooling.electrical",
        "--project",
        PROJECT,
        "--native-summary",
        summary_arg,
        "--output",
        "build/electrical/i2c-contract-fault",
    )
    assert process.returncode == 1, process.stderr + process.stdout
    cli_fault = ElectricalAnalysisReport.model_validate_json(process.stdout)
    async with Client(create_server(parity.mcp_root, allow_checks=True), mode="legacy") as client:
        result = await client.call_tool(
            "analyze_electrical",
            {"project_id": PROJECT, "view_id": "i2c-contract-fault", "native_summary": summary_arg},
        )
    assert not result.is_error, result.content
    mcp_fault = ElectricalAnalysisReport.model_validate_json(json.dumps(result.structured_content))
    assert cli_fault.checks == mcp_fault.checks
    fault_checks = {item.id: item for item in cli_fault.checks}
    assert fault_checks["i2c-pullup/control/sda"].status == "FAIL"
    assert fault_checks["i2c-pullup/control/sda"].observed == 500
    assert fault_checks["can-termination/fieldbus/local"].status == "FAIL"
    assert fault_checks["can-termination/fieldbus/local/midpoint-capacitor"].status == "FAIL"
    assert fault_checks["usb-c/host-port/cc1-attachment"].status == "FAIL"
    assert fault_checks["usb-c/host-port/vbus-capacitance"].status == "FAIL"
    assert fault_checks["usb-c/host-port/vbus-capacitance"].observed == 2200
    assert fault_checks["spi/control/device/memory/pins"].status == "FAIL"


def test_bus_requirements_match_cli_and_mcp_analysis(parity: ElectricalParityHarness) -> None:
    asyncio.run(_run_bus_requirements_match_cli_and_mcp_analysis(parity))
