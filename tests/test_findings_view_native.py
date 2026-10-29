"""Optional exact-native calibration for PCB DRC coordinates and SVG geometry."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from kicad_tooling.hwrepo.contracts import read_kicad_drc_findings
from kicad_tooling.hwrepo.findings_view_mapping import drc_finding
from kicad_tooling.hwrepo.findings_view_models import ReviewDrawing
from kicad_tooling.hwrepo.findings_view_svg import prepare_drawing
from tests.support import reference_root

pytestmark = [pytest.mark.native_kicad, pytest.mark.template_checkout]


def test_native_pcb_drc_markers_match_exported_pad_centers(tmp_path: Path) -> None:
    executable = os.environ.get("KICAD_FINDINGS_CLI")
    if not executable:
        pytest.skip("Set KICAD_FINDINGS_CLI to an exact KiCad 10 CLI for native calibration")
    version = subprocess.run(
        [executable, "version"], check=True, capture_output=True, text=True
    ).stdout.strip()
    if version not in {"10.0.0", "10.0.5", "10.0.6"}:
        pytest.skip(f"KiCad {version} is outside the explorer's calibrated versions")
    source = reference_root() / "examples/projects/controller/kicad"
    directory = tmp_path / "controller"
    shutil.copytree(source, directory)
    board = directory / "controller.kicad_pcb"
    lines = board.read_text(encoding="utf-8").splitlines(keepends=True)
    target = "93a92d2f-4c52-59f5-b593-aed3319c9827"
    assert sum(target in line for line in lines) == 1
    board.write_text("".join(line for line in lines if target not in line), encoding="utf-8")
    drc = tmp_path / "drc.json"
    svg = tmp_path / "pcb.svg"
    process = subprocess.run(
        [
            executable,
            "pcb",
            "drc",
            "--format",
            "json",
            "--severity-all",
            "--exit-code-violations",
            "--refill-zones",
            "--output",
            str(drc),
            str(board),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert process.returncode == 5, process.stderr
    subprocess.run(
        [
            executable,
            "pcb",
            "export",
            "svg",
            "--layers",
            "F.Cu,F.SilkS,Edge.Cuts,Cmts.User",
            "--output",
            str(svg),
            str(board),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    native = read_kicad_drc_findings(drc)
    picture = prepare_drawing(svg.read_bytes(), "pcb")
    drawing = ReviewDrawing(
        kind="pcb",
        file="pcb.svg",
        source_artifact="pcb.svg",
        sha256="0" * 64,
        width_mm=picture.width,
        height_mm=picture.height,
        mapping_supported=picture.can_map_mm,
    )
    finding = next(item for item in native.findings if item.category == "unconnected_items")
    mapped = drc_finding(finding, drawing, version, native.units)
    assert [(marker.x_mm, marker.y_mm) for marker in mapped.markers] == [
        (100.0, 100.0),
        (100.0, 110.0),
    ]
    root = ET.fromstring(picture.content)
    centers = {
        (float(node.attrib["cx"]), float(node.attrib["cy"]))
        for node in root.iter("{http://www.w3.org/2000/svg}circle")
        if "cx" in node.attrib and "cy" in node.attrib
    }
    assert {(marker.x_mm, marker.y_mm) for marker in mapped.markers} <= centers
