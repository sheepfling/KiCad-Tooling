"""Shared source-bound fixtures for CLI/MCP electrical parity tests."""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

from kicad_tooling.hwrepo.contracts import write_model
from kicad_tooling.hwrepo.models import (
    GroundDomain,
    GroundingAnalysis,
    NetlistContract,
)
from tests import test_contract_coach as coach_fixture
from tests.test_electrical import ISLAND, NA, install_fixture


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
