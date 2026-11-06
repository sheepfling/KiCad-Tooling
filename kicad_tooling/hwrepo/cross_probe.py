"""Join explicit parts and drawing receipts into source-matched navigation."""

from __future__ import annotations

import hashlib
from pathlib import Path
from uuid import uuid4

from .artifact_access import read_regular_bytes
from .contract_coach import receipt_directory
from .contracts import repo_path, write_model
from .cross_probe_admission import admit_cross_probe_inputs, verify_cross_probe_inputs
from .cross_probe_board import resolve_cross_probe_board_markers
from .cross_probe_html import render_cross_probe
from .cross_probe_models import CrossProbeReport
from .cross_probe_operation_models import CrossProbeBuildRequest
from .cross_probe_reconciliation import (
    CrossProbeLocationEvidence,
    CrossProbePopulationInput,
    reconcile_cross_probe_population,
)
from .cross_probe_schematic import (
    schematic_drawing_bindings,
    schematic_symbol_anchors,
)
from .evidence import digest
from .purchasing import read_components
from .schematic_geometry_models import SchematicSourceFile, VerifiedSchematicSourceTree
from .schematic_geometry_source import schematic_root, schematic_scalar, schematic_sheet_references


def _source_bytes(root: Path, name: str, sha256: str) -> bytes:
    content, _ = read_regular_bytes(repo_path(root, name), maximum=32 * 1024 * 1024)
    if hashlib.sha256(content).hexdigest() != sha256:
        raise ValueError(f"Project source changed while reading: {name}")
    return content


def build_cross_probe_request(root: Path, request: CrossProbeBuildRequest) -> CrossProbeReport:
    """Export reversible links only for current, explicit, matching evidence."""
    root = root.resolve()
    admitted = admit_cross_probe_inputs(root, request)
    config = admitted.config
    current = admitted.source_hashes
    parts = admitted.parts
    parts_path = admitted.parts_path
    parts_sha = admitted.parts_sha256
    findings = admitted.findings
    findings_path = admitted.findings_path
    findings_sha = admitted.findings_sha256
    variant = admitted.variant
    drawing_bytes = admitted.drawing_bytes

    board_path = Path(config.project).with_suffix(".kicad_pcb").as_posix()
    board_source = (
        _source_bytes(root, board_path, current[board_path]) if board_path in current else None
    )
    board_marker_resolution = resolve_cross_probe_board_markers(
        board_path=board_path,
        board_source_sha256=current.get(board_path),
        board_source=board_source,
        findings_view_path=findings_path.relative_to(root).as_posix(),
        findings_view_sha256=findings_sha,
        drawings=findings.drawings,
    )
    root_schematic = Path(config.project).with_suffix(".kicad_sch").as_posix()
    schematic_files = {
        name: _source_bytes(root, name, sha)
        for name, sha in current.items()
        if name.endswith(".kicad_sch")
    }
    project_directory = Path(config.project).parent.as_posix()
    schematic_tree = (
        VerifiedSchematicSourceTree(
            root_path=root_schematic,
            project_directory=project_directory,
            source_files=tuple(
                SchematicSourceFile(
                    source_path=name,
                    source_sha256=current[name],
                    contents=content,
                )
                for name, content in sorted(schematic_files.items())
            ),
        )
        if root_schematic in schematic_files
        else None
    )
    schematic_resolution = schematic_symbol_anchors(
        schematic_tree,
        root_path=root_schematic,
        project_directory=project_directory,
        project_name=Path(config.project).stem,
    )
    if any(
        current.get(source_path) != source_sha256
        for source_path, source_sha256 in schematic_resolution.source_hashes.items()
    ):
        raise ValueError("Schematic anchor resolution differs from the admitted source inventory")
    schematic_drawings = tuple(item for item in findings.drawings if item.kind == "schematic")
    root_instance = None
    if root_schematic in schematic_files:
        document = schematic_root(schematic_files[root_schematic])
        text = document.text
        root_node = document.root
        if not schematic_sheet_references(schematic_files[root_schematic]):
            root_instance = "/" + schematic_scalar(text, root_node, "uuid")
    drawing_resolution = schematic_drawing_bindings(
        schematic_drawings,
        current,
        root_source=root_schematic,
        legacy_root_instance=root_instance,
    )
    plan = parts.plan
    assert plan is not None
    variant_components = tuple(read_components(variant.netlist_path)) if variant is not None else ()
    locations = CrossProbeLocationEvidence(
        source_hashes=current,
        board_marker_resolution=board_marker_resolution,
        schematic_anchor_resolution=schematic_resolution,
        schematic_drawing_resolution=drawing_resolution,
    )
    population = reconcile_cross_probe_population(
        CrossProbePopulationInput(
            parts_components=plan.components,
            variant_components=variant_components,
            locations=locations,
            variant=variant,
        )
    )
    entries = population.entries
    board_only = population.board_only
    issues = [*schematic_resolution.issues, *drawing_resolution.issues]
    if board_marker_resolution.drawing_status == "UNAVAILABLE":
        issues.append("No retained PCB drawing is available for markers.")
    if any(location.drawing_file is None for entry in entries for location in entry.schematic):
        issues.append("Some schematic symbol instances have no uniquely bound SVG drawing.")
    if variant is None:
        issues.append(
            "Variant identity is not recorded in the selected parts and drawing receipts."
        )
    else:
        issues.append(
            "Selected named variant is observed in native exports; the parts receipt has no variant identity."
        )
        if board_only:
            issues.append("Selected variant has PCB references absent from its schematic netlist.")

    def verify_inputs() -> None:
        verify_cross_probe_inputs(root, admitted)

    verify_inputs()
    target = (
        request.output or Path("build/cross-probe") / f"{request.project_id}-{uuid4().hex[:12]}"
    )
    directory = receipt_directory(root, request.project_id, target)
    for name, content in drawing_bytes.items():
        (directory / name).write_bytes(content)
    report = CrossProbeReport(
        project_id=request.project_id,
        parts_report=parts_path.relative_to(root).as_posix(),
        parts_report_sha256=parts_sha,
        findings_view=findings_path.relative_to(root).as_posix(),
        findings_view_sha256=findings_sha,
        source_hashes=current,
        variant_scope="NAMED_OBSERVED" if variant is not None else "NOT_RECORDED",
        assembly_variant=variant.name if variant is not None else None,
        variant_lint_report=(
            variant.lint_path.relative_to(root).as_posix() if variant is not None else None
        ),
        variant_lint_report_sha256=variant.lint_sha256 if variant is not None else None,
        variant_evidence_sha256=variant.evidence_sha256 if variant is not None else {},
        variant_board_only=board_only,
        entries=entries,
        drawings=findings.drawings,
        issues=tuple(issues),
        output_directory=str(directory),
    )
    (directory / "index.html").write_text(render_cross_probe(report), encoding="utf-8")
    verify_inputs()
    report = report.model_copy(
        update={"artifacts_sha256": {path.name: digest(path) for path in directory.iterdir()}}
    )
    write_model(directory / "cross-probe.json", report)
    return report


def build_cross_probe(
    root: Path,
    project_id: str,
    parts_report: Path,
    findings_view: Path,
    output: Path | None = None,
    assembly_variant: str | None = None,
) -> CrossProbeReport:
    """Adapt the legacy positional call to the typed cross-probe operation."""
    return build_cross_probe_request(
        root,
        CrossProbeBuildRequest(
            project_id=project_id,
            parts_report=parts_report,
            findings_view=findings_view,
            output=output,
            assembly_variant=assembly_variant,
        ),
    )
