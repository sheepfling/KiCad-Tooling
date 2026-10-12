"""Shared source-bound fixtures for CLI/MCP electrical parity tests."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

import pytest
from mcp import Client

from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import (
    ElectricalAnalysisContract,
    ElectricalAnalysisReport,
    GroundDomain,
    GroundingAnalysis,
    NetlistContract,
    ValidationSummary,
)
from tests import test_contract_coach as coach_fixture
from tests.electrical_simulation_support import ISLAND, NA, PROJECT, install_fixture


def contract_netlist_xml(observed: NetlistContract) -> str:
    """Serialize typed synthetic netlist evidence for electrical contract tests."""
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


class ElectricalParityHarness:
    """Create isolated template-backed CLI and MCP projects for parity cases."""

    def __init__(self) -> None:
        self.fixture = coach_fixture.ContractCoachTests()
        self.fixture.setUp()
        self.root = self.fixture.root
        self.mcp_root = self.root.parent / "mcp-repository"
        try:
            shutil.copytree(self.root, self.mcp_root)
        except Exception:
            self.close()
            raise

    def close(self) -> None:
        self.fixture.doCleanups()

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

    async def analyze_electrical(
        self, view_id: str
    ) -> tuple[ElectricalAnalysisReport, ElectricalAnalysisReport, int]:
        """Run one saved electrical view through CLI and MCP and compare outputs."""
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
        async with Client(create_server(self.mcp_root, allow_checks=True), mode="legacy") as client:
            result = await client.call_tool(
                "analyze_electrical",
                {"project_id": PROJECT, "view_id": view_id, "native_summary": summary},
            )
        assert not result.is_error, result.content
        mcp_report = ElectricalAnalysisReport.model_validate_json(
            json.dumps(result.structured_content)
        )
        assert cli_report.checks == mcp_report.checks
        return cli_report, mcp_report, process.returncode

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

    def install_netlist_contract(
        self, observed: NetlistContract, contract_updates: dict[str, object]
    ) -> None:
        """Install one typed netlist and its reviewed contract update on both surfaces."""
        serialized = contract_netlist_xml(observed)
        for root in (self.root, self.mcp_root):
            contract_path = root / ISLAND / "tests/electrical.json"
            contract = read_model(contract_path, ElectricalAnalysisContract)
            write_model(contract_path, contract.model_copy(update=contract_updates))
            netlist = root / "build/native/controller/netlist.xml"
            netlist.write_text(serialized, encoding="utf-8")
            summary_path = root / "build/native/controller/summary.json"
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


@pytest.fixture(name="parity")
def parity_harness():
    """Provide one isolated CLI/MCP project pair to a parity test."""
    harness = ElectricalParityHarness()
    try:
        yield harness
    finally:
        harness.close()
