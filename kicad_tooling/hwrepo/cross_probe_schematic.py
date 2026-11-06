"""Locate exact symbol instances without collapsing hierarchy or multi-unit parts."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from pathlib import Path

from .cross_probe_schematic_models import (
    SchematicDrawingBindingResolution,
    SchematicSymbolAnchor,
    SchematicSymbolAnchorResolution,
)
from .findings_view_models import ReviewDrawing
from .kicad_sexpr import sexpr_atoms as _atoms
from .schematic_geometry_models import VerifiedSchematicSourceTree
from .schematic_geometry_source import (
    resolve_schematic_sheet_path,
    schematic_at,
    schematic_instance_references,
    schematic_nodes,
    schematic_root,
    schematic_scalar,
    schematic_sheet_references,
    source_tree_sha256,
)
from .schematic_geometry_types import MAX_SHEET_OCCURRENCES
from .source_state_models import SourceHashInventory


def schematic_drawing_bindings(
    drawings: tuple[ReviewDrawing, ...],
    source_hashes: SourceHashInventory,
    *,
    root_source: str,
    legacy_root_instance: str | None,
) -> SchematicDrawingBindingResolution:
    """Use exact source and sheet identities; retain the single-sheet legacy fallback."""
    candidates: dict[str, list[ReviewDrawing]] = defaultdict(list)
    issues: list[str] = []
    schematic = tuple(item for item in drawings if item.kind == "schematic")
    decision_paths: set[str] = set()
    if schematic and legacy_root_instance is not None:
        decision_paths.add(root_source)
    for drawing in schematic:
        if drawing.schematic_source is not None:
            decision_paths.add(drawing.schematic_source)
    observed_hashes = {
        source_path: source_hashes[source_path]
        for source_path in sorted(decision_paths)
        if source_path in source_hashes
    }
    for drawing in schematic:
        if not drawing.mapping_supported:
            continue
        if drawing.sheet_instance_path is not None:
            if (
                drawing.schematic_source is None
                or drawing.schematic_source_sha256 != source_hashes.get(drawing.schematic_source)
            ):
                issues.append(f"Schematic drawing {drawing.file} has stale source binding.")
                continue
            candidates[drawing.sheet_instance_path].append(drawing)
        elif (
            legacy_root_instance is not None
            and len(schematic) == 1
            and drawing.source_artifact.endswith(f"/{Path(root_source).stem}.svg")
        ):
            candidates[legacy_root_instance].append(drawing)
    result: dict[str, ReviewDrawing] = {}
    for instance, matches in candidates.items():
        if len(matches) != 1:
            issues.append(f"Multiple schematic drawings claim sheet instance {instance}.")
        else:
            result[instance] = matches[0]
    issue_tuple = tuple(issues)
    status = (
        "NOT_REQUESTED"
        if not schematic
        else "COMPLETE"
        if len(result) == len(schematic) and not issue_tuple
        else "PARTIAL"
    )
    return SchematicDrawingBindingResolution(
        root_source=root_source,
        legacy_root_instance=legacy_root_instance,
        source_hashes=observed_hashes,
        source_inventory_sha256=source_tree_sha256(observed_hashes),
        source_drawings=schematic,
        status=status,
        drawings_by_instance=result,
        issues=issue_tuple,
    )


def schematic_symbol_anchors(
    source_tree: VerifiedSchematicSourceTree | None,
    *,
    root_path: str,
    project_directory: str,
    project_name: str,
) -> SchematicSymbolAnchorResolution:
    """Resolve exact symbol locations and retain their verified source identity."""
    if source_tree is None:
        return SchematicSymbolAnchorResolution(
            root_path=root_path,
            project_directory=project_directory,
            project_name=project_name,
            status="BLOCKED",
            source_tree_sha256=None,
            source_hashes={},
            anchors_by_casefolded_reference={},
            issues=("Root schematic source is unavailable.",),
        )
    if source_tree.root_path != root_path or source_tree.project_directory != project_directory:
        raise ValueError("Schematic source tree does not match the requested project context")
    source_files = source_tree.source_contents_by_path
    source_hashes = source_tree.source_hashes
    found: dict[str, list[SchematicSymbolAnchor]] = defaultdict(list)
    issues: list[str] = []
    visited: set[str] = set()
    visited_sources: set[str] = set()

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
        payload = source_files.get(source_path)
        if payload is None:
            raise ValueError(f"Schematic child source is unavailable: {source_path}")
        visited_sources.add(source_path)
        document = schematic_root(payload)
        text = document.text
        root = document.root
        reference_resolution = schematic_instance_references(
            text,
            root,
            source_path=source_path,
            project_name=project_name,
            sheet_instance_path=instance_path,
        )
        if (
            reference_resolution.source_path != source_path
            or reference_resolution.source_sha256 != hashlib.sha256(payload).hexdigest()
            or reference_resolution.project_name != project_name
            or reference_resolution.sheet_instance_path != instance_path
        ):
            raise ValueError("Schematic instance references do not match the retained context")
        issues.extend(
            f"{source_path} at {instance_path}: {item}" for item in reference_resolution.issues
        )
        for symbol in schematic_nodes(text, root, "symbol"):
            uuids = schematic_nodes(text, symbol, "uuid")
            if len(uuids) != 1:
                continue
            symbol_uuid = _atoms(text, uuids[0])[1]
            reference = reference_resolution.references_by_symbol_uuid.get(symbol_uuid)
            if reference is None:
                continue
            try:
                x_mm, y_mm, _ = schematic_at(text, symbol, angle_required=True)
            except ValueError as exc:
                issues.append(f"{source_path} at {instance_path}: {reference}: {exc}")
                continue
            found[reference.casefold()].append(
                SchematicSymbolAnchor(
                    reference, source_path, instance_path, sheet_path, symbol_uuid, x_mm, y_mm
                )
            )
        for sheet in schematic_sheet_references(payload):
            child_path = resolve_schematic_sheet_path(source_path, project_directory, sheet.file)
            visit(
                child_path,
                f"{instance_path}/{sheet.uuid}",
                (*sheet_path, sheet.name),
                (*ancestors, source_path),
            )

    document = schematic_root(source_files[root_path])
    text = document.text
    root = document.root
    root_uuid = schematic_scalar(text, root, "uuid")
    visit(root_path, f"/{root_uuid}", (), ())
    referenced_hashes = {
        source_path: source_hashes[source_path] for source_path in sorted(visited_sources)
    }
    anchor_index = {key: tuple(values) for key, values in found.items()}
    issue_tuple = tuple(issues)
    return SchematicSymbolAnchorResolution(
        root_path=root_path,
        project_directory=project_directory,
        project_name=project_name,
        status="PARTIAL" if issue_tuple else "COMPLETE",
        source_tree_sha256=source_tree_sha256(referenced_hashes),
        source_hashes=referenced_hashes,
        anchors_by_casefolded_reference=anchor_index,
        issues=issue_tuple,
    )
