"""Register release workflow tools over shared path-safe release operations."""

from __future__ import annotations

from pathlib import Path
from threading import Lock

from mcp.server import MCPServer
from mcp.types import ToolAnnotations

from . import mcp_workflow as workflow
from .mcp_server_guardrails import service_operation
from .release_report_models import ReleasePackageReport, ReleaseReadinessReport


def register_release_tools(
    server: MCPServer[None],
    root: Path,
    operation: Lock,
    read_only: ToolAnnotations,
    create_only: ToolAnnotations,
    *,
    allow_exports: bool,
) -> None:
    """Bind read-only release checks and separately gated archive operations."""

    def check_release(manifest: str) -> ReleaseReadinessReport:
        """Verify a retained release manifest and source evidence; creates no approval."""
        with service_operation(operation):
            return workflow.check_release(root, manifest)

    server.tool(annotations=read_only)(check_release)

    def verify_package(archive: str) -> ReleasePackageReport:
        """Verify an ignored ZIP through temporary restore without running project code."""
        with service_operation(operation):
            return workflow.verify_package(root, archive)

    server.tool(annotations=read_only)(verify_package)

    if allow_exports:

        def package_release(manifest: str, package_id: str) -> ReleasePackageReport:
            """Package retained release evidence into a fresh ignored ZIP; no publishing."""
            with service_operation(operation):
                return workflow.package_release(root, manifest, package_id)

        server.tool(annotations=create_only)(package_release)

        def restore_package(archive: str, restore_id: str) -> ReleasePackageReport:
            """Restore an ignored ZIP to a fresh checkout without running its scripts."""
            with service_operation(operation):
                return workflow.restore_package(root, archive, restore_id)

        server.tool(annotations=create_only)(restore_package)
