"""Generate source-validated project and BOM views for MCP review."""

from __future__ import annotations

from pathlib import Path

from . import generation
from .mcp_workflow_paths import fresh_output
from .models import McpGenerationReport
from .selection import ProjectSelector, resolve_project_ids


def generate_views(
    root: Path,
    view_id: str,
    project_ids: tuple[str, ...] = (),
    product_ids: tuple[str, ...] = (),
    tags: tuple[str, ...] = (),
    exclude_tags: tuple[str, ...] = (),
) -> McpGenerationReport:
    """Render validated product/BOM projections into a fresh ignored review directory."""
    selector = ProjectSelector(
        project_ids=project_ids,
        product_ids=product_ids,
        tags=tags,
        excluded_tags=exclude_tags,
    )
    selected = resolve_project_ids(root, selector) if selector.active else None
    output = fresh_output(root, "views", view_id)
    output.mkdir(parents=True, exist_ok=False)
    names = generation.generate(root, output=output, selected_project_ids=selected)
    return McpGenerationReport(
        status="PASS",
        directory=output.relative_to(root).as_posix(),
        files=tuple((output / name).relative_to(root).as_posix() for name in names),
    )
