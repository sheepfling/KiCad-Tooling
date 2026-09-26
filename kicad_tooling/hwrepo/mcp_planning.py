"""Bounded MCP planning adapters over the CLI's non-executing repository services."""
from __future__ import annotations

from pathlib import Path

from ..impact import build_plan
from . import model_population, sourcing
from .contracts import read_model, repo_path
from .mcp_files import artifact_path
from .mcp_workflow import fresh_output, pcb_config
from .models import (
    ImpactPlan,
    ModelPopulationReport,
    PolicyIssue,
    SourcingSnapshot,
    SourcingSnapshotReport,
)


def init_model_map(root: Path, project_id: str, view_id: str) -> ModelPopulationReport:
    """Create a fresh ignored DRAFT; candidate filenames do not select physical models."""
    root = root.resolve()
    pcb_config(root, project_id)
    output = fresh_output(root, "model-maps", view_id)
    destination = repo_path(root, (output / "model-map.json").relative_to(root).as_posix())
    return model_population.init_model_map(root, project_id, destination, output=output)


def plan_impact(
    root: Path, base: str | None = None, head: str = "HEAD",
    paths: tuple[str, ...] | None = None, full: bool = False,
    select_project: str | None = None, select_tag: str | None = None,
    select_product: str | None = None, exclude_tag: str | None = None,
    shard: str | None = None,
) -> ImpactPlan:
    """Plan Git, explicit-path, full or manual-selection scope without running checks."""
    return build_plan(
        root, base=base, head=head, paths=paths, full=full, select_project=select_project,
        select_tag=select_tag, select_product=select_product, exclude_tag=exclude_tag,
        shard=shard,
    )


def inspect_sourcing_snapshot(root: Path, path: str) -> SourcingSnapshotReport:
    """Validate a saved offer artifact without supplier access or purchase approval."""
    # Reject authorization-boundary violations before the CLI-compatible load report.
    source = artifact_path(root, path)
    try:
        if source.exists() and not source.is_file():
            raise ValueError("Select a regular sourcing snapshot artifact")
        snapshot = read_model(source, SourcingSnapshot)
    except (OSError, ValueError) as exc:
        return SourcingSnapshotReport(
            snapshot_id="unreadable-snapshot", offers=0, status="FAIL",
            issues=(PolicyIssue(code="SOURCING_LOAD", location=path, message=str(exc)),),
        )
    return sourcing.check(root, snapshot)
