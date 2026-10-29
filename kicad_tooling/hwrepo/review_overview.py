"""Build one offline navigation snapshot from explicitly selected project receipts."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from ..validate import hashes
from .contract_coach import receipt_directory
from .contracts import read_model, repo_path, write_model
from .discovery import load_config
from .evidence import digest
from .project_models import ProjectManifest
from .review_overview_evidence import ReviewContext, selected_receipt
from .review_overview_html import render_review_overview
from .review_overview_models import OverviewItem, OverviewKind, ReviewOverviewReport
from .review_overview_receipts import inspect_receipt
from .selection import resolve_project

_FILES: tuple[tuple[OverviewKind, str], ...] = (
    ("native", "summary.json"),
    ("findings", "review.json"),
    ("parts", "report.json"),
    ("three_d", "visualization.json"),
    ("simulation", "charts.json"),
    ("verification", "verification.json"),
)


def build_review_overview(
    root: Path,
    project_id: str,
    *,
    native_summary: Path | None = None,
    findings_view: Path | None = None,
    parts_report: Path | None = None,
    three_d_report: Path | None = None,
    charts_report: Path | None = None,
    verification_report: Path | None = None,
    output: Path | None = None,
) -> ReviewOverviewReport:
    """Assess saved receipts without choosing runs or executing engineering tools."""
    root = root.resolve()
    project = resolve_project(root, project_id)
    manifest_path = repo_path(root, project.config)
    manifest = read_model(manifest_path, ProjectManifest)
    config = load_config(root, project.config)
    current = hashes(root, config.source_roots)
    manifest_hash = digest(manifest_path)
    context = ReviewContext(root, project_id, config, current)
    selections = {
        "native": native_summary,
        "findings": findings_view,
        "parts": parts_report,
        "three_d": three_d_report,
        "simulation": charts_report,
        "verification": verification_report,
    }
    selected: dict[OverviewKind, Path] = {}
    items: list[OverviewItem] = []
    for kind, filename in _FILES:
        requested = selections[kind]
        if requested is None:
            items.append(OverviewItem(kind=kind))
            continue
        path = selected_receipt(root, requested, filename)
        selected[kind] = path
        items.append(inspect_receipt(context, kind, path))

    def verify_inputs() -> None:
        if (
            digest(manifest_path) != manifest_hash
            or read_model(manifest_path, ProjectManifest) != manifest
            or load_config(root, project.config) != config
            or hashes(root, config.source_roots) != current
        ):
            raise ValueError("Project source or configuration changed during overview export")
        for item in items:
            path = selected.get(item.kind)
            if path is not None and inspect_receipt(context, item.kind, path) != item:
                raise ValueError(f"Selected {item.kind} receipt changed during overview export")

    verify_inputs()
    target = output or Path("build/review-overview") / f"{project_id}-{uuid4().hex[:12]}"
    directory = receipt_directory(root, project_id, target)
    report = ReviewOverviewReport(
        project_id=project_id,
        project_manifest=project.config,
        project_manifest_sha256=manifest_hash,
        toolchain_id=config.toolchain_id,
        kicad_version=config.kicad_version,
        current_source_hashes=current,
        items=tuple(items),
        output_directory=str(directory),
    )
    (directory / "index.html").write_text(render_review_overview(root, report), encoding="utf-8")
    verify_inputs()
    report = report.model_copy(
        update={"artifacts_sha256": {"index.html": digest(directory / "index.html")}}
    )
    write_model(directory / "overview.json", report)
    return report
