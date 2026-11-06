"""Associate supported KiCad SVG sheets with hashed source instances."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from .findings_view_models import ReviewDrawing
from .findings_view_svg import schematic_title_identity
from .schematic_geometry_models import SchematicGeometrySourceBinding
from .schematic_geometry_source import source_tree_sha256
from .schematic_source_tree import schematic_instance_bindings, verified_schematic_sources
from .source_state_models import SourceHashInventory

HIERARCHY_SVG_VERSION = "10.0.6"
ROOT_SVG_VERSIONS = frozenset({"10.0.0", "10.0.5"})


def _bind_single_root_drawing(
    root: Path,
    primary: str,
    source_hashes: SourceHashInventory,
    drawings: tuple[tuple[ReviewDrawing, bytes], ...],
) -> tuple[
    tuple[tuple[ReviewDrawing, bytes], ...],
    tuple[SchematicGeometrySourceBinding, ...],
    str | None,
    tuple[str, ...],
]:
    schematic = tuple((item, content) for item, content in drawings if item.kind == "schematic")
    if len(schematic) != 1:
        return drawings, (), None, ()
    drawing, _ = schematic[0]
    if (
        not drawing.mapping_supported
        or Path(drawing.source_artifact).name != f"{Path(primary).stem}.svg"
    ):
        return drawings, (), None, ()
    try:
        project_directory = Path(primary).parent.as_posix()
        source_tree = verified_schematic_sources(root, primary, project_directory, source_hashes)
        bindings = schematic_instance_bindings(source_tree)
    except (OSError, ValueError) as exc:
        return drawings, (), None, (f"Schematic root instance could not be verified: {exc}",)
    if (
        len(source_tree.source_files) != 1
        or len(bindings) != 1
        or bindings[0].source_path != primary
        or bindings[0].sheet_path != ()
        or bindings[0].source_sha256 != source_tree.source_hashes.get(primary)
    ):
        return drawings, (), None, ()
    binding = bindings[0]
    bound = drawing.model_copy(
        update={
            "sheet_instance_path": binding.sheet_instance_path,
            "sheet_path": (),
            "schematic_source": primary,
            "schematic_source_sha256": binding.source_sha256,
        }
    )
    return (
        tuple(
            (bound, content) if item is drawing else (item, content) for item, content in drawings
        ),
        (binding,),
        source_tree_sha256(source_tree.source_hashes),
        (),
    )


def bind_schematic_drawings(
    root: Path,
    primary: str,
    version: str,
    source_hashes: SourceHashInventory,
    drawings: tuple[tuple[ReviewDrawing, bytes], ...],
) -> tuple[
    tuple[tuple[ReviewDrawing, bytes], ...],
    tuple[SchematicGeometrySourceBinding, ...],
    str | None,
    tuple[str, ...],
]:
    """Bind only unique SVG sheet labels to exact UUID paths in the source tree."""
    if version in ROOT_SVG_VERSIONS:
        return _bind_single_root_drawing(root, primary, source_hashes, drawings)
    if version != HIERARCHY_SVG_VERSION or not any(
        drawing.kind == "schematic" for drawing, _ in drawings
    ):
        return drawings, (), None, ()
    try:
        project_directory = Path(primary).parent.as_posix()
        source_tree = verified_schematic_sources(root, primary, project_directory, source_hashes)
        bindings = schematic_instance_bindings(source_tree)
    except (OSError, ValueError) as exc:
        return drawings, (), None, (f"Schematic sheet instances could not be verified: {exc}",)
    tree_hash = source_tree_sha256(source_tree.source_hashes)
    by_title: dict[tuple[tuple[str, ...], str], list[SchematicGeometrySourceBinding]] = {}
    for binding in bindings:
        key = binding.sheet_path, Path(binding.source_path).name
        by_title.setdefault(key, []).append(binding)
    used: set[str] = set()
    result: list[tuple[ReviewDrawing, bytes]] = []
    issues: list[str] = []
    identities = [
        schematic_title_identity(content)
        for drawing, content in drawings
        if drawing.kind == "schematic"
    ]
    title_counts = Counter(identity for identity in identities if identity is not None)
    for drawing, content in drawings:
        if drawing.kind != "schematic":
            result.append((drawing, content))
            continue
        identity = schematic_title_identity(content)
        matches = () if identity is None else by_title.get(identity, ())
        if (
            not drawing.mapping_supported
            or identity is None
            or title_counts[identity] != 1
            or len(matches) != 1
            or matches[0].sheet_instance_path in used
        ):
            issues.append(
                f"Schematic SVG {drawing.source_artifact} has no unique verified sheet instance."
            )
            result.append((drawing, content))
            continue
        binding = matches[0]
        used.add(binding.sheet_instance_path)
        result.append(
            (
                drawing.model_copy(
                    update={
                        "sheet_instance_path": binding.sheet_instance_path,
                        "sheet_path": binding.sheet_path,
                        "schematic_source": binding.source_path,
                        "schematic_source_sha256": binding.source_sha256,
                    }
                ),
                content,
            )
        )
    missing = {item.sheet_instance_path for item in bindings} - used
    if missing:
        issues.append(f"No uniquely bound SVG is available for {len(missing)} sheet instance(s).")
    return tuple(result), bindings, tree_hash, tuple(issues)
