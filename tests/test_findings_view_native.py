"""Optional exact-native calibration for PCB DRC coordinates and SVG geometry."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import replace
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from kicad_tooling.hwrepo.contracts import read_kicad_drc_findings, read_kicad_erc_report
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.findings_view_mapping import drc_finding, erc_finding
from kicad_tooling.hwrepo.findings_view_models import ReviewDrawing
from kicad_tooling.hwrepo.findings_view_sheets import bind_schematic_drawings
from kicad_tooling.hwrepo.findings_view_svg import prepare_drawing, schematic_title_identity
from kicad_tooling.hwrepo.schematic_geometry_source import schematic_root, schematic_scalar
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


def test_native_reused_sheet_svg_titles_bind_distinct_instances(tmp_path: Path) -> None:
    executable = os.environ.get("KICAD_FINDINGS_CLI")
    if not executable:
        pytest.skip("Set KICAD_FINDINGS_CLI for exact KiCad 10.0.6 sheet calibration")
    version = subprocess.run(
        [executable, "version"], check=True, capture_output=True, text=True
    ).stdout.strip()
    if version != "10.0.6":
        pytest.skip(f"KiCad {version} has no calibrated hierarchical SVG title mapping")
    fixture = Path(__file__).parent / "fixtures/design_lint/repeated-sheet"
    project = tmp_path / "project"
    project.mkdir()
    for name in ("repeated-sheet-root.kicad_sch", "repeated-channel.kicad_sch"):
        shutil.copy2(fixture / name, project / name)
    output = tmp_path / "svg"
    output.mkdir()
    subprocess.run(
        [
            executable,
            "sch",
            "export",
            "svg",
            "--output",
            str(output),
            str(project / "repeated-sheet-root.kicad_sch"),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    files = sorted(output.glob("*.svg"))
    assert len(files) == 3
    identities = [
        schematic_title_identity(prepare_drawing(path.read_bytes(), "schematic").content)
        for path in files
    ]
    assert {item[0] for item in identities if item is not None} == {
        (),
        ("InstanceA",),
        ("InstanceB",),
    }
    sources = {
        name: digest(project / name)
        for name in ("repeated-sheet-root.kicad_sch", "repeated-channel.kicad_sch")
    }
    drawings = tuple(
        (
            ReviewDrawing(
                kind="schematic",
                file=f"schematic-{index}.svg",
                source_artifact=f"schematic/{path.name}",
                sha256=digest(path),
                width_mm=picture.width,
                height_mm=picture.height,
                mapping_supported=picture.can_map_mm,
            ),
            picture.content,
        )
        for index, path in enumerate(files, 1)
        for picture in (prepare_drawing(path.read_bytes(), "schematic"),)
    )
    bound, bindings, tree_hash, issues = bind_schematic_drawings(
        project, "repeated-sheet-root.kicad_sch", version, sources, drawings
    )
    assert not issues and tree_hash is not None
    assert len(bindings) == 3
    matched = {drawing.sheet_path: drawing for drawing, _ in bound}
    assert matched[("InstanceA",)].schematic_source == "repeated-channel.kicad_sch"
    assert matched[("InstanceB",)].schematic_source == "repeated-channel.kicad_sch"
    assert (
        matched[("InstanceA",)].sheet_instance_path != matched[("InstanceB",)].sheet_instance_path
    )
    erc_path = tmp_path / "repeated-erc.json"
    erc_process = subprocess.run(
        [
            executable,
            "sch",
            "erc",
            "--format",
            "json",
            "--severity-all",
            "--exit-code-violations",
            "--output",
            str(erc_path),
            str(project / "repeated-sheet-root.kicad_sch"),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert erc_process.returncode == 5, erc_process.stderr
    erc = read_kicad_erc_report(erc_path)
    child = next(
        item
        for item in erc.violations
        if item.sheet_path == "/InstanceA/" and item.type == "pin_not_connected"
    )
    by_instance = {
        drawing.sheet_instance_path: drawing
        for drawing, _ in bound
        if drawing.sheet_instance_path is not None
    }
    finding = erc_finding(child, erc, "repeated-sheet-root.kicad_sch", by_instance, sources)
    assert finding.unmapped_reason is None and len(finding.markers) == 1
    marker = finding.markers[0]
    assert (marker.x_mm, marker.y_mm) == pytest.approx((76.2, 81.28))
    assert marker.drawing_file == matched[("InstanceA",)].file
    assert marker.drawing_file != matched[("InstanceB",)].file


def test_native_erc_positions_match_fault_svg_and_control(tmp_path: Path) -> None:
    executable = os.environ.get("KICAD_FINDINGS_CLI")
    if not executable:
        pytest.skip("Set KICAD_FINDINGS_CLI for exact KiCad 10.0.6 ERC calibration")
    version = subprocess.run(
        [executable, "version"], check=True, capture_output=True, text=True
    ).stdout.strip()
    if version != "10.0.6":
        pytest.skip(f"KiCad {version} has no calibrated ERC-to-SVG mapping")
    fixture = Path(__file__).parent / "fixtures/design_lint/label-near-wire-endpoint.kicad_sch"
    source_text = fixture.read_text(encoding="utf-8")
    assert source_text.count('(label "CONTROL_NET" (at 102.1 71.12 0)') == 1
    sources = {
        "fault": source_text,
        "control": source_text.replace(
            '(label "CONTROL_NET" (at 102.1 71.12 0)',
            '(label "CONTROL_NET" (at 101.6 71.12 0)',
        ),
    }
    for name, content in sources.items():
        directory = tmp_path / name
        directory.mkdir()
        source = directory / f"{name}.kicad_sch"
        source.write_text(content, encoding="utf-8")
        erc_path = directory / "erc.json"
        erc_process = subprocess.run(
            [
                executable,
                "sch",
                "erc",
                "--format",
                "json",
                "--severity-all",
                "--exit-code-violations",
                "--output",
                str(erc_path),
                str(source),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        assert erc_process.returncode in {0, 5}, erc_process.stderr
        subprocess.run(
            [executable, "sch", "export", "svg", "--output", str(directory), str(source)],
            check=True,
            capture_output=True,
            text=True,
        )
        report = read_kicad_erc_report(erc_path)
        picture = prepare_drawing((directory / f"{name}.svg").read_bytes(), "schematic")
        text, source_root = schematic_root(source.read_bytes())
        sheet_uuid = "/" + schematic_scalar(text, source_root, "uuid")
        assert report.coordinate_units == "mm" and report.source == source.name
        assert picture.can_map_mm
        assert all(item.sheet_uuid_path == sheet_uuid for item in report.violations)
        dangling = [item for item in report.violations if item.type == "label_dangling"]
        if name == "control":
            assert not dangling
            continue
        assert len(dangling) == 1
        drawing = ReviewDrawing(
            kind="schematic",
            file="fault.svg",
            source_artifact="schematic/fault.svg",
            sha256=digest(directory / "fault.svg"),
            width_mm=picture.width,
            height_mm=picture.height,
            mapping_supported=picture.can_map_mm,
            sheet_instance_path=sheet_uuid,
            schematic_source=source.name,
            schematic_source_sha256=digest(source),
        )
        finding = erc_finding(
            dangling[0], report, source.name, {sheet_uuid: drawing}, {source.name: digest(source)}
        )
        assert finding.unmapped_reason is None and len(finding.markers) == 1
        marker = finding.markers[0]
        assert (marker.x_mm, marker.y_mm) == pytest.approx((102.1, 71.12))
        root = ET.fromstring(picture.content)
        label_text = [
            item for item in root.iter() if item.tag.endswith("text") and item.text == "CONTROL_NET"
        ]
        assert any(float(item.attrib["x"]) == pytest.approx(marker.x_mm) for item in label_text)
        for changed in (
            replace(report, kicad_version="10.0.5"),
            replace(report, coordinate_units="unknown"),
        ):
            unmapped = erc_finding(
                dangling[0],
                changed,
                source.name,
                {sheet_uuid: drawing},
                {source.name: digest(source)},
            )
            assert not unmapped.markers and unmapped.unmapped_reason
