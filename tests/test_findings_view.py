"""Source binding, placement and safe rendering for the findings explorer."""

from __future__ import annotations

import hashlib
from pathlib import Path
from unittest.mock import patch

import pytest

from kicad_tooling.hwrepo.command_evidence_models import CommandEvidence
from kicad_tooling.hwrepo.contracts import read_model, write_model
from kicad_tooling.hwrepo.design_lint import inspect_summary
from kicad_tooling.hwrepo.design_lint_finding_models import (
    DesignLintFinding,
    DesignLintRuleOverride,
)
from kicad_tooling.hwrepo.design_lint_report_models import DesignLintReport
from kicad_tooling.hwrepo.findings_view import build_findings_view
from kicad_tooling.hwrepo.findings_view_html import render_findings_view
from kicad_tooling.hwrepo.findings_view_mapping import design_lint_finding, drc_finding
from kicad_tooling.hwrepo.findings_view_models import FindingsViewReport
from kicad_tooling.hwrepo.findings_view_svg import prepare_drawing
from kicad_tooling.hwrepo.models import ProjectTestContract, ValidationSummary
from kicad_tooling.hwrepo.native_drc_findings import NativeDrcFinding, NativeDrcItem
from kicad_tooling.hwrepo.project_models import ProjectManifest, ToolchainsCatalog
from kicad_tooling.hwrepo.schematic_geometry_source import source_tree_sha256
from kicad_tooling.hwrepo.schematic_source_tree import (
    schematic_instance_bindings,
    verified_schematic_sources,
)
from tests.findings_view_support import (
    add_lint_snapshot,
    add_native_review,
    select_schematic_geometry_toolchain,
)
from tests.mcp_parity_support import parity_native_evidence, parity_workspace

pytestmark = [pytest.mark.design_lint, pytest.mark.template_checkout]


@pytest.fixture
def evidence(tmp_path: Path) -> tuple[Path, Path]:
    root, island, _ = parity_workspace(tmp_path)
    select_schematic_geometry_toolchain(island)
    native = parity_native_evidence(root, island)
    add_native_review(root, native)
    return root, native


def test_source_bound_view_maps_supported_board_and_schematic_findings(
    evidence: tuple[Path, Path],
) -> None:
    root, native = evidence
    lint = add_lint_snapshot(root, native)
    report = build_findings_view(root, "controller", native, Path("build/findings-view/test"), lint)
    output = Path(report.output_directory)
    assert read_model(output / "review.json", FindingsViewReport) == report
    assert report.native_status == "FAIL"
    assert report.lint_status == "REVIEW"
    assert [item.origin for item in report.findings] == ["ERC", "DRC", "DRC", "DESIGN_LINT"]
    erc, drc, parity, lint_finding = report.findings
    assert not erc.markers and "exact KiCad 10.0.6 UUID sheet" in (erc.unmapped_reason or "")
    assert [(point.x_mm, point.y_mm) for point in drc.markers] == [(100.0, 100.0), (100.0, 110.0)]
    assert not parity.markers and parity.unmapped_reason
    assert [(point.x_mm, point.y_mm) for point in lint_finding.markers] == [(50.0, 40.0)]
    assert lint_finding.fingerprint == "1" * 64
    assert lint_finding.evidence["crossing_mm"] == ("50.000000,40.000000",)
    assert "0.762, 0.7112 (raw ERC position)" in erc.evidence["native_items"][0]
    html = (output / "index.html").read_text(encoding="utf-8")
    assert 'cx="100.000000" cy="110.000000"' in html
    assert 'cx="50.000000" cy="40.000000"' in html
    assert 'cx="0.762000"' not in html
    assert "Unmapped:" in html
    assert "Unmapped or partially mapped findings" in html
    assert "Finding evidence" in html
    assert set(report.artifacts_sha256) == {"index.html", "pcb.svg", "schematic-1.svg"}
    assert (
        report.artifacts_sha256["pcb.svg"]
        == hashlib.sha256((output / "pcb.svg").read_bytes()).hexdigest()
    )
    assert not report.build_authorized


def test_rejects_changed_source_and_artifacts(evidence: tuple[Path, Path]) -> None:
    root, native = evidence
    (native.parent / "pcb.svg").write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="changed or is missing"):
        build_findings_view(root, "controller", native)
    # The source check fails independently of the retained artifact.
    source = root / "examples/projects/controller/kicad/controller.kicad_pcb"
    source.write_text(source.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="hashes do not match"):
        build_findings_view(root, "controller", native)


def test_unverified_sheets_and_parity_remain_unmapped(evidence: tuple[Path, Path]) -> None:
    root, native = evidence
    lint = add_lint_snapshot(root, native, sheet_path="/reused-sheet")
    report = build_findings_view(root, "controller", native, lint_report=lint)
    finding = next(item for item in report.findings if item.origin == "DESIGN_LINT")
    assert not finding.markers and finding.unmapped_reason


def test_without_lint_snapshot_explains_missing_coverage(evidence: tuple[Path, Path]) -> None:
    root, native = evidence
    report = build_findings_view(root, "controller", native)
    assert report.lint_status == "NOT_SUPPLIED"
    assert any("not shown" in issue for issue in report.issues)


def test_svg_rejects_active_and_external_content() -> None:
    svg = (
        b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><script>bad()</script></svg>'
    )
    with pytest.raises(ValueError, match="active content"):
        prepare_drawing(svg, "pcb")
    external = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><image href="https://example.test/x"/></svg>'
    with pytest.raises(ValueError, match="external reference"):
        prepare_drawing(external, "pcb")
    entity = b'<!DOCTYPE svg [<!ENTITY x "bad">]><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"/>'
    with pytest.raises(ValueError, match="entity declarations"):
        prepare_drawing(entity, "pcb")
    with pytest.raises(ValueError, match="UTF-8"):
        prepare_drawing(entity.decode().encode("utf-16"), "pcb")


def test_unbound_or_unexpected_native_files_are_rejected(evidence: tuple[Path, Path]) -> None:
    root, native = evidence
    summary = read_model(native, ValidationSummary)
    artifacts = dict(summary.artifacts_sha256)
    artifacts.pop("drc.json")
    write_model(native, summary.model_copy(update={"artifacts_sha256": artifacts}))
    with pytest.raises(ValueError, match="does not bind drc.json"):
        build_findings_view(root, "controller", native)


def test_svg_command_with_different_origin_is_rejected(evidence: tuple[Path, Path]) -> None:
    root, native = evidence
    command_path = native.parent / "pcb_svg.command.json"
    command = read_model(command_path, CommandEvidence)
    write_model(
        command_path,
        command.model_copy(update={"argv": (*command.argv[:-1], "/other/controller.kicad_pcb")}),
    )
    summary = read_model(native, ValidationSummary)
    write_model(
        native,
        summary.model_copy(
            update={
                "artifacts_sha256": {
                    **summary.artifacts_sha256,
                    command_path.name: hashlib.sha256(command_path.read_bytes()).hexdigest(),
                }
            }
        ),
    )
    with pytest.raises(ValueError, match="command does not match"):
        build_findings_view(root, "controller", native)


def test_mixed_items_report_partial_mapping(evidence: tuple[Path, Path]) -> None:
    import json

    root, native = evidence
    drc_path = native.parent / "drc.json"
    data = json.loads(drc_path.read_text(encoding="utf-8"))
    data["unconnected_items"][0]["items"][1]["pos"] = {"x": 9999.0, "y": 100.0}
    drc_path.write_text(json.dumps(data), encoding="utf-8")
    summary = read_model(native, ValidationSummary)
    write_model(
        native,
        summary.model_copy(
            update={
                "artifacts_sha256": {
                    **summary.artifacts_sha256,
                    "drc.json": hashlib.sha256(drc_path.read_bytes()).hexdigest(),
                }
            }
        ),
    )
    result = build_findings_view(root, "controller", native)
    finding = next(item for item in result.findings if item.rule == "unconnected_items")
    assert len(finding.markers) == 1
    assert finding.unmapped_reason
    html = (Path(result.output_directory) / "index.html").read_text(encoding="utf-8")
    assert "1 partially mapped" in html


def test_saved_lint_snapshot_rejects_changed_policy(evidence: tuple[Path, Path]) -> None:
    root, native = evidence
    lint = add_lint_snapshot(root, native)
    policy = root / "examples/projects/controller/tests/contract.json"
    policy.write_text(policy.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="does not match current sources, netlist or policy"):
        build_findings_view(root, "controller", native, lint_report=lint)


def test_drawing_that_changes_during_export_never_gets_a_completed_receipt(
    evidence: tuple[Path, Path],
) -> None:
    root, native = evidence

    def mutate(report: FindingsViewReport) -> str:
        (native.parent / "pcb.svg").write_text("changed during render", encoding="utf-8")
        return render_findings_view(report)

    output = root / "build/findings-view/interrupted"
    with (
        patch("kicad_tooling.hwrepo.findings_view.render_findings_view", side_effect=mutate),
        pytest.raises(ValueError, match="changed or is missing"),
    ):
        build_findings_view(root, "controller", native, output)
    assert not (output / "review.json").exists()


def test_nonstandard_svg_coordinate_frame_is_not_used_for_markers(
    evidence: tuple[Path, Path],
) -> None:
    root, native = evidence
    svg = native.parent / "pcb.svg"
    svg.write_text(
        svg.read_text(encoding="utf-8").replace('viewBox="0 0 200 150"', 'viewBox="10 20 200 150"'),
        encoding="utf-8",
    )
    summary = read_model(native, ValidationSummary)
    write_model(
        native,
        summary.model_copy(
            update={
                "artifacts_sha256": {
                    **summary.artifacts_sha256,
                    "pcb.svg": hashlib.sha256(svg.read_bytes()).hexdigest(),
                }
            }
        ),
    )
    report = build_findings_view(root, "controller", native)
    board = next(drawing for drawing in report.drawings if drawing.kind == "pcb")
    assert not board.mapping_supported
    assert not any(finding.markers for finding in report.findings)
    assert any("unsupported coordinate frame" in issue for issue in report.issues)


def test_unverified_coordinate_conventions_do_not_create_markers(
    evidence: tuple[Path, Path],
) -> None:
    root, native = evidence
    report = build_findings_view(root, "controller", native)
    board = next(item for item in report.drawings if item.kind == "pcb")
    item = NativeDrcFinding(
        category="violations",
        rule="clearance",
        severity="error",
        description="Clearance",
        excluded=False,
        items=(NativeDrcItem(description="pad", x_mm=10.0, y_mm=10.0),),
    )
    assert not drc_finding(item, board, "10.1.0", "mm").markers
    assert not drc_finding(item, board, "10.0.5", "in").markers
    schematic = next(d for d in report.drawings if d.kind == "schematic")
    source = "examples/projects/controller/kicad/controller.kicad_sch"
    finding = DesignLintFinding(
        rule_id="schematic.free_text_over_wire",
        fingerprint="1" * 64,
        subject="Wire near text",
        message="Review the drawing.",
        mode="review",
        disposition="OPEN",
        evidence={
            "schematic": (source,),
            "schematic_sha256": (report.source_hashes[source],),
            "sheet_instance_path": ("/",),
            "kicad_version": ("10.0.5",),
            "overlap_segment_mm": ("10,10,180,10",),
        },
    )
    # This field contains a wire segment, not an exact collision location.
    assert not design_lint_finding(
        finding,
        {"/": schematic.model_copy(update={"schematic_source": source})},
        report.source_hashes,
        "10.0.5",
    ).markers


def test_real_lint_geometry_snapshot_maps_its_exact_root_instance(tmp_path: Path) -> None:
    root, island, _ = parity_workspace(tmp_path)
    select_schematic_geometry_toolchain(island)
    fixture = (
        Path(__file__).parent
        / "fixtures/design_lint/t-junction/near-miss-crossing-and-t-junction.kicad_sch"
    )
    (island / "kicad/controller.kicad_sch").write_text(
        fixture.read_text(encoding="utf-8").replace("near-miss-pin-line", "controller"),
        encoding="utf-8",
    )
    policy_path = island / "tests/contract.json"
    contract = read_model(policy_path, ProjectTestContract)
    assert contract.design_lint is not None
    policy = contract.design_lint.model_copy(
        update={
            "rules": (
                *contract.design_lint.rules,
                DesignLintRuleOverride(
                    rule_id="schematic.unmarked_wire_crossing",
                    mode="review",
                    reason="Synthetic crossing review",
                ),
            )
        }
    )
    write_model(policy_path, contract.model_copy(update={"design_lint": policy}))
    native = parity_native_evidence(root, island)
    add_native_review(root, native)
    lint = inspect_summary(root, "controller", native)
    crossing = next(f for f in lint.findings if f.rule_id == "schematic.unmarked_wire_crossing")
    assert lint.schematic_geometry.status in {"COMPLETE", "PARTIAL"}
    assert crossing.evidence["sheet_instance_path"][0].startswith("/")
    snapshot = native.parent / "captured-lint.json"
    write_model(snapshot, lint)
    view = build_findings_view(root, "controller", native, lint_report=snapshot)
    mapped = next(f for f in view.findings if f.rule == "schematic.unmarked_wire_crossing")
    assert [(point.x_mm, point.y_mm) for point in mapped.markers] == [(127.0, 127.0)]


def test_reused_child_sheet_findings_map_to_distinct_drawings(tmp_path: Path) -> None:
    root, island, _ = parity_workspace(tmp_path)
    catalog_path = root / "catalog/toolchains.json"
    catalog = read_model(catalog_path, ToolchainsCatalog)
    write_model(
        catalog_path,
        catalog.model_copy(
            update={
                "toolchains": (
                    *catalog.toolchains,
                    catalog.toolchains[-1].model_copy(
                        update={
                            "id": "kicad-10.0.6",
                            "kicad_version": "10.0.6",
                            "image": "ghcr.io/kicad/kicad:10.0.6@sha256:" + "a" * 64,
                        }
                    ),
                )
            }
        ),
    )
    manifest_path = island / "project.json"
    manifest = read_model(manifest_path, ProjectManifest)
    write_model(manifest_path, manifest.model_copy(update={"toolchain_id": "kicad-10.0.6"}))
    fixture = Path(__file__).parent / "fixtures/design_lint/repeated-sheet"
    primary = island / "kicad/controller.kicad_sch"
    child = island / "kicad/repeated-channel.kicad_sch"
    primary.write_bytes((fixture / "repeated-sheet-root.kicad_sch").read_bytes())
    child.write_bytes((fixture / "repeated-channel.kicad_sch").read_bytes())
    native = parity_native_evidence(root, island)
    add_native_review(root, native)
    summary = read_model(native, ValidationSummary)
    names = (
        ("controller.svg", "/", "controller.kicad_sch"),
        ("controller-InstanceA.svg", "/InstanceA/", "repeated-channel.kicad_sch"),
        ("controller-InstanceB.svg", "/InstanceB/", "repeated-channel.kicad_sch"),
    )
    artifacts = dict(summary.artifacts_sha256)
    for name, sheet, source_name in names:
        path = native.parent / "schematic" / name
        raw = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="200mm" height="150mm" '
            'viewBox="0 0 200 150"><desc>Image generated by Eeschema-SVG</desc>'
            f'<text text-anchor="start" opacity="0" stroke-opacity="0">File: {source_name}</text>'
            f'<text text-anchor="start" opacity="0" stroke-opacity="0">Sheet: {sheet}</text>'
            '<path d="M 20 40 L 80 40" stroke="black"/></svg>'
        )
        path.write_bytes(prepare_drawing(raw.encode("utf-8"), "schematic").content)
        artifacts[f"schematic/{name}"] = hashlib.sha256(path.read_bytes()).hexdigest()
    check = summary.checks["schematic_svg"]
    write_model(
        native,
        summary.model_copy(
            update={
                "checks": {
                    **summary.checks,
                    "schematic_svg": check.model_copy(
                        update={
                            "files": tuple(f"schematic/{name}" for name, _, _ in names),
                        }
                    ),
                },
                "artifacts_sha256": artifacts,
            }
        ),
    )
    lint_path = add_lint_snapshot(root, native)
    lint = read_model(lint_path, DesignLintReport)
    source_hashes = lint.source_hashes
    primary_name = primary.relative_to(root).as_posix()
    child_name = child.relative_to(root).as_posix()
    source_files = verified_schematic_sources(
        root, primary_name, primary.parent.relative_to(root).as_posix(), source_hashes
    )
    bindings = schematic_instance_bindings(
        source_files, primary_name, primary.parent.relative_to(root).as_posix()
    )
    child_bindings = [item for item in bindings if item.source_path == child_name]
    assert len(child_bindings) == 2
    findings = tuple(
        DesignLintFinding(
            rule_id="schematic.unmarked_wire_crossing",
            fingerprint=str(index) * 64,
            subject=f"Crossing in {binding.sheet_path[0]}",
            message="Review crossing.",
            mode="review",
            disposition="OPEN",
            evidence={
                "schematic": (child_name,),
                "schematic_sha256": (source_hashes[child_name],),
                "sheet_instance_path": (binding.sheet_instance_path,),
                "crossing_mm": ("50,40",),
                "kicad_version": ("10.0.6",),
            },
        )
        for index, binding in enumerate(child_bindings, 1)
    )
    write_model(
        lint_path,
        lint.model_copy(
            update={
                "findings": findings,
                "schematic_geometry": lint.schematic_geometry.model_copy(
                    update={
                        "source_tree_sha256": source_tree_sha256(
                            {name: source_hashes[name] for name in source_files}
                        ),
                        "source_bindings": bindings,
                        "finding_count": 2,
                    }
                ),
            }
        ),
    )
    report = build_findings_view(root, "controller", native, lint_report=lint_path)
    mapped = {item.title: item for item in report.findings if item.origin == "DESIGN_LINT"}
    assert len(mapped) == 2
    drawing_by_sheet = {
        item.sheet_path: item for item in report.drawings if item.kind == "schematic"
    }
    for binding in child_bindings:
        finding = mapped[f"Crossing in {binding.sheet_path[0]}"]
        assert len(finding.markers) == 1
        marker = finding.markers[0]
        assert marker.sheet_instance_path == binding.sheet_instance_path
        assert marker.drawing_file == drawing_by_sheet[binding.sheet_path].file
    assert (
        mapped["Crossing in InstanceA"].markers[0].drawing_file
        != mapped["Crossing in InstanceB"].markers[0].drawing_file
    )
    html = (Path(report.output_directory) / "index.html").read_text(encoding="utf-8")
    for finding in mapped.values():
        marker_id = f"marker-{report.findings.index(finding) + 1}-1"
        drawing_file = finding.markers[0].drawing_file
        assert drawing_file is not None
        section = html.split(f'id="drawing-{drawing_file}"', 1)[1].split("</section>", 1)[0]
        assert f'id="{marker_id}"' in section
        for other in drawing_by_sheet.values():
            if other.file != drawing_file:
                other_section = html.split(f'id="drawing-{other.file}"', 1)[1].split(
                    "</section>", 1
                )[0]
                assert f'id="{marker_id}"' not in other_section

    first_svg = native.parent / "schematic/controller-InstanceA.svg"
    second_svg = native.parent / "schematic/controller-InstanceB.svg"
    second_svg.write_bytes(first_svg.read_bytes())
    changed = read_model(native, ValidationSummary)
    write_model(
        native,
        changed.model_copy(
            update={
                "artifacts_sha256": {
                    **changed.artifacts_sha256,
                    "schematic/controller-InstanceB.svg": hashlib.sha256(
                        second_svg.read_bytes()
                    ).hexdigest(),
                }
            }
        ),
    )
    ambiguous = build_findings_view(
        root, "controller", native, Path("build/findings-view/ambiguous"), lint_path
    )
    ambiguous_findings = [item for item in ambiguous.findings if item.origin == "DESIGN_LINT"]
    assert len(ambiguous_findings) == 2
    assert all(not item.markers and item.unmapped_reason for item in ambiguous_findings)
    assert any("no unique verified sheet instance" in issue for issue in ambiguous.issues)
