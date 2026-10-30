"""Locate exact symbol instances without collapsing hierarchy or multi-unit parts."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from .findings_view_models import ReviewDrawing
from .model_inventory import _atoms  # pyright: ignore[reportPrivateUsage]
from .schematic_geometry_source import (
    resolve_schematic_sheet_path,
    schematic_at,
    schematic_instance_references,
    schematic_nodes,
    schematic_root,
    schematic_scalar,
    schematic_sheet_references,
)
from .schematic_geometry_types import MAX_SHEET_OCCURRENCES


@dataclass(frozen=True, slots=True)
class SchematicSymbolAnchor:
    reference: str
    source_path: str
    sheet_instance_path: str
    sheet_path: tuple[str, ...]
    symbol_uuid: str
    x_mm: float
    y_mm: float


def schematic_drawing_bindings(
    drawings: tuple[ReviewDrawing, ...],
    source_hashes: Mapping[str, str],
    *,
    root_source: str,
    legacy_root_instance: str | None,
) -> tuple[dict[str, ReviewDrawing], tuple[str, ...]]:
    """Use exact source and sheet identities; retain the single-sheet legacy fallback."""
    candidates: dict[str, list[ReviewDrawing]] = defaultdict(list)
    issues: list[str] = []
    schematic = tuple(item for item in drawings if item.kind == "schematic")
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
    return result, tuple(issues)


def schematic_symbol_anchors(
    source_files: Mapping[str, bytes],
    *,
    root_path: str,
    project_directory: str,
    project_name: str,
) -> tuple[dict[str, tuple[SchematicSymbolAnchor, ...]], tuple[str, ...]]:
    """Resolve references for each sheet occurrence and retain all symbol units."""
    if root_path not in source_files:
        return {}, ("Root schematic source is unavailable.",)
    found: dict[str, list[SchematicSymbolAnchor]] = defaultdict(list)
    issues: list[str] = []
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
        payload = source_files.get(source_path)
        if payload is None:
            raise ValueError(f"Schematic child source is unavailable: {source_path}")
        text, root = schematic_root(payload)
        references, mapping_issues = schematic_instance_references(
            text, root, project_name, instance_path
        )
        issues.extend(f"{source_path} at {instance_path}: {item}" for item in mapping_issues)
        for symbol in schematic_nodes(text, root, "symbol"):
            uuids = schematic_nodes(text, symbol, "uuid")
            if len(uuids) != 1:
                continue
            symbol_uuid = _atoms(text, uuids[0])[1]
            reference = references.get(symbol_uuid)
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

    text, root = schematic_root(source_files[root_path])
    root_uuid = schematic_scalar(text, root, "uuid")
    visit(root_path, f"/{root_uuid}", (), ())
    return {key: tuple(values) for key, values in found.items()}, tuple(issues)
