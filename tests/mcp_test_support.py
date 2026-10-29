"""Shared fixtures and capability declarations for MCP integration tests."""

from __future__ import annotations

import hashlib
import shutil
import tempfile
import unittest
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType

from mcp.types import (
    AudioContent,
    CallToolResult,
    EmbeddedResource,
    ImageContent,
    ResourceLink,
    TextContent,
)

from tests.support import initialize_git, reference_root


def text_content(result: CallToolResult) -> str:
    """Join only text blocks from one MCP response."""
    content: list[TextContent | ImageContent | AudioContent | ResourceLink | EmbeddedResource] = (
        result.content
    )
    return "\n".join(item.text for item in content if isinstance(item, TextContent))


DEFAULT_TOOLS = frozenset(
    {
        "list_projects",
        "get_project",
        "doctor",
        "read_document",
        "preview_import",
        "scan_imports",
        "diagnose_import",
        "rescue_project",
        "list_artifacts",
        "read_artifact",
        "read_project_file",
        "preview_project_edit",
        "inspect_contract",
        "inspect_design_lint",
        "reconcile_design_lint",
        "list_design_lint_rules",
        "check_release",
        "verify_package",
        "inspect_3d_models",
        "preview_model_population",
        "inspect_tool_surfaces",
        "plan_impact",
        "inspect_sourcing_snapshot",
    }
)
CHECK_TOOLS = frozenset(
    {
        "check_project",
        "diagnose_project",
        "capture_contract",
        "check_scope",
        "check_native_scope",
        "analyze_electrical",
        "check_electrical_scope",
    }
)
WRITE_TOOLS = frozenset({"new_project", "import_project"})
EXPORT_TOOLS = frozenset(
    {
        "package_release",
        "restore_package",
        "generate_views",
        "prepare_parts",
        "init_model_map",
        "capture_electrical_inputs",
        "prepare_part_picker",
        "preview_part_selection",
        "preview_model_sync",
        "preview_auto_cad",
        "prepare_supplier_handoff",
        "export_electrical_charts",
        "export_electrical_chart_suite",
        "export_findings_view",
        "export_review_overview",
        "source_cad",
        "preview_cad_import",
    }
)
EDIT_TOOLS = frozenset(
    {
        "apply_project_edit",
        "apply_model_population",
        "save_parts_preferences",
        "init_electrical",
        "apply_part_selection",
        "apply_auto_cad",
        "apply_cad_import",
    }
)
NATIVE_EXPORT_TOOLS = frozenset(
    {
        "export_project",
        "prepare_review",
        "prepare_review_scope",
        "export_3d",
        "convert_pcb",
        "check_step_alignment",
    }
)
DOCUMENTS: Mapping[str, str] = MappingProxyType(
    {
        "start-here": "START_HERE.md",
        "first-board": "FIRST_BOARD.md",
        "diagnostics": "DIAGNOSTICS.md",
        "import-workflow": "IMPORT_WORKFLOW.md",
        "contributor-guide": "CONTRIBUTOR_GUIDE.md",
        "checks-and-ci": "CHECKS_AND_CI.md",
        "mcp": "MCP.md",
        "bom-policy": "BOM_POLICY.md",
        "release-readiness": "RELEASE_READINESS.md",
        "release-storage": "RELEASE_STORAGE.md",
        "project-kinds": "PROJECT_KINDS.md",
        "libraries": "LIBRARIES.md",
        "authority-model": "AUTHORITY_MODEL.md",
        "assurance-profiles": "ASSURANCE_PROFILES.md",
        "three-d-workflow": "THREE_D_WORKFLOW.md",
        "parts-to-order": "PARTS_TO_ORDER.md",
        "tool-surfaces": "TOOL_SURFACES.md",
        "electrical-analysis": "ELECTRICAL_ANALYSIS.md",
        "cad-sourcing": "CAD_SOURCING.md",
    }
)


def snapshot(root: Path) -> dict[str, str]:
    """Capture authored files and directory creation, excluding mutable Git state."""
    result: dict[str, str] = {}
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if ".git" in relative.parts or "__pycache__" in relative.parts:
            continue
        if path.is_symlink():
            result[relative.as_posix()] = f"link:{path.readlink()}"
        elif path.is_file():
            result[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
        else:
            result[relative.as_posix()] = "directory"
    return result


class McpTestCase(unittest.IsolatedAsyncioTestCase):
    """Common isolated project checkout for MCP integration tests."""

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="kicad-mcp-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.root = self.base / "repository"
        shutil.copytree(
            reference_root(),
            self.root,
            ignore=shutil.ignore_patterns(".git", "build", "__pycache__"),
        )
        initialize_git(self.root)
        self.source = self.base / "Incoming board"
        self.source.mkdir()
        self.project = self.source / "Incoming board.kicad_pro"
        self.project.write_text("{}", encoding="utf-8")
        self.project.with_suffix(".kicad_sch").write_text("(kicad_sch)", encoding="utf-8")
        self.project.with_suffix(".kicad_pcb").write_text("(kicad_pcb)", encoding="utf-8")

    def structured(self, result: CallToolResult):
        self.assertFalse(result.is_error, result.content)
        self.assertIsNotNone(result.structured_content)
        return result.structured_content

    @staticmethod
    def text(result: CallToolResult) -> str:
        return text_content(result)

    def import_arguments(self, source: Path | None = None) -> dict[str, str]:
        return {
            "source": str(source or self.project),
            "project_id": "incoming-board",
            "toolchain_id": "kicad-10.0.5",
        }
