"""Names and project-relative paths for MCP workflow guide resources."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Literal

DocumentName = Literal[
    "start-here",
    "first-board",
    "diagnostics",
    "import-workflow",
    "contributor-guide",
    "checks-and-ci",
    "mcp",
    "bom-policy",
    "release-readiness",
    "release-storage",
    "project-kinds",
    "libraries",
    "authority-model",
    "assurance-profiles",
    "three-d-workflow",
    "parts-to-order",
    "tool-surfaces",
    "electrical-analysis",
    "cad-sourcing",
]
DOCUMENTS: Mapping[DocumentName, str] = MappingProxyType(
    {
        "start-here": "docs/workflow/START_HERE.md",
        "first-board": "docs/workflow/FIRST_BOARD.md",
        "diagnostics": "docs/workflow/DIAGNOSTICS.md",
        "import-workflow": "docs/workflow/IMPORT_WORKFLOW.md",
        "contributor-guide": "docs/workflow/CONTRIBUTOR_GUIDE.md",
        "checks-and-ci": "docs/workflow/CHECKS_AND_CI.md",
        "mcp": "docs/workflow/MCP.md",
        "bom-policy": "docs/workflow/BOM_POLICY.md",
        "release-readiness": "docs/workflow/RELEASE_READINESS.md",
        "release-storage": "docs/workflow/RELEASE_STORAGE.md",
        "project-kinds": "docs/workflow/PROJECT_KINDS.md",
        "libraries": "docs/workflow/LIBRARIES.md",
        "authority-model": "docs/workflow/AUTHORITY_MODEL.md",
        "assurance-profiles": "docs/workflow/ASSURANCE_PROFILES.md",
        "three-d-workflow": "docs/workflow/THREE_D_WORKFLOW.md",
        "parts-to-order": "docs/workflow/PARTS_TO_ORDER.md",
        "tool-surfaces": "docs/workflow/TOOL_SURFACES.md",
        "electrical-analysis": "docs/workflow/ELECTRICAL_ANALYSIS.md",
        "cad-sourcing": "docs/workflow/CAD_SOURCING.md",
    }
)
