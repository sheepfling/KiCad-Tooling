"""Bounded parts-review exports and reviewed purchasing preference edits for MCP."""
from __future__ import annotations

from pathlib import Path

from . import contract_coach, parts_workflow
from .contracts import repo_path
from .doctor import NativeRunner
from .mcp_workflow import artifact_file, fresh_output, native_summary_path, selected_project
from .models import PurchasingReport
from .purchasing_preferences import save_parts_preferences

__all__ = ["prepare_parts", "save_parts_preferences"]


def preferences_file(root: Path, project_id: str, value: str | None) -> Path | None:
    """Use only selected-island authored preferences or bounded temporary artifacts."""
    project = selected_project(root, project_id)
    docs = repo_path(root, (Path(project.config).parent / "docs").as_posix())
    if value is None:
        default = repo_path(root, (docs / "purchasing.json").relative_to(root).as_posix())
        if default.exists() and not default.is_file():
            raise ValueError("Purchasing preferences must be a regular JSON file")
        return None
    path = repo_path(root, value)
    if not path.is_relative_to(docs):
        path = artifact_file(root, value)
    if path.suffix != ".json" or not path.is_file():
        raise ValueError("Select a preferences JSON in this project's docs/ or build artifacts")
    return path


def prepare_parts(
    root: Path, project_id: str, view_id: str, native_summary: str | None = None,
    preferences: str | None = None, boards: int | None = None,
    spare_percent: int | None = None, spare_minimum: int | None = None,
    runner: NativeRunner = "auto", *, allow_checks: bool = False,
) -> PurchasingReport:
    """Create the CLI's source-bound checklist and conditional order CSV in fresh output."""
    selected_project(root, project_id)
    if native_summary is None and not allow_checks:
        raise ValueError("Fresh parts capture requires --allow-checks as well as --allow-exports; "
                         "otherwise supply a saved native_summary")
    if runner not in {"auto", "local", "container"}:
        raise ValueError(f"Unknown native runner: {runner}")
    if native_summary is not None and runner != "auto":
        raise ValueError("runner applies only to fresh capture, not saved native_summary")
    summary = None if native_summary is None else native_summary_path(root, native_summary)
    requested = preferences_file(root, project_id, preferences)
    output = fresh_output(root, "parts", view_id)
    output.mkdir(parents=True, exist_ok=False)
    native_runner = (
        contract_coach.LocalNetlistRunner("kicad-cli") if runner == "local"
        else contract_coach.ContainerNetlistRunner() if runner == "container"
        else contract_coach.AutoNetlistRunner("kicad-cli")
    )
    report = parts_workflow.prepare(
        root, project_id, output, native_runner, summary, requested,
        boards, spare_percent, spare_minimum,
    )
    parts_workflow.save_report(output, report)
    return report
