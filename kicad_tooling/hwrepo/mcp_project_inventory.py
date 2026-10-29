"""Register read-only MCP tools for project inventory and detail."""

from __future__ import annotations

from pathlib import Path
from threading import Lock

from mcp.server import MCPServer
from mcp.types import ToolAnnotations

from .inventory import inventory
from .mcp_server_guardrails import service_operation
from .project_detail import read_project_detail
from .project_inventory_models import (
    McpProjectReport,
    ProjectDetailRequest,
    TemplateInventoryReport,
)


def register_project_inventory_tools(
    server: MCPServer[None],
    root: Path,
    operation: Lock,
    read_only: ToolAnnotations,
) -> None:
    """Bind project inventory service operations to their stable MCP contracts."""

    def list_projects() -> TemplateInventoryReport:
        """Discover project IDs, products, tags and toolchains; presence is not validation."""
        with service_operation(operation):
            return inventory(root)

    server.tool(annotations=read_only)(list_projects)

    def get_project(project_id: str) -> McpProjectReport:
        """Read one registered project's inventory, manifest and authored test expectations."""
        with service_operation(operation):
            return read_project_detail(root, ProjectDetailRequest(project_id=project_id))

    server.tool(annotations=read_only)(get_project)
