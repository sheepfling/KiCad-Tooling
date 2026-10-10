"""Shared pytest helpers for schematic geometry lanes."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.schematic_geometry import (
    SUPPORTED_KICAD_VERSION,
    scan_schematic_geometry_tree,
    scan_wire_ends_on_pin_lines,
)


class SchematicGeometryHelpers:
    def scan(
        self,
        source: bytes,
        *,
        unconnected_pins: frozenset[str] = frozenset({"R1.1"}),
        version: str = SUPPORTED_KICAD_VERSION,
    ):
        return scan_wire_ends_on_pin_lines(
            source,
            source_path="synthetic/near-miss-pin-line.kicad_sch",
            kicad_version=version,
            unconnected_pins=unconnected_pins,
        )


class NativeSchematicGeometryHelpers(SchematicGeometryHelpers):
    @pytest.fixture(autouse=True)
    def _use_exact_native_cli(self, native_schematic_geometry_toolchain: tuple[Path, str]) -> None:
        self.cli, self.kicad_version = native_schematic_geometry_toolchain

    def native_scan(
        self,
        fixture: Path | bytes,
        *,
        source_name: str | None = None,
        related_sources: tuple[Path, ...] = (),
        scan_hierarchy: bool = False,
    ) -> tuple[object, dict[str, object], dict[str, object]]:
        with tempfile.TemporaryDirectory(prefix="schematic-geometry-native-") as directory:
            root = Path(directory)
            if isinstance(fixture, Path):
                source_path = root / fixture.name
                shutil.copyfile(fixture, source_path)
                for related_source in related_sources:
                    shutil.copyfile(related_source, root / related_source.name)
            else:
                source_path = root / (source_name or "synthetic.kicad_sch")
                source_path.write_bytes(fixture)
                if related_sources:
                    raise ValueError("Related schematic files require a path-backed root fixture")
            netlist_path = root / "netlist.xml"
            erc_path = root / "erc.json"
            commands = (
                (
                    str(self.cli),
                    "sch",
                    "export",
                    "netlist",
                    "--format",
                    "kicadxml",
                    "--output",
                    str(netlist_path),
                    str(source_path),
                ),
                (
                    str(self.cli),
                    "sch",
                    "erc",
                    "--format",
                    "json",
                    "--output",
                    str(erc_path),
                    str(source_path),
                ),
            )
            for command in commands:
                result = subprocess.run(command, capture_output=True, text=True, check=False)
                assert result.returncode == 0, result.stderr or result.stdout

            netlist_root = ET.parse(netlist_path).getroot()
            unconnected = frozenset(
                f"{node.attrib['ref']}.{node.attrib['pin']}"
                for net in netlist_root.findall("./nets/net")
                if net.attrib.get("name", "").startswith("unconnected-")
                for node in net.findall("node")
            )
            erc = json.loads(erc_path.read_text(encoding="utf-8"))
            source = source_path.read_bytes()
            if scan_hierarchy:
                source_files = {source_path.name: source}
                source_files.update(
                    {related.name: related.read_bytes() for related in related_sources}
                )
                scan = scan_schematic_geometry_tree(
                    source_files,
                    root_path=source_path.name,
                    project_directory=".",
                    project_name=source_path.stem,
                    kicad_version=self.kicad_version,
                    unconnected_pins=unconnected,
                )
            else:
                scan = scan_wire_ends_on_pin_lines(
                    source,
                    source_path=source_path.name,
                    kicad_version=self.kicad_version,
                    unconnected_pins=unconnected,
                )
            return scan, netlist_root, erc

    def native_svg(self, fixture: bytes, *, source_name: str) -> ET.Element:
        with tempfile.TemporaryDirectory(prefix="schematic-text-svg-") as directory:
            root = Path(directory)
            source_path = root / source_name
            source_path.write_bytes(fixture)
            output = root / "svg"
            result = subprocess.run(
                (
                    str(self.cli),
                    "sch",
                    "export",
                    "svg",
                    str(source_path),
                    "--output",
                    str(output),
                ),
                capture_output=True,
                text=True,
                check=False,
            )
            assert result.returncode == 0, result.stderr or result.stdout
            svg_path = output / f"{source_path.stem}.svg"
            return ET.parse(svg_path).getroot()
