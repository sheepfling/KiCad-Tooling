"""Source-matched BOM navigation and CLI/MCP export parity."""

from __future__ import annotations

from pathlib import Path

import pytest
from mcp import Client

from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.cross_probe import (  # pyright: ignore[reportPrivateUsage]
    _entry,
    build_cross_probe,
)
from kicad_tooling.hwrepo.cross_probe_board import board_footprint_anchors
from kicad_tooling.hwrepo.cross_probe_html import render_cross_probe
from kicad_tooling.hwrepo.cross_probe_models import CrossProbeReport
from kicad_tooling.hwrepo.cross_probe_schematic import (
    schematic_drawing_bindings,
    schematic_symbol_anchors,
)
from kicad_tooling.hwrepo.discovery import load_config
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.findings_view import build_findings_view
from kicad_tooling.hwrepo.findings_view_models import FindingsViewReport, ReviewDrawing
from kicad_tooling.hwrepo.mcp_server import create_server
from kicad_tooling.hwrepo.models import PurchasingComponent, PurchasingPlan, PurchasingReport
from kicad_tooling.hwrepo.purchasing_preference_models import PurchasingPreferences
from kicad_tooling.validate import hashes
from tests.findings_view_support import add_native_review, select_schematic_geometry_toolchain
from tests.mcp_parity_support import (
    McpParityHarness,
    parity_native_evidence,
    parity_workspace,
    run_mcp_parity,
)

pytestmark = pytest.mark.template_checkout


def saved_inputs(root: Path, island: Path) -> tuple[Path, Path]:
    select_schematic_geometry_toolchain(island)
    native = parity_native_evidence(root, island)
    add_native_review(root, native)
    findings = build_findings_view(
        root, "controller", native, Path("build/findings-view/cross-probe")
    )
    config = load_config(root, "examples/projects/controller/project.json")
    source = hashes(root, config.source_roots)
    directory = root / "build/parts/cross-probe"
    directory.mkdir(parents=True)
    (directory / "netlist.xml").write_bytes((native.parent / "netlist.xml").read_bytes())
    plan = PurchasingPlan(
        status="NEEDS_PARTS",
        preferences=PurchasingPreferences(),
        components=(
            PurchasingComponent(
                reference="R1", value="1k", footprint="Pilot:R_Test", part_id="resistor-1k"
            ),
            PurchasingComponent(reference="R2", value="2k", footprint="Pilot:R_Test", dnp=True),
            PurchasingComponent(reference="U1", value="IC", footprint="Fixture:U"),
            PurchasingComponent(reference="C1", value="1u", footprint="Fixture:C"),
            PurchasingComponent(reference="C1", value="1u", footprint="Fixture:C"),
            PurchasingComponent(
                reference="J1", value="header", footprint="Fixture:J", exclude_from_bom=True
            ),
        ),
        lines=(),
        findings=(),
    )
    report = PurchasingReport(
        project_id="controller",
        status="NEEDS_PARTS",
        plan=plan,
        source_hashes=source,
        input_hashes={"examples/projects/controller/project.json": digest(island / "project.json")},
        netlist_sha256=digest(directory / "netlist.xml"),
        receipt_dir=str(directory),
    )
    path = directory / "report.json"
    write_model(path, report)
    return path, Path(findings.output_directory) / "review.json"


def test_matched_unplaced_excluded_and_duplicate_references(tmp_path: Path) -> None:
    root, island, _ = parity_workspace(tmp_path)
    parts, findings = saved_inputs(root, island)
    report = build_cross_probe(
        root, "controller", parts, findings, Path("build/cross-probe/review")
    )
    r1, r2, u1, c1a, c1b, j1 = report.entries
    assert r1.population == "FITTED"
    assert [(item.x_mm, item.y_mm, item.drawing_file) for item in r1.board] == [
        (100.0, 100.0, "pcb.svg")
    ]
    assert [(item.x_mm, item.y_mm, item.drawing_file) for item in r1.schematic] == [
        (76.2, 76.2, "schematic-1.svg")
    ]
    assert r2.population == "DNP" and not r2.board and not r2.schematic
    assert u1.population == "FITTED" and not u1.board and not u1.schematic
    assert c1a.population == c1b.population == "DUPLICATE"
    assert not c1a.board and not c1b.schematic
    assert j1.population == "EXCLUDED" and not j1.board
    assert report.variant_scope == "NOT_RECORDED"
    output = Path(report.output_directory)
    html = (output / "index.html").read_text(encoding="utf-8")
    assert 'href="#marker-1-pcb-1"' in html
    assert 'id="marker-1-pcb-1" href="#component-1"' in html
    assert 'href="#marker-1-schematic-1"' in html
    assert "Variant identity is not recorded" in html
    assert read_model(output / "cross-probe.json", CrossProbeReport) == report
    assert all(digest(output / name) == sha for name, sha in report.artifacts_sha256.items())


def test_stale_source_or_drawing_is_rejected(tmp_path: Path) -> None:
    root, island, _ = parity_workspace(tmp_path)
    parts, findings = saved_inputs(root, island)
    board = island / "kicad/controller.kicad_pcb"
    board.write_bytes(board.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="current project and source scope"):
        build_cross_probe(root, "controller", parts, findings)
    board.write_bytes(board.read_bytes()[:-1])
    (findings.parent / "pcb.svg").write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="drawing changed"):
        build_cross_probe(root, "controller", parts, findings)


def test_back_side_and_unsupported_frame_keep_coordinates_without_markers(
    tmp_path: Path,
) -> None:
    root, island, _ = parity_workspace(tmp_path)
    board = island / "kicad/controller.kicad_pcb"
    source = board.read_text(encoding="utf-8")
    board.write_text(source.replace('(layer "F.Cu")', '(layer "B.Cu")', 1), encoding="utf-8")
    parts, findings = saved_inputs(root, island)
    saved = read_model(findings, FindingsViewReport)
    drawings = tuple(
        item.model_copy(update={"mapping_supported": False}) for item in saved.drawings
    )
    write_model(findings, saved.model_copy(update={"drawings": drawings}))
    report = build_cross_probe(root, "controller", parts, findings)
    r1 = report.entries[0]
    assert r1.board[0].side == "B.Cu" and r1.board[0].drawing_file is None
    assert r1.schematic[0].drawing_file is None
    assert "source coordinate" in " ".join(r1.issues)


def test_rejects_active_svg_even_if_a_saved_report_claims_its_hash(tmp_path: Path) -> None:
    root, island, _ = parity_workspace(tmp_path)
    parts, findings = saved_inputs(root, island)
    drawing = findings.parent / "pcb.svg"
    drawing.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="200mm" height="150mm" '
        'viewBox="0 0 200 150"><script>alert(1)</script></svg>',
        encoding="utf-8",
    )
    saved = read_model(findings, FindingsViewReport)
    drawings = tuple(
        item.model_copy(update={"sha256": digest(drawing)}) if item.file == "pcb.svg" else item
        for item in saved.drawings
    )
    artifact_hashes = {**saved.artifacts_sha256, "pcb.svg": digest(drawing)}
    write_model(
        findings,
        saved.model_copy(update={"drawings": drawings, "artifacts_sha256": artifact_hashes}),
    )
    with pytest.raises(ValueError, match="active content"):
        build_cross_probe(root, "controller", parts, findings)


def test_board_parser_retains_duplicate_placements_without_a_unique_marker() -> None:
    source = (
        Path(__file__).parents[1]
        / "kicad_tooling/hwrepo/fixtures/pcb-decoupling-placement.kicad_pcb"
    )
    text = source.read_bytes()
    anchors = board_footprint_anchors(text)
    assert [(item.x_mm, item.y_mm) for item in anchors["c1"]] == [(11.0, 10.0)]
    duplicate = text.replace(b'(property "Reference" "C2")', b'(property "Reference" "C1")')
    assert len(board_footprint_anchors(duplicate)["c1"]) == 2


def test_hierarchy_and_multiunit_symbols_retain_exact_instances() -> None:
    fixtures = Path(__file__).parent / "fixtures/cross_probe"
    root = "projects/demo/kicad/root.kicad_sch"
    child = "projects/demo/kicad/child.kicad_sch"
    anchors, issues = schematic_symbol_anchors(
        {
            root: (fixtures / "root.kicad_sch").read_bytes(),
            child: (fixtures / "child.kicad_sch").read_bytes(),
        },
        root_path=root,
        project_directory="projects/demo/kicad",
        project_name="demo",
    )
    assert not issues
    assert [(item.x_mm, item.y_mm) for item in anchors["u1"]] == [(10.0, 20.0), (30.0, 20.0)]
    assert anchors["r1"][0].sheet_path == ("Power A",)
    assert anchors["r2"][0].sheet_path == ("Power B",)
    assert anchors["r1"][0].source_path == anchors["r2"][0].source_path == child
    assert anchors["r1"][0].sheet_instance_path != anchors["r2"][0].sheet_instance_path


def test_reused_child_symbols_link_only_to_their_exact_bound_drawings() -> None:
    fixtures = Path(__file__).parent / "fixtures/cross_probe"
    root = "projects/demo/kicad/root.kicad_sch"
    child = "projects/demo/kicad/child.kicad_sch"
    anchors, issues = schematic_symbol_anchors(
        {
            root: (fixtures / "root.kicad_sch").read_bytes(),
            child: (fixtures / "child.kicad_sch").read_bytes(),
        },
        root_path=root,
        project_directory="projects/demo/kicad",
        project_name="demo",
    )
    assert not issues
    drawings = tuple(
        ReviewDrawing(
            kind="schematic",
            file=f"sheet-{index}.svg",
            source_artifact=f"schematic/demo-{name}.svg",
            sha256="a" * 64,
            width_mm=200,
            height_mm=150,
            mapping_supported=True,
            sheet_instance_path=anchors[reference][0].sheet_instance_path,
            sheet_path=anchors[reference][0].sheet_path,
            schematic_source=child,
            schematic_source_sha256="b" * 64,
        )
        for index, (reference, name) in enumerate((("r1", "PowerA"), ("r2", "PowerB")), 1)
    )
    bound, binding_issues = schematic_drawing_bindings(
        drawings, {child: "b" * 64}, root_source=root, legacy_root_instance=None
    )
    assert not binding_issues and len(bound) == 2
    entries = tuple(
        _entry(
            PurchasingComponent(reference=reference, value="1k", footprint="Res:R"),
            duplicate=False,
            board_path="projects/demo/kicad/demo.kicad_pcb",
            board_anchors={},
            schematic_anchors=anchors,
            board_drawing=None,
            schematic_drawings=bound,
        )
        for reference in ("R1", "R2")
    )
    assert entries[0].schematic[0].drawing_file == "sheet-1.svg"
    assert entries[1].schematic[0].drawing_file == "sheet-2.svg"
    report = CrossProbeReport(
        project_id="demo",
        parts_report="build/parts/report.json",
        parts_report_sha256="c" * 64,
        findings_view="build/findings/review.json",
        findings_view_sha256="d" * 64,
        source_hashes={child: "b" * 64},
        entries=entries,
        drawings=drawings,
        output_directory="build/cross-probe",
    )
    html = render_cross_probe(report)
    first = html.split("sheet /Power A", 1)[1].split("</section>", 1)[0]
    second = html.split("sheet /Power B", 1)[1].split("</section>", 1)[0]
    assert 'id="marker-1-schematic-1"' in first
    assert 'id="marker-2-schematic-1"' not in first
    assert 'id="marker-2-schematic-1"' in second
    assert 'id="marker-1-schematic-1"' not in second

    stale, stale_issues = schematic_drawing_bindings(
        drawings, {child: "e" * 64}, root_source=root, legacy_root_instance=None
    )
    assert not stale and len(stale_issues) == 2
    duplicate, duplicate_issues = schematic_drawing_bindings(
        (drawings[0], drawings[0]),
        {child: "b" * 64},
        root_source=root,
        legacy_root_instance=None,
    )
    assert not duplicate and "Multiple schematic drawings" in duplicate_issues[0]


class _CrossProbeParity(McpParityHarness):
    async def _case_test_cli_mcp_cross_probe_parity(self) -> None:
        parts, findings = saved_inputs(self.root, self.island)
        cli = await self.cli(
            "kicad_tooling.cross_probe",
            CrossProbeReport,
            "--project",
            "controller",
            "--parts-report",
            str(parts),
            "--findings-view",
            str(findings),
            "--output",
            "build/cross-probe/cli",
        )
        arguments = {
            "project_id": "controller",
            "view_id": "mcp",
            "parts_report": parts.relative_to(self.root).as_posix(),
            "findings_view": findings.relative_to(self.root).as_posix(),
        }
        async with Client(create_server(self.root), mode="legacy") as client:
            self.assertTrue((await client.call_tool("export_bom_cross_probe", arguments)).is_error)
        async with Client(create_server(self.root, allow_exports=True), mode="legacy") as client:
            mcp = await self.call(client, "export_bom_cross_probe", CrossProbeReport, arguments)
        self.receipt_equal(cli, mcp, "output_directory")
        self.assertEqual(
            (Path(cli.output_directory) / "index.html").read_bytes(),
            (Path(mcp.output_directory) / "index.html").read_bytes(),
        )


def test_cli_mcp_cross_probe_parity() -> None:
    run_mcp_parity(_CrossProbeParity, "_case_test_cli_mcp_cross_probe_parity")
