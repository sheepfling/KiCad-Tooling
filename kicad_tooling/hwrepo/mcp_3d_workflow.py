"""Typed MCP workflows for PCB model inventory, export, and assignment review."""

from __future__ import annotations

from pathlib import Path

from . import model_inventory, model_population, three_d
from .contracts import read_model, repo_path
from .discovery import load_config
from .doctor import NativeRunner
from .evidence import digest
from .mcp_workflow_paths import artifact_file, fresh_output, selected_project
from .models import (
    ModelInventoryReport,
    ModelMap,
    ModelMapAssignment,
    ModelPopulationReport,
    ProjectConfig,
    ProjectKind,
    ThreeDReport,
    ThreeDView,
)


def pcb_config(root: Path, project_id: str) -> ProjectConfig:
    """Resolve one registered PCB without creating outputs or choosing geometry."""
    project = selected_project(root, project_id)
    if project.kind not in {ProjectKind.PCB, ProjectKind.PCB_ONLY}:
        raise ValueError("3D model inspection and export require a pcb or pcb_only project")
    return load_config(root, project.config)


def inspect_3d_models(root: Path, project_id: str) -> ModelInventoryReport:
    """Inspect placed-footprint model references; candidates still require package review."""
    return model_inventory.inspect_models(root, pcb_config(root, project_id))


def export_3d(
    root: Path,
    project_id: str,
    view_id: str,
    runner: NativeRunner = "auto",
    assembly_variant: str | None = None,
    views: list[ThreeDView] | None = None,
) -> ThreeDReport:
    """Create source-bound 3D review artifacts under one fresh ignored destination."""
    root = root.resolve()
    pcb_config(root, project_id)
    if runner not in {"auto", "local", "container"}:
        raise ValueError(f"Unknown native runner: {runner}")
    selected = three_d.selected_views(views)
    output = fresh_output(root, "3d", view_id)
    return three_d.generate(
        root,
        project_id,
        runner=runner,
        cli="kicad-cli",
        output=output,
        assembly_variant=assembly_variant,
        views=selected,
    )


def preview_model_population(
    root: Path,
    project_id: str,
    board_sha256: str,
    assignments: tuple[ModelMapAssignment, ...],
) -> ModelPopulationReport:
    """Retain a source-bound plan for explicitly reviewed model assignments."""
    root = root.resolve()
    pcb_config(root, project_id)
    project = selected_project(root, project_id)
    spec = ModelMap(
        project_id=project_id,
        board_sha256=board_sha256,
        manifest_sha256=digest(repo_path(root, project.config)),
        assignments=assignments,
    )
    repo_path(root, "build/diagnostics")
    return model_population.populate_models(root, project_id, spec)


def apply_model_population(root: Path, project_id: str, plan: str) -> ModelPopulationReport:
    """Apply the selected saved plan only while its source and exact edits still match."""
    root = root.resolve()
    pcb_config(root, project_id)
    plan_path = artifact_file(root, plan)
    reviewed = read_model(plan_path, ModelPopulationReport)
    if reviewed.status != "PLAN" or reviewed.project_id != project_id:
        raise ValueError(
            "Select a PLAN receipt for the same project before applying model assignments"
        )
    map_path = artifact_file(
        root, (plan_path.parent / "locked-model-map.json").relative_to(root).as_posix()
    )
    spec = read_model(map_path, ModelMap)
    repo_path(root, "build/diagnostics")
    return model_population.populate_models(
        root, project_id, spec, apply=True, reviewed_plan=reviewed
    )
