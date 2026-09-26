"""Fixed-command MCP adapters for reviewed electrical requirements and analysis."""
from __future__ import annotations

from pathlib import Path

from . import contract_coach, electrical_runner, electrical_setup
from .doctor import NativeRunner
from .mcp_workflow import fresh_output, native_summary_path, selected_project
from .models import (
    ElectricalAnalysisReport,
    ElectricalInputInventory,
    ElectricalSetupReport,
    ElectricalSuiteReport,
)
from .selection import ProjectSelector


def init_electrical(root: Path, project_id: str,
                    ngspice_version: str = "UNREVIEWED") -> ElectricalSetupReport:
    """Add pending requirements only; no observations become approved limits or bindings."""
    selected_project(root, project_id)
    return electrical_setup.initialize(root, project_id, ngspice_version)


def capture_electrical_inputs(root: Path, project_id: str, view_id: str,
                              models: tuple[str, ...] = ()) -> ElectricalInputInventory:
    """Capture UNREVIEWED input hashes in a fresh ignored receipt without source edits."""
    root = root.resolve()
    selected_project(root, project_id)
    output = fresh_output(root, "electrical-inputs", view_id)
    return electrical_setup.capture_inputs(root, project_id, models, output)


def analyze_electrical(root: Path, project_id: str, view_id: str,
                       native_summary: str | None = None,
                       runner: NativeRunner = "auto") -> ElectricalAnalysisReport:
    """Run declared analyses with fixed executables and optional source-bound native evidence."""
    root = root.resolve()
    selected_project(root, project_id)
    if runner not in {"auto", "local", "container"}:
        raise ValueError(f"Unknown native runner: {runner}")
    summary = None if native_summary is None else native_summary_path(root, native_summary)
    output = fresh_output(root, "electrical", view_id)
    native_runner = (
        contract_coach.LocalNetlistRunner("kicad-cli") if runner == "local"
        else contract_coach.ContainerNetlistRunner() if runner == "container"
        else contract_coach.AutoNetlistRunner("kicad-cli")
    )
    return electrical_runner.analyze(root, project_id, output, summary,
                                     cli="kicad-cli", ngspice="ngspice", runner=native_runner)


def check_electrical_scope(root: Path, project_ids: tuple[str, ...] = (),
                           product_ids: tuple[str, ...] = (), tags: tuple[str, ...] = (),
                           exclude_tags: tuple[str, ...] = ()) -> ElectricalSuiteReport:
    """Use the CLI's union/exclusion selectors and keep NOT_CONFIGURED and FAIL results."""
    return electrical_runner.analyze_scope(root, ProjectSelector(
        project_ids=project_ids, product_ids=product_ids, tags=tags, excluded_tags=exclude_tags,
    ), cli="kicad-cli", ngspice="ngspice")
