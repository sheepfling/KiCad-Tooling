"""Explicit receipt selection, freshness and safe offline links."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.discovery import load_config
from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.findings_view import build_findings_view
from kicad_tooling.hwrepo.models import (
    DesignLintPolicy,
    ElectricalAnalysisReport,
    ElectricalChartCase,
    ElectricalChartsReport,
    ProjectDiscovery,
    ProjectVerificationReport,
    PurchasingReport,
    SourceState,
    ThreeDReport,
    ValidationSummary,
)
from kicad_tooling.hwrepo.review_overview import build_review_overview
from kicad_tooling.hwrepo.review_overview_html import render_review_overview
from kicad_tooling.hwrepo.review_overview_models import (
    OverviewItem,
    OverviewLink,
    ReviewOverviewReport,
)
from kicad_tooling.validate import hashes
from tests.findings_view_support import add_native_review, select_schematic_geometry_toolchain
from tests.mcp_parity_support import parity_native_evidence, parity_workspace
from tests.synthetic_design_lint_project import synthetic_design_lint_project

pytestmark = pytest.mark.template_checkout


@pytest.fixture
def saved_receipts(tmp_path: Path) -> tuple[Path, dict[str, Path]]:
    root, island, _ = parity_workspace(tmp_path)
    select_schematic_geometry_toolchain(island)
    native = parity_native_evidence(root, island)
    add_native_review(root, native)
    findings = build_findings_view(root, "controller", native, Path("build/findings-view/saved"))
    config = load_config(root, "examples/projects/controller/project.json")
    source = hashes(root, config.source_roots)
    board = str(Path(config.project).with_suffix(".kicad_pcb"))
    manifest = island / "project.json"

    parts = root / "build/parts/saved"
    parts.mkdir(parents=True)
    (parts / "index.html").write_text("<h1>parts</h1>", encoding="utf-8")
    (parts / "bom.csv").write_text("reference,quantity\nR1,1\n", encoding="utf-8")
    (parts / "netlist.xml").write_bytes((native.parent / "netlist.xml").read_bytes())
    write_model(
        parts / "report.json",
        PurchasingReport(
            project_id="controller",
            status="NEEDS_PARTS",
            receipt_dir=str(parts),
            source_hashes=source,
            input_hashes={manifest.relative_to(root).as_posix(): digest(manifest)},
            netlist_sha256=digest(parts / "netlist.xml"),
            artifacts=("bom.csv",),
        ),
    )

    three_d = root / "build/3d/saved"
    three_d.mkdir(parents=True)
    (three_d / "index.html").write_text("<h1>3D</h1>", encoding="utf-8")
    (three_d / "board.glb").write_bytes(b"glTF\x02\0\0\0synthetic")
    write_model(
        three_d / "visualization.json",
        ThreeDReport(
            project_id="controller",
            mode="generate",
            status="PASS",
            run_directory=str(three_d),
            toolchain_id=config.toolchain_id,
            kicad_version=config.kicad_version,
            board=board,
            source_sha256={board: source[board]},
            artifacts_sha256={name: digest(three_d / name) for name in ("index.html", "board.glb")},
        ),
    )

    analysis = root / "build/electrical/saved"
    analysis.mkdir(parents=True)
    (analysis / "requirements.json").write_text("{}", encoding="utf-8")
    write_model(
        analysis / "electrical.json",
        ElectricalAnalysisReport(
            project_id="controller",
            status="PASS",
            run_directory=str(analysis),
            source=SourceState(files_sha256={board: source[board]}),
            input_sha256={manifest.relative_to(root).as_posix(): digest(manifest)},
            artifacts_sha256={"requirements.json": digest(analysis / "requirements.json")},
            checks=(),
        ),
    )
    charts = root / "build/electrical-charts/saved"
    charts.mkdir(parents=True)
    (charts / "transient.svg").write_text("<svg/>", encoding="utf-8")
    (charts / "transient.csv").write_text("time_s,v\n0,1\n", encoding="utf-8")
    write_model(
        charts / "charts.json",
        ElectricalChartsReport(
            project_id="controller",
            status="PASS",
            source_analysis_status="PASS",
            source_receipt=str(analysis),
            source_report_sha256=digest(analysis / "electrical.json"),
            run_directory=str(charts),
            cases=(
                ElectricalChartCase(
                    id="transient",
                    status="PASS",
                    detail="Synthetic retained chart",
                    svg="transient.svg",
                    csv="transient.csv",
                ),
            ),
            artifacts_sha256={
                name: digest(charts / name) for name in ("transient.svg", "transient.csv")
            },
        ),
    )

    verification = root / "build/verify/saved"
    verification.mkdir(parents=True)
    write_model(
        verification / "verification.json",
        ProjectVerificationReport(
            project_id="controller",
            depth="portable",
            status="FAIL",
            run_directory=str(verification),
        ),
    )
    return root, {
        "native": native,
        "findings": Path(findings.output_directory) / "review.json",
        "parts": parts / "report.json",
        "three_d": three_d / "visualization.json",
        "simulation": charts / "charts.json",
        "verification": verification / "verification.json",
    }


def _all(root: Path, paths: dict[str, Path], output: str) -> ReviewOverviewReport:
    return build_review_overview(
        root,
        "controller",
        native_summary=paths["native"],
        findings_view=paths["findings"],
        parts_report=paths["parts"],
        three_d_report=paths["three_d"],
        charts_report=paths["simulation"],
        verification_report=paths["verification"],
        output=Path(output),
    )


def test_overview_keeps_original_status_and_freshness_separate(
    saved_receipts: tuple[Path, dict[str, Path]],
) -> None:
    root, paths = saved_receipts
    report = _all(root, paths, "build/review-overview/all")
    items = {item.kind: item for item in report.items}
    assert {key: item.freshness for key, item in items.items()} == {
        "native": "CURRENT",
        "findings": "CURRENT",
        "parts": "UNKNOWN",
        "three_d": "CURRENT",
        "simulation": "CURRENT",
        "verification": "UNKNOWN",
    }
    assert items["native"].status == "FAIL"
    assert items["verification"].status == "FAIL"
    assert {link.label.split(":")[0] for link in items["native"].links} >= {
        "Schematic",
        "PCB",
    }
    assert items["parts"].links[-1].receipt_bound is False
    assert items["findings"].links[-1].label == "Open findings explorer"
    assert (
        read_model(Path(report.output_directory) / "overview.json", ReviewOverviewReport) == report
    )
    html = (Path(report.output_directory) / "index.html").read_text(encoding="utf-8")
    assert "Current means recorded bytes matched" in html
    assert "snapshot hash only" in html
    assert "not an electrical" in html
    assert "https://" not in html
    assert not report.build_authorized


def test_mixed_revisions_changed_artifacts_and_missing_selection(
    saved_receipts: tuple[Path, dict[str, Path]],
) -> None:
    root, paths = saved_receipts
    source = root / "examples/projects/controller/kicad/controller.kicad_pcb"
    source.write_text(source.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    (paths["three_d"].parent / "board.glb").write_bytes(b"changed")
    (paths["simulation"].parent / "transient.svg").write_text("changed", encoding="utf-8")
    missing = root / "build/findings-view/absent/review.json"
    report = build_review_overview(
        root,
        "controller",
        native_summary=paths["native"],
        findings_view=missing,
        parts_report=paths["parts"],
        three_d_report=paths["three_d"],
        charts_report=paths["simulation"],
        output=Path("build/review-overview/mixed"),
    )
    items = {item.kind: item for item in report.items}
    assert items["native"].freshness == "STALE"
    assert items["findings"].freshness == "MISSING"
    assert items["parts"].freshness == "STALE"
    assert items["three_d"].freshness == "STALE"
    assert items["simulation"].freshness == "STALE"
    assert items["verification"].freshness == "NOT_SELECTED"
    assert not any(link.path.endswith("board.glb") for link in items["three_d"].links)


def test_changed_project_input_keeps_unaffected_receipts_distinct(
    saved_receipts: tuple[Path, dict[str, Path]],
) -> None:
    root, paths = saved_receipts
    manifest = root / "examples/projects/controller/project.json"
    manifest.write_text(manifest.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    report = build_review_overview(
        root,
        "controller",
        native_summary=paths["native"],
        parts_report=paths["parts"],
        charts_report=paths["simulation"],
        output=Path("build/review-overview/input-change"),
    )
    items = {item.kind: item for item in report.items}
    assert items["native"].freshness == "CURRENT"
    assert items["parts"].freshness == "STALE"
    assert items["simulation"].freshness == "STALE"
    assert any("project.json" in issue for issue in items["parts"].issues)


def test_invalid_or_other_project_receipts_are_unavailable_without_searching(
    saved_receipts: tuple[Path, dict[str, Path]],
) -> None:
    root, paths = saved_receipts
    wrong = read_model(paths["parts"], PurchasingReport).model_copy(update={"project_id": "other"})
    write_model(paths["parts"], wrong)
    paths["verification"].write_text("{invalid", encoding="utf-8")
    report = build_review_overview(
        root,
        "controller",
        parts_report=paths["parts"],
        verification_report=paths["verification"],
        output=Path("build/review-overview/invalid"),
    )
    items = {item.kind: item for item in report.items}
    assert items["parts"].freshness == "UNAVAILABLE"
    assert items["verification"].freshness == "UNAVAILABLE"
    assert items["native"].freshness == "NOT_SELECTED"
    wrong_type = build_review_overview(
        root,
        "controller",
        parts_report=paths["native"],
        output=Path("build/review-overview/wrong-type"),
    )
    assert wrong_type.items[2].freshness == "UNAVAILABLE"
    with pytest.raises(ValueError, match="inside this project checkout"):
        build_review_overview(
            root, "controller", native_summary=Path("/private/tmp/foreign/summary.json")
        )


def test_existing_receipt_change_is_detected_even_when_source_is_stable(
    saved_receipts: tuple[Path, dict[str, Path]],
) -> None:
    root, paths = saved_receipts
    (paths["native"].parent / "pcb.svg").write_text("changed", encoding="utf-8")
    report = build_review_overview(
        root,
        "controller",
        native_summary=paths["native"],
        findings_view=paths["findings"],
        output=Path("build/review-overview/changed"),
    )
    native = report.items[0]
    assert native.freshness == "STALE"
    assert any("pcb.svg" in issue for issue in native.issues)
    assert not any(link.path.endswith("pcb.svg") for link in native.links)
    assert report.items[1].freshness == "STALE"


def test_configured_nested_layout_uses_registered_project_paths(tmp_path: Path) -> None:
    root, native = synthetic_design_lint_project(tmp_path, DesignLintPolicy())
    discovery = read_model(root / "catalog/projects.json", ProjectDiscovery)
    (root / "policy").mkdir()
    write_model(
        root / "policy/discovery.json",
        discovery.model_copy(update={"project_roots": ("hardware",), "project_depth": 2}),
    )
    (root / "catalog/projects.json").unlink()
    destination = root / "hardware/team/controller"
    destination.parent.mkdir(parents=True)
    shutil.move(root / "projects/controller", destination)
    (root / "kicad-tooling.toml").write_text(
        '[layout]\ndiscovery = "policy/discovery.json"\nnew_project_root = "hardware/team"\n',
        encoding="utf-8",
    )
    config = load_config(root, "hardware/team/controller/project.json")
    current = hashes(root, config.source_roots)
    original = read_model(native, ValidationSummary)
    checks = {
        **original.checks,
        "source_scope": original.checks["source_scope"].model_copy(
            update={"source_hashes": current}
        ),
        "source_unchanged": original.checks["source_unchanged"].model_copy(
            update={"source_hashes": current}
        ),
    }
    write_model(native, original.model_copy(update={"checks": checks}))
    report = build_review_overview(
        root,
        "controller",
        native_summary=native,
        output=Path("build/review-overview/nested"),
    )
    assert report.project_manifest == "hardware/team/controller/project.json"
    assert report.items[0].freshness == "CURRENT"
    assert report.current_source_hashes == current


def test_overview_escapes_untrusted_receipt_text_and_encodes_local_paths(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repository"
    root.mkdir()
    report = ReviewOverviewReport(
        project_id="demo",
        project_manifest="projects/demo/project.json",
        project_manifest_sha256="0" * 64,
        toolchain_id="kicad",
        kicad_version="10.0.5",
        current_source_hashes={},
        output_directory=str(root / "build/review-overview/demo"),
        items=(
            OverviewItem(
                kind="parts",
                status="<script>bad()</script>",
                freshness="UNKNOWN",
                issues=("<img src=x onerror=bad()>",),
                links=(
                    OverviewLink(
                        label="A & B",
                        path="build/parts/A & B.html",
                        sha256="1" * 64,
                        receipt_bound=False,
                    ),
                ),
            ),
        ),
    )
    html = render_review_overview(root, report)
    assert "&lt;script&gt;bad()&lt;/script&gt;" in html
    assert "&lt;img src=x onerror=bad()&gt;" in html
    assert "A &amp; B" in html
    assert "A%20%26%20B.html" in html
    assert "<script>bad()" not in html
