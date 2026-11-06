"""Small source-tree builders shared by schematic cross-probe tests."""

from __future__ import annotations

import hashlib
from pathlib import Path

from kicad_tooling.hwrepo.cross_probe_schematic_models import (
    SchematicDrawingBindingIndex,
    SchematicDrawingBindingResolution,
    SchematicSymbolAnchorIndex,
    SchematicSymbolAnchorResolution,
)
from kicad_tooling.hwrepo.findings_view_models import ReviewDrawing
from kicad_tooling.hwrepo.schematic_geometry_models import (
    SchematicSourceFile,
    VerifiedSchematicSourceTree,
)
from kicad_tooling.hwrepo.schematic_geometry_source import source_tree_sha256
from kicad_tooling.hwrepo.source_state_models import SourceHashInventory

ROOT_PATH = "projects/demo/kicad/root.kicad_sch"
CHILD_PATH = "projects/demo/kicad/child.kicad_sch"
PROJECT_DIRECTORY = "projects/demo/kicad"


def cross_probe_fixture_tree() -> VerifiedSchematicSourceTree:
    """Build a verified source tree from the small checked-in hierarchy fixtures."""
    fixtures = Path(__file__).parent / "fixtures/cross_probe"
    source_contents = {
        ROOT_PATH: (fixtures / "root.kicad_sch").read_bytes(),
        CHILD_PATH: (fixtures / "child.kicad_sch").read_bytes(),
    }
    return VerifiedSchematicSourceTree(
        root_path=ROOT_PATH,
        project_directory=PROJECT_DIRECTORY,
        source_files=tuple(
            SchematicSourceFile(
                source_path=source_path,
                source_sha256=hashlib.sha256(contents).hexdigest(),
                contents=contents,
            )
            for source_path, contents in source_contents.items()
        ),
    )


def source_bound_anchor_resolution(
    *,
    root_path: str,
    project_directory: str,
    project_name: str,
    source_hashes: SourceHashInventory,
    anchors: SchematicSymbolAnchorIndex | None = None,
    issues: tuple[str, ...] = (),
) -> SchematicSymbolAnchorResolution:
    """Build a valid resolution for focused reconciliation contract tests."""
    if root_path not in source_hashes:
        blocked_issues = issues or ("Root schematic source is unavailable.",)
        return SchematicSymbolAnchorResolution(
            root_path=root_path,
            project_directory=project_directory,
            project_name=project_name,
            status="BLOCKED",
            source_tree_sha256=None,
            source_hashes={},
            anchors_by_casefolded_reference={},
            issues=blocked_issues,
        )
    return SchematicSymbolAnchorResolution(
        root_path=root_path,
        project_directory=project_directory,
        project_name=project_name,
        status="PARTIAL" if issues else "COMPLETE",
        source_tree_sha256=source_tree_sha256(source_hashes),
        source_hashes=source_hashes,
        anchors_by_casefolded_reference=anchors or {},
        issues=issues,
    )


def source_bound_drawing_resolution(
    *,
    root_source: str,
    source_hashes: SourceHashInventory,
    source_drawings: tuple[ReviewDrawing, ...],
    drawings_by_instance: SchematicDrawingBindingIndex,
    legacy_root_instance: str | None = None,
    issues: tuple[str, ...] = (),
) -> SchematicDrawingBindingResolution:
    """Build a source-bound drawing index for focused reconciliation tests."""
    status = (
        "NOT_REQUESTED"
        if not source_drawings
        else "COMPLETE"
        if len(drawings_by_instance) == len(source_drawings) and not issues
        else "PARTIAL"
    )
    return SchematicDrawingBindingResolution(
        root_source=root_source,
        legacy_root_instance=legacy_root_instance,
        source_hashes=source_hashes,
        source_inventory_sha256=source_tree_sha256(source_hashes),
        source_drawings=source_drawings,
        status=status,
        drawings_by_instance=drawings_by_instance,
        issues=issues,
    )
