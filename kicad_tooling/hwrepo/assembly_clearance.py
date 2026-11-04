"""Source-bound board clearance to a project-authored enclosure free-space box."""

from __future__ import annotations

import hashlib
from pathlib import Path
from uuid import uuid4

from .assembly_clearance_geometry import measure_free_space_box
from .assembly_clearance_html import render_assembly_clearance
from .assembly_clearance_models import AssemblyClearanceContract, AssemblyClearanceReport
from .assembly_mesh_surfaces import compare_mesh_surfaces
from .assembly_review import build_assembly_review, selected_assembly_contract
from .contract_coach import receipt_directory
from .contracts import parse_model_text, repo_path, write_model
from .discovery import load_config
from .evidence import digest
from .project_source_hashes import hash_project_sources as hashes
from .selection import resolve_project
from .three_d_glb import mesh_geometry, mesh_triangles


def build_assembly_clearance(
    root: Path,
    project_id: str,
    board_receipt: Path,
    placement_contract: Path,
    clearance_contract: Path,
    output: Path | None = None,
) -> AssemblyClearanceReport:
    """Measure box margins and bounded surface gap for source-bound static GLBs."""
    root = root.resolve()
    project = resolve_project(root, project_id)
    config = load_config(root, project.config)
    current = hashes(root, config.source_roots)
    project_directory = repo_path(root, project.config).parent
    placement_path, placement_bytes = selected_assembly_contract(
        root, project_directory, placement_contract
    )
    clearance_path, clearance_bytes = selected_assembly_contract(
        root, project_directory, clearance_contract, label="Clearance"
    )
    clearance = parse_model_text(clearance_bytes.decode("utf-8"), AssemblyClearanceContract)
    placement_sha = hashlib.sha256(placement_bytes).hexdigest()
    clearance_sha = hashlib.sha256(clearance_bytes).hexdigest()
    if clearance.project_id != project_id or clearance.placement_contract_sha256 != placement_sha:
        raise ValueError("Clearance contract does not bind the selected placement contract")

    def verify_inputs() -> None:
        if (
            hashes(root, config.source_roots) != current
            or load_config(root, project.config) != config
        ):
            raise ValueError("Project source changed during clearance review")
        if digest(placement_path) != placement_sha or digest(clearance_path) != clearance_sha:
            raise ValueError("Placement or clearance contract changed during review")

    verify_inputs()
    target = output or Path("build/assembly-clearance") / f"{project_id}-{uuid4().hex[:12]}"
    directory = receipt_directory(root, project_id, target)
    assembly = build_assembly_review(
        root, project_id, board_receipt, placement_path, directory / "assembly"
    )
    if dict(assembly.source_hashes) != current:
        raise ValueError("Assembly review uses another project source")
    board_copy = directory / "assembly/board.glb"
    if digest(board_copy) != assembly.board_glb_sha256:
        raise ValueError("Retained board model changed during assembly review")
    enclosure_copy = directory / "assembly/enclosure.glb"

    def verify_retained_enclosure() -> None:
        if assembly.status == "READY" and not enclosure_copy.is_file():
            raise ValueError("Retained enclosure model is missing")
        if enclosure_copy.is_file() and digest(enclosure_copy) != assembly.enclosure_sha256:
            raise ValueError("Retained enclosure model changed during clearance review")

    verify_retained_enclosure()
    issues = list(assembly.issues)
    issues.append(
        "Surface gap does not establish solid containment, watertightness, internal features, or fit."
    )
    measurement = None
    surface = None
    board_triangles = ()
    if assembly.status == "READY" and assembly.placement is not None:
        try:
            vertices, board_triangles = mesh_geometry(board_copy)
            measurement = measure_free_space_box(
                vertices,
                board_unit=assembly.board_unit,
                enclosure_unit=assembly.enclosure_unit,
                placement=assembly.placement,
                free_space=clearance.free_space,
                required_margin_mm=clearance.required_margin_mm,
            )
        except (OSError, ValueError, TypeError, OverflowError) as exc:
            issues.append(f"Board mesh geometry is unassessed: {exc}")
        if measurement is not None:
            try:
                surface = compare_mesh_surfaces(
                    board_triangles,
                    mesh_triangles(enclosure_copy),
                    board_unit=assembly.board_unit,
                    enclosure_unit=assembly.enclosure_unit,
                    placement=assembly.placement,
                )
            except (OSError, ValueError, TypeError, OverflowError) as exc:
                issues.append(f"Enclosure mesh surface comparison is unassessed: {exc}")
    else:
        issues.append("A complete placed assembly and board model coverage are required.")
    verify_inputs()
    assembly_path = directory / "assembly/assembly-review.json"
    report = AssemblyClearanceReport(
        project_id=project_id,
        status=(
            "MESH_SURFACE_INTERSECTION"
            if surface is not None and surface.status == "INTERSECTING"
            else "BOX_INTERFERENCE"
            if measurement is not None and measurement.status == "BOX_INTERFERENCE"
            else "LOW_SURFACE_GAP"
            if surface is not None and surface.minimum_gap_mm < clearance.required_margin_mm
            else measurement.status
            if measurement is not None
            else "UNASSESSED"
        ),
        assembly_review=assembly_path.relative_to(root).as_posix(),
        assembly_review_sha256=digest(assembly_path),
        clearance_contract=clearance_path.relative_to(root).as_posix(),
        clearance_contract_sha256=clearance_sha,
        placement_contract=placement_path.relative_to(root).as_posix(),
        placement_contract_sha256=placement_sha,
        board_glb_sha256=assembly.board_glb_sha256,
        enclosure_glb_sha256=assembly.enclosure_sha256,
        source_hashes=current,
        free_space=clearance.free_space,
        required_margin_mm=clearance.required_margin_mm,
        face_margins_mm=measurement.face_margins_mm if measurement is not None else {},
        minimum_margin_mm=measurement.minimum_margin_mm if measurement is not None else None,
        referenced_vertices=measurement.referenced_vertices if measurement is not None else 0,
        surface_status=surface.status if surface is not None else "UNASSESSED",
        surface_gap_mm=surface.minimum_gap_mm if surface is not None else None,
        board_triangles=surface.board_triangles if surface is not None else 0,
        enclosure_triangles=surface.enclosure_triangles if surface is not None else 0,
        surface_pairs_tested=surface.tested_pairs if surface is not None else 0,
        first_surface_intersection=surface.first_intersection if surface is not None else None,
        issues=tuple(issues),
        output_directory=str(directory),
    )
    (directory / "index.html").write_text(render_assembly_clearance(report), encoding="utf-8")
    verify_inputs()
    if digest(assembly_path) != report.assembly_review_sha256:
        raise ValueError("Retained assembly review changed during clearance export")
    if digest(board_copy) != assembly.board_glb_sha256:
        raise ValueError("Retained board model changed during clearance export")
    verify_retained_enclosure()
    report = report.model_copy(
        update={
            "artifacts_sha256": {
                path.name: digest(path) for path in directory.iterdir() if path.is_file()
            }
        }
    )
    write_model(directory / "assembly-clearance.json", report)
    return report
