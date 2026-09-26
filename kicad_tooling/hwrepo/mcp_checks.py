"""Grouped native CLI checks through a fixed MCP executable and fresh receipt."""

from __future__ import annotations

from pathlib import Path

from ..check_all import check_all
from ..check_toolchain import cli_executable
from .mcp_workflow import fresh_output
from .models import McpNativeScopeReport
from .selection import ProjectSelector, resolve_project_ids


def check_native_scope(
    root: Path,
    view_id: str,
    project_ids: tuple[str, ...] = (),
    product_ids: tuple[str, ...] = (),
    tags: tuple[str, ...] = (),
    exclude_tags: tuple[str, ...] = (),
) -> McpNativeScopeReport:
    """Match kicad_tooling.ci --kicad, including its exact local KiCad and domain failures."""
    selector = ProjectSelector(
        project_ids=project_ids,
        product_ids=product_ids,
        tags=tags,
        excluded_tags=exclude_tags,
    )
    selected = list(resolve_project_ids(root, selector)) if selector.active else None
    output = fresh_output(root, "native", view_id)
    result = check_all(root, output, cli_executable("kicad-cli") or "kicad-cli", selected)
    return McpNativeScopeReport(
        status=result.status,
        report=result,
        run_directory=str(output),
    )
