"""Create a source-bound, offline review of saved KiCad and lint findings."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Literal
from uuid import uuid4

from ..validate import hashes
from .artifact_access import artifact_file, artifact_path, read_regular_bytes
from .contract_coach import receipt_directory
from .contracts import parse_model_text, read_model, repo_path, write_model
from .design_lint_report_models import DesignLintReport
from .discovery import load_config
from .evidence import digest
from .findings_view_html import render_findings_view
from .findings_view_mapping import design_lint_finding
from .findings_view_models import FindingsViewReport, ReviewDrawing
from .findings_view_native import NativeArtifacts, drawings, native_findings
from .findings_view_sheets import bind_schematic_drawings
from .models import ValidationSummary
from .native_summary_binding import validate_native_summary_binding
from .project_models import ProjectManifest
from .schematic_geometry_source import schematic_root, schematic_scalar, schematic_sheet_references
from .selection import resolve_project


def _artifact(root: Path, requested: Path) -> Path:
    try:
        relative = requested.relative_to(root) if requested.is_absolute() else requested
    except ValueError as exc:
        raise ValueError("Select a generated artifact inside the project checkout") from exc
    return artifact_path(root, relative.as_posix())


def _lint_snapshot(
    root: Path,
    path: Path,
    project_id: str,
    summary_path: Path,
    summary: ValidationSummary,
    manifest_path: Path,
    policy_path: Path,
    source_hashes: dict[str, str],
) -> tuple[DesignLintReport, str]:
    selected = _artifact(root, path)
    if not selected.is_file():
        raise ValueError("Select a saved design-lint JSON report")
    content, _ = read_regular_bytes(selected, maximum=16 * 1024 * 1024)
    report = parse_model_text(content.decode("utf-8"), DesignLintReport)
    if report.project_id != project_id or report.native_summary is None:
        raise ValueError("Design-lint snapshot is not bound to the selected project and summary")
    lint_summary = Path(report.native_summary)
    if not lint_summary.is_absolute():
        lint_summary = root / lint_summary
    if lint_summary.resolve() != summary_path:
        raise ValueError("Design-lint snapshot refers to a different native summary")
    if (report.status != "BLOCKED" or report.findings) and (
        report.source_hashes != source_hashes
        or report.netlist_sha256 is None
        or report.netlist_sha256 != summary.artifacts_sha256.get("netlist.xml")
        or report.project_manifest_sha256 != digest(manifest_path)
        or report.policy_path != policy_path.relative_to(root).as_posix()
        or report.policy_sha256 != digest(policy_path)
    ):
        raise ValueError("Design-lint snapshot does not match current sources, netlist or policy")
    return report, hashlib.sha256(content).hexdigest()


def build_findings_view(
    root: Path,
    project_id: str,
    native_summary: Path,
    output: Path | None = None,
    lint_report: Path | None = None,
) -> FindingsViewReport:
    """Render saved evidence without rerunning KiCad, design lint or project hooks."""
    root = root.resolve()
    project = resolve_project(root, project_id)
    manifest_path = repo_path(root, project.config)
    manifest_before = digest(manifest_path)
    manifest = read_model(manifest_path, ProjectManifest)
    policy_path = repo_path(manifest_path.parent, manifest.checks)
    policy_before = digest(policy_path)
    config = load_config(root, project.config)
    source_hashes = hashes(root, config.source_roots)
    selected = _artifact(root, native_summary)
    if selected.is_dir():
        selected = artifact_file(root, (selected / "summary.json").relative_to(root).as_posix())
    if not selected.is_file() or selected.name != "summary.json":
        raise ValueError("Select a saved native summary.json or its receipt directory")
    summary_bytes, _ = read_regular_bytes(selected, maximum=8 * 1024 * 1024)
    summary_hash = hashlib.sha256(summary_bytes).hexdigest()
    summary = parse_model_text(summary_bytes.decode("utf-8"), ValidationSummary)
    validate_native_summary_binding(summary, config, source_hashes)
    for checks, extension in (
        (("erc", "schematic_svg"), ".kicad_sch"),
        (("drc", "pcb_svg"), ".kicad_pcb"),
    ):
        if any(
            summary.checks.get(name) is not None and summary.checks[name].status != "NOT_RUN"
            for name in checks
        ):
            source = Path(config.project).with_suffix(extension).as_posix()
            if source not in source_hashes:
                raise ValueError(
                    f"Authoritative drawing source is absent from native hashes: {source}"
                )
    native = NativeArtifacts(root, selected.parent, summary)
    output_drawings = drawings(native, config)
    primary = Path(config.project).with_suffix(".kicad_sch").as_posix()
    output_drawings, source_bindings, source_tree_hash, sheet_issues = bind_schematic_drawings(
        root, primary, config.kicad_version, source_hashes, output_drawings
    )
    schematic = tuple(drawing for drawing, _ in output_drawings if drawing.kind == "schematic")
    board = next((drawing for drawing, _ in output_drawings if drawing.kind == "pcb"), None)
    findings, native_issues = native_findings(native, config, board, schematic, source_hashes)
    issues = [*native_issues, *sheet_issues]
    if not schematic:
        issues.append("No validated schematic SVG is available in this native receipt.")
    if board is None:
        issues.append("No validated PCB SVG is available in this native receipt.")
    if len(schematic) > 1 and not source_bindings:
        issues.append(
            "Multiple schematic sheets are displayed; markers need exact sheet-instance binding."
        )
    if any(not item.mapping_supported for item, _ in output_drawings):
        issues.append(
            "At least one SVG has an unsupported coordinate frame; it is displayed without markers."
        )
    if any(item.origin == "ERC" and item.unmapped_reason for item in findings):
        issues.append("Some ERC item positions have no verified schematic marker.")
    lint_status: Literal["NOT_SUPPLIED", "PASS", "REVIEW", "FAIL", "BLOCKED"] = "NOT_SUPPLIED"
    lint_hash: str | None = None
    if lint_report is None:
        issues.append(
            "No saved design-lint snapshot was supplied; design-lint findings are not shown."
        )
    else:
        lint, lint_hash = _lint_snapshot(
            root,
            lint_report,
            project_id,
            selected,
            summary,
            manifest_path,
            policy_path,
            source_hashes,
        )
        lint_status = lint.status
        if lint.status == "BLOCKED":
            issues.extend(lint.issues or ("The supplied design-lint snapshot is blocked.",))
        if lint.status != "BLOCKED" or lint.findings:
            native.read("netlist.xml")
            native.read("netlist.command.json")
            lookup: dict[str, ReviewDrawing] = {}
            exact_bindings = {
                (item.source_path, item.source_sha256, item.sheet_instance_path, item.sheet_path)
                for item in source_bindings
            }
            lint_bindings = {
                (item.source_path, item.source_sha256, item.sheet_instance_path, item.sheet_path)
                for item in lint.schematic_geometry.source_bindings
            }
            if (
                source_tree_hash is not None
                and source_tree_hash == lint.schematic_geometry.source_tree_sha256
                and exact_bindings == lint_bindings
                and lint.schematic_geometry.status in {"COMPLETE", "PARTIAL"}
                and lint.schematic_geometry.kicad_version == config.kicad_version
                and lint.schematic_geometry.netlist_sha256 == lint.netlist_sha256
            ):
                lookup.update(
                    (drawing.sheet_instance_path, drawing)
                    for drawing in schematic
                    if drawing.sheet_instance_path is not None
                )
            elif source_bindings:
                issues.append(
                    "Design-lint sheet bindings differ from the verified source tree; "
                    "hierarchical markers remain unmapped."
                )
            single_root_sheet = (
                config.kicad_version != "10.0.6"
                and len(schematic) == 1
                and Path(schematic[0].source_artifact).name == f"{Path(primary).stem}.svg"
                and len(lint.schematic_geometry.source_bindings) == 1
                and lint.schematic_geometry.status in {"COMPLETE", "PARTIAL"}
                and lint.schematic_geometry.source_path == primary
                and lint.schematic_geometry.source_sha256 == source_hashes.get(primary)
                and lint.schematic_geometry.netlist_sha256 == lint.netlist_sha256
                and lint.schematic_geometry.kicad_version == config.kicad_version
                and lint.schematic_geometry.source_bindings[0].source_path == primary
                and lint.schematic_geometry.source_bindings[0].source_sha256
                == source_hashes.get(primary)
                and lint.schematic_geometry.source_bindings[0].sheet_path == ()
            )
            if single_root_sheet:
                try:
                    content, _ = read_regular_bytes(
                        repo_path(root, primary), maximum=16 * 1024 * 1024
                    )
                    if hashlib.sha256(content).hexdigest() != source_hashes[primary]:
                        raise ValueError("Schematic changed during findings review")
                    text, source_root = schematic_root(content)
                    source_instance = "/" + schematic_scalar(text, source_root, "uuid")
                    single_root_sheet = (
                        not schematic_sheet_references(content)
                        and lint.schematic_geometry.source_bindings[0].sheet_instance_path
                        == source_instance
                    )
                except (OSError, ValueError):
                    single_root_sheet = False
            root_instance = (
                lint.schematic_geometry.source_bindings[0].sheet_instance_path
                if single_root_sheet
                else None
            )
            if root_instance is not None and len(schematic) == 1:
                lookup[root_instance] = schematic[0].model_copy(
                    update={
                        "schematic_source": primary,
                        "schematic_source_sha256": source_hashes[primary],
                        "sheet_instance_path": root_instance,
                    }
                )
            findings += tuple(
                design_lint_finding(item, lookup, source_hashes, config.kicad_version)
                for item in lint.findings
            )
            issues.append(
                "Design-lint is a saved snapshot; independent review-map inputs may need a fresh inspection."
            )
    if not issues:
        issues.append("Markers show reported locations for review, not electrical approval.")

    def verify_inputs() -> None:
        native.verify()
        if digest(selected) != summary_hash or hashes(root, config.source_roots) != source_hashes:
            raise ValueError("Native summary or project source changed during review export")
        if digest(manifest_path) != manifest_before or digest(policy_path) != policy_before:
            raise ValueError("Project manifest or policy changed during review export")
        if load_config(root, project.config) != config:
            raise ValueError("Project configuration changed during review export")
        if lint_report is not None and digest(_artifact(root, lint_report)) != lint_hash:
            raise ValueError("Design-lint snapshot changed during review export")

    verify_inputs()
    target = output or Path("build/findings-view") / f"{project_id}-{uuid4().hex[:12]}"
    directory = receipt_directory(root, project_id, target)
    for drawing, content in output_drawings:
        (directory / drawing.file).write_bytes(content)
    report = FindingsViewReport(
        project_id=project_id,
        native_status=summary.status,
        lint_status=lint_status,
        native_summary=selected.relative_to(root).as_posix(),
        native_summary_sha256=summary_hash,
        lint_report=None
        if lint_report is None
        else _artifact(root, lint_report).relative_to(root).as_posix(),
        lint_report_sha256=lint_hash,
        source_hashes=source_hashes,
        drawings=tuple(item for item, _ in output_drawings),
        findings=findings,
        issues=tuple(issues),
        output_directory=str(directory),
    )
    (directory / "index.html").write_text(render_findings_view(report), encoding="utf-8")
    verify_inputs()
    report = report.model_copy(
        update={
            "artifacts_sha256": {
                path.name: digest(path) for path in sorted(directory.iterdir()) if path.is_file()
            }
        }
    )
    write_model(directory / "review.json", report)
    return report
