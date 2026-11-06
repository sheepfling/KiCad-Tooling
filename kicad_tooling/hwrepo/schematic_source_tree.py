"""Hash-bound schematic source files and exact hierarchy occurrences."""

from __future__ import annotations

import hashlib
from pathlib import Path

from .artifact_access import read_regular_bytes
from .contracts import repo_path
from .schematic_geometry_models import (
    SchematicGeometrySourceBinding,
    SchematicSourceFile,
    VerifiedSchematicSourceTree,
)
from .schematic_geometry_source import (
    resolve_schematic_sheet_path,
    schematic_root,
    schematic_scalar,
    schematic_sheet_references,
)
from .schematic_geometry_types import MAX_SHEET_OCCURRENCES
from .source_state_models import SourceHashInventory


def verified_schematic_sources(
    root: Path,
    root_path: str,
    project_directory: str,
    source_hashes: SourceHashInventory,
) -> VerifiedSchematicSourceTree:
    """Read each project-local sheet source once against the exact saved inventory."""
    source_files: dict[str, SchematicSourceFile] = {}
    pending = [root_path]
    while pending:
        current_path = pending.pop()
        if current_path in source_files:
            continue
        if len(source_files) >= MAX_SHEET_OCCURRENCES:
            raise ValueError(f"Schematic source tree exceeds {MAX_SHEET_OCCURRENCES} unique files")
        expected_hash = source_hashes.get(current_path)
        if expected_hash is None:
            raise ValueError(
                "Referenced hierarchical schematic is absent from the source-bound "
                f"hashes: {current_path}"
            )
        source, _ = read_regular_bytes(repo_path(root, current_path), maximum=16 * 1024 * 1024)
        source_sha256 = hashlib.sha256(source).hexdigest()
        if source_sha256 != expected_hash:
            raise ValueError(f"Schematic differs from the source-bound hashes: {current_path}")
        source_file = SchematicSourceFile(
            source_path=current_path,
            source_sha256=source_sha256,
            contents=source,
        )
        source_files[current_path] = source_file
        for sheet in schematic_sheet_references(source_file.contents):
            child_path = resolve_schematic_sheet_path(current_path, project_directory, sheet.file)
            repo_path(root, child_path)
            if child_path not in source_files:
                pending.append(child_path)
    return VerifiedSchematicSourceTree(
        root_path=root_path,
        project_directory=project_directory,
        source_files=tuple(source_files.values()),
    )


def schematic_instance_bindings(
    source_tree: VerifiedSchematicSourceTree,
) -> tuple[SchematicGeometrySourceBinding, ...]:
    """Resolve reused sheet files to their distinct UUID paths and displayed names."""
    source_files = source_tree.source_files_by_path
    root_path = source_tree.root_path
    if root_path not in source_files:
        raise ValueError("Root schematic source is unavailable")
    document = schematic_root(source_files[root_path].contents)
    text = document.text
    root = document.root
    root_uuid = schematic_scalar(text, root, "uuid")
    found: list[SchematicGeometrySourceBinding] = []
    visited: set[str] = set()

    def visit(
        source_path: str,
        instance_path: str,
        sheet_path: tuple[str, ...],
        ancestors: tuple[str, ...],
    ) -> None:
        if source_path in ancestors:
            raise ValueError(f"Recursive schematic sheet reference: {source_path}")
        if len(visited) >= MAX_SHEET_OCCURRENCES or instance_path in visited:
            raise ValueError("Schematic has too many or duplicate sheet instances")
        visited.add(instance_path)
        source_file = source_files.get(source_path)
        if source_file is None:
            raise ValueError(f"Schematic child source is unavailable: {source_path}")
        found.append(
            SchematicGeometrySourceBinding(
                source_path=source_path,
                source_sha256=source_file.source_sha256,
                sheet_instance_path=instance_path,
                sheet_path=sheet_path,
            )
        )
        for sheet in schematic_sheet_references(source_file.contents):
            child_path = resolve_schematic_sheet_path(
                source_path, source_tree.project_directory, sheet.file
            )
            visit(
                child_path,
                f"{instance_path}/{sheet.uuid}",
                (*sheet_path, sheet.name),
                (*ancestors, source_path),
            )

    visit(root_path, f"/{root_uuid}", (), ())
    return tuple(found)
