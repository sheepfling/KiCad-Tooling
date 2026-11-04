"""Exact KiCad 10.0.0/10.0.5 ERC-to-SVG fault, control, and hierarchy calibration."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from kicad_tooling.hwrepo.contract_coach import run_command
from kicad_tooling.hwrepo.contracts import read_kicad_erc_report, read_model, write_model
from kicad_tooling.hwrepo.discovery import load_config
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.findings_view import build_findings_view
from kicad_tooling.hwrepo.findings_view_mapping import erc_finding
from kicad_tooling.hwrepo.findings_view_models import ReviewDrawing
from kicad_tooling.hwrepo.findings_view_sheets import bind_schematic_drawings
from kicad_tooling.hwrepo.findings_view_svg import prepare_drawing
from kicad_tooling.hwrepo.models import CheckEvidence, ValidationSummary
from kicad_tooling.hwrepo.pcb_variant_population_capture import run_variant_native_command
from kicad_tooling.hwrepo.project_models import ProjectKind, ProjectManifest
from kicad_tooling.hwrepo.project_source_hashes import hash_project_sources as hashes
from kicad_tooling.hwrepo.schematic_geometry_source import schematic_root, schematic_scalar
from tests.mcp_parity_support import parity_workspace
from tests.pcb_native_fixture_support import NATIVE_KICAD_PROJECTS
from tests.support import reference_root

pytestmark = [
    pytest.mark.native_kicad,
    pytest.mark.slow,
    pytest.mark.template_checkout,
    pytest.mark.skipif(
        os.environ.get("KICAD_RUN_NATIVE_PCB_FIXTURES") != "1",
        reason="exact KiCad ERC calibration runs in the opt-in native fixture lane",
    ),
]

FIXTURES = Path(__file__).parent / "fixtures/design_lint"


def _export(root: Path, output: Path, image: str, source: Path) -> Path:
    output.mkdir(parents=True)
    relative = source.relative_to(root).as_posix()
    erc = run_variant_native_command(
        root,
        output,
        image,
        "kicad-cli",
        (
            "sch",
            "erc",
            "--format",
            "json",
            "--severity-all",
            "--exit-code-violations",
            "--output",
            "/output/erc.json",
            f"/work/{relative}",
        ),
    )
    assert erc.returncode in {0, 5} and erc.error is None, erc.stderr
    svg = run_variant_native_command(
        root,
        output,
        image,
        "kicad-cli",
        ("sch", "export", "svg", "--output", "/output", f"/work/{relative}"),
    )
    assert svg.returncode == 0 and svg.error is None, svg.stderr
    return output / "erc.json"


@pytest.mark.parametrize("project,version", NATIVE_KICAD_PROJECTS)
def test_root_erc_fault_and_control_match_svg(tmp_path: Path, project: str, version: str) -> None:
    template = reference_root()
    config = load_config(template, f"examples/projects/{project}/project.json")
    assert config.kicad_version == version
    root = tmp_path / "repository"
    source_dir = root / "source"
    source_dir.mkdir(parents=True)
    original = (FIXTURES / "label-near-wire-endpoint.kicad_sch").read_text(encoding="utf-8")
    assert original.count('(label "CONTROL_NET" (at 102.1 71.12 0)') == 1
    for case, text in (
        ("fault", original),
        (
            "control",
            original.replace(
                '(label "CONTROL_NET" (at 102.1 71.12 0)',
                '(label "CONTROL_NET" (at 101.6 71.12 0)',
            ),
        ),
    ):
        source = source_dir / f"{case}.kicad_sch"
        source.write_text(text, encoding="utf-8")
        output = root / "build" / f"{version}-{case}"
        erc_path = _export(root, output, config.image, source)
        report = read_kicad_erc_report(erc_path)
        assert report.kicad_version == version
        assert report.coordinate_units == "mm" and report.source == source.name
        dangling = tuple(item for item in report.violations if item.type == "label_dangling")
        if case == "control":
            assert not dangling
            continue
        assert len(dangling) == 1
        svg = output / f"{case}.svg"
        picture = prepare_drawing(svg.read_bytes(), "schematic")
        assert picture.can_map_mm
        relative = source.relative_to(root).as_posix()
        drawing = ReviewDrawing(
            kind="schematic",
            file=svg.name,
            source_artifact=f"schematic/{svg.name}",
            sha256=digest(svg),
            width_mm=picture.width,
            height_mm=picture.height,
            mapping_supported=picture.can_map_mm,
        )
        bound, bindings, _, issues = bind_schematic_drawings(
            root,
            relative,
            version,
            {relative: digest(source)},
            ((drawing, picture.content),),
        )
        assert not issues and len(bindings) == 1
        mapped_drawing = bound[0][0]
        document = schematic_root(source.read_bytes())
        instance = "/" + schematic_scalar(document.text, document.root, "uuid")
        assert mapped_drawing.sheet_instance_path == instance
        mapped = erc_finding(
            dangling[0],
            report,
            relative,
            {instance: mapped_drawing},
            {relative: digest(source)},
        )
        assert mapped.unmapped_reason is None and len(mapped.markers) == 1
        assert (mapped.markers[0].x_mm, mapped.markers[0].y_mm) == pytest.approx((102.1, 71.12))
        assert mapped.evidence["coordinate_conversion"] == (
            f"KiCad {version} ERC position ×100 to schematic mm",
        )
        root_svg = ET.fromstring(picture.content)
        labels = [
            item
            for item in root_svg.iter()
            if item.tag.endswith("text") and item.text == "CONTROL_NET"
        ]
        assert any(float(item.attrib["x"]) == pytest.approx(102.1) for item in labels)


@pytest.mark.parametrize("project,version", NATIVE_KICAD_PROJECTS)
def test_repeated_child_sheets_remain_unmapped_without_unique_svg_binding(
    tmp_path: Path, project: str, version: str
) -> None:
    config = load_config(reference_root(), f"examples/projects/{project}/project.json")
    assert config.kicad_version == version
    root = tmp_path / "repository"
    source_dir = root / "source"
    source_dir.mkdir(parents=True)
    for name in ("repeated-sheet-root.kicad_sch", "repeated-channel.kicad_sch"):
        shutil.copyfile(FIXTURES / "repeated-sheet" / name, source_dir / name)
    source = source_dir / "repeated-sheet-root.kicad_sch"
    output = root / "build" / version
    report = read_kicad_erc_report(_export(root, output, config.image, source))
    files = sorted(output.glob("*.svg"))
    assert len(files) == 3
    source_hashes = {
        path.relative_to(root).as_posix(): digest(path) for path in source_dir.glob("*.kicad_sch")
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
    bound, bindings, _, _ = bind_schematic_drawings(
        root,
        source.relative_to(root).as_posix(),
        version,
        source_hashes,
        drawings,
    )
    assert not bindings and all(item.sheet_instance_path is None for item, _ in bound)
    child = next(item for item in report.violations if item.sheet_path.startswith("/Instance"))
    unmapped = erc_finding(
        child,
        report,
        source.relative_to(root).as_posix(),
        {},
        source_hashes,
    )
    assert not unmapped.markers and unmapped.unmapped_reason


@pytest.mark.parametrize("project,version", NATIVE_KICAD_PROJECTS)
def test_source_bound_findings_view_places_native_root_erc_marker(
    tmp_path: Path, project: str, version: str
) -> None:
    root, island, _ = parity_workspace(tmp_path)
    manifest_path = island / "project.json"
    manifest = read_model(manifest_path, ProjectManifest)
    if version != "10.0.0":
        write_model(manifest_path, manifest.model_copy(update={"toolchain_id": "kicad-10.0.5"}))
    config = load_config(root, manifest_path)
    assert config.kicad_version == version
    source = island / "kicad/controller.kicad_sch"
    shutil.copyfile(FIXTURES / "label-near-wire-endpoint.kicad_sch", source)
    current = hashes(root, config.source_roots)
    native_dir = root / "build/native-erc"
    (native_dir / "schematic").mkdir(parents=True)
    relative = source.relative_to(root).as_posix()
    common = (
        "docker",
        "run",
        "--rm",
        "--platform",
        "linux/amd64",
        "--network",
        "none",
        "--read-only",
        "--tmpfs",
        "/tmp:rw,nosuid,nodev,size=64m",
        "--user",
        f"{os.getuid()}:{os.getgid()}",
        "-e",
        "HOME=/tmp",
        "-v",
        f"{root}:/work:ro",
        "-v",
        f"{native_dir}:/work/build/native-erc:rw",
        "-w",
        "/work",
        "--entrypoint",
        "kicad-cli",
        config.image,
    )
    erc = run_command(
        root,
        (
            *common,
            "sch",
            "erc",
            "--format",
            "json",
            "--severity-all",
            "--exit-code-violations",
            "--output",
            "/work/build/native-erc/erc.json",
            f"/work/{relative}",
        ),
        timeout=600,
    )
    assert erc.returncode == 5 and erc.error is None, erc.stderr
    write_model(native_dir / "erc.command.json", erc)
    svg = run_command(
        root,
        (
            *common,
            "sch",
            "export",
            "svg",
            "--output",
            "/work/build/native-erc/schematic",
            f"/work/{relative}",
        ),
        timeout=600,
    )
    assert svg.returncode == 0 and svg.error is None, svg.stderr
    write_model(native_dir / "schematic_svg.command.json", svg)
    drawing_path = native_dir / "schematic/controller.svg"
    assert drawing_path.is_file()
    summary_path = native_dir / "summary.json"
    write_model(
        summary_path,
        ValidationSummary(
            timestamp_utc="2026-11-03T00:00:00+00:00",
            checked_commit="LOCAL_UNBOUND",
            project_id="controller",
            project_kind=ProjectKind.PCB,
            checks={
                "source_scope": CheckEvidence(status="PASS", source_hashes=current),
                "source_unchanged": CheckEvidence(status="PASS", source_hashes=current),
                "toolchain": CheckEvidence(
                    status="PASS", observed_version=config.kicad_version, image=config.image
                ),
                "erc": CheckEvidence(status="FAIL", returncode=5),
                "schematic_svg": CheckEvidence(
                    status="PASS", returncode=0, files=("schematic/controller.svg",)
                ),
            },
            status="FAIL",
            artifacts_sha256={
                name: digest(native_dir / name)
                for name in (
                    "erc.json",
                    "erc.command.json",
                    "schematic/controller.svg",
                    "schematic_svg.command.json",
                )
            },
        ),
    )
    view = build_findings_view(
        root, "controller", summary_path, Path(f"build/findings-view-erc-{version}")
    )
    dangling = next(item for item in view.findings if item.rule == "label_dangling")
    assert dangling.unmapped_reason is None and len(dangling.markers) == 1
    assert (dangling.markers[0].x_mm, dangling.markers[0].y_mm) == pytest.approx((102.1, 71.12))
    assert dangling.markers[0].drawing_file == "schematic-1.svg"
    assert 'id="marker-' in (Path(view.output_directory) / "index.html").read_text(encoding="utf-8")
