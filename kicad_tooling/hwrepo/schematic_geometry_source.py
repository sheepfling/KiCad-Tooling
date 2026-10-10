"""Bounded KiCad schematic source parsing and project-local sheet paths."""

from __future__ import annotations

import hashlib
import math
import posixpath
from collections.abc import Mapping
from pathlib import PurePosixPath

from .model_inventory import (  # pyright: ignore[reportPrivateUsage]
    _atoms,  # pyright: ignore[reportPrivateUsage]
    _children,  # pyright: ignore[reportPrivateUsage]
    _Span,  # pyright: ignore[reportPrivateUsage]
)
from .schematic_geometry_types import SchematicSheetReference


def source_tree_sha256(source_hashes: Mapping[str, str]) -> str:
    """Hash a canonical path/hash inventory for one or more source files."""
    tree_hasher = hashlib.sha256()
    for path, source_sha256 in sorted(source_hashes.items()):
        tree_hasher.update(path.encode("utf-8"))
        tree_hasher.update(b"\0")
        tree_hasher.update(source_sha256.encode("ascii"))
        tree_hasher.update(b"\n")
    return tree_hasher.hexdigest()


def schematic_nodes(source: str, parent: _Span, name: str) -> tuple[_Span, ...]:
    return tuple(
        node
        for node in _children(source, parent.start + 1, parent.end - 1)
        if _atoms(source, node)[:1] == (name,)
    )


def schematic_scalar(source: str, parent: _Span, name: str) -> str:
    found = schematic_nodes(source, parent, name)
    if len(found) != 1:
        raise ValueError(f"Expected exactly one {name} field in KiCad schematic")
    atoms = _atoms(source, found[0])
    if len(atoms) != 2:
        raise ValueError(f"Malformed {name} field in KiCad schematic")
    return atoms[1]


def schematic_root(source: bytes) -> tuple[str, _Span]:
    try:
        text = source.decode("utf-8")
        roots = _children(text, 0, len(text))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError("Malformed KiCad schematic source") from exc
    if len(roots) != 1 or _atoms(text, roots[0])[:1] != ("kicad_sch",):
        raise ValueError("Expected one kicad_sch root")
    return text, roots[0]


def schematic_sheet_references(source: bytes) -> tuple[SchematicSheetReference, ...]:
    """Read child-sheet identifiers and file properties from a KiCad schematic."""
    text, root = schematic_root(source)
    result: list[SchematicSheetReference] = []
    seen_uuids: set[str] = set()
    seen_names: set[str] = set()
    for sheet in schematic_nodes(text, root, "sheet"):
        sheet_uuid = schematic_scalar(text, sheet, "uuid")
        sheet_name = schematic_property_aliases(text, sheet, ("Sheet name", "Sheetname"))
        sheet_file = schematic_property_aliases(text, sheet, ("Sheet file", "Sheetfile"))
        if not sheet_uuid or not sheet_name or not sheet_file:
            raise ValueError("Hierarchical sheet is missing its UUID, name, or file property")
        if sheet_uuid in seen_uuids:
            raise ValueError(f"Duplicate hierarchical sheet UUID: {sheet_uuid}")
        if sheet_name.casefold() in seen_names:
            raise ValueError(f"Duplicate hierarchical sheet name: {sheet_name}")
        seen_uuids.add(sheet_uuid)
        seen_names.add(sheet_name.casefold())
        result.append(SchematicSheetReference(sheet_uuid, sheet_name, sheet_file))
    return tuple(result)


def resolve_schematic_sheet_path(
    source_path: str,
    project_directory: str,
    sheet_file: str,
) -> str:
    """Resolve one portable project-local KiCad sheet path without touching disk."""
    if not source_path or "\\" in source_path or ":" in source_path:
        raise ValueError("Schematic source path is not portable")
    if not sheet_file or "\\" in sheet_file or ":" in sheet_file:
        raise ValueError(f"Schematic sheet file is not portable: {sheet_file!r}")
    if "$" in sheet_file and not sheet_file.startswith("${KIPRJMOD}/"):
        raise ValueError(f"Unresolved schematic sheet variable: {sheet_file}")
    file_name = sheet_file.removeprefix("${KIPRJMOD}/")
    if not file_name or PurePosixPath(file_name).is_absolute():
        raise ValueError(f"Schematic sheet file must be project-relative: {sheet_file!r}")
    source_parent = posixpath.dirname(source_path)
    base = project_directory if sheet_file.startswith("${KIPRJMOD}/") else source_parent
    resolved = posixpath.normpath(posixpath.join(base, file_name))
    project_root = posixpath.normpath(project_directory) if project_directory else "."
    if resolved == ".." or resolved.startswith("../"):
        raise ValueError(f"Schematic sheet file escapes the repository: {sheet_file!r}")
    if (
        project_root != "."
        and resolved != project_root
        and not resolved.startswith(project_root + "/")
    ):
        raise ValueError(f"Schematic sheet file escapes its project directory: {sheet_file!r}")
    if not resolved.endswith(".kicad_sch"):
        raise ValueError(f"Schematic sheet file must end in .kicad_sch: {sheet_file!r}")
    return resolved


def schematic_instance_references(
    source: str,
    root: _Span,
    project_name: str,
    sheet_instance_path: str,
) -> tuple[dict[str, str], tuple[str, ...]]:
    references: dict[str, str] = {}
    issues: list[str] = []
    for symbol in schematic_nodes(source, root, "symbol"):
        symbol_uuids = schematic_nodes(source, symbol, "uuid")
        if len(symbol_uuids) != 1:
            issues.append("A placed symbol has no unique UUID for instance mapping")
            continue
        symbol_uuid = _atoms(source, symbol_uuids[0])[1]
        instance_sections = schematic_nodes(source, symbol, "instances")
        matches: list[str] = []
        for section in instance_sections:
            for project in schematic_nodes(source, section, "project"):
                project_atoms = _atoms(source, project)
                if len(project_atoms) != 2 or project_atoms[1] != project_name:
                    continue
                for path in schematic_nodes(source, project, "path"):
                    path_atoms = _atoms(source, path)
                    if len(path_atoms) != 2 or path_atoms[1] != sheet_instance_path:
                        continue
                    reference_nodes = schematic_nodes(source, path, "reference")
                    if len(reference_nodes) != 1:
                        continue
                    reference_atoms = _atoms(source, reference_nodes[0])
                    if len(reference_atoms) == 2 and reference_atoms[1]:
                        matches.append(reference_atoms[1])
        if len(matches) != 1:
            issues.append(
                f"Symbol {symbol_uuid} has no unique reference for sheet instance "
                f"{sheet_instance_path} in project {project_name!r}"
            )
            continue
        references[symbol_uuid] = matches[0]
    return references, tuple(issues)


def schematic_number(value: str, field: str) -> float:
    try:
        result = float(value)
    except ValueError as exc:
        raise ValueError(f"Invalid numeric {field} in KiCad schematic") from exc
    if not math.isfinite(result):
        raise ValueError(f"Non-finite numeric {field} in KiCad schematic")
    return result


def schematic_at(source: str, parent: _Span, *, angle_required: bool) -> tuple[float, float, float]:
    found = schematic_nodes(source, parent, "at")
    if len(found) != 1:
        raise ValueError("Expected exactly one at field in KiCad schematic")
    atoms = _atoms(source, found[0])
    expected = 4 if angle_required else 3
    if len(atoms) != expected:
        raise ValueError("Malformed at field in KiCad schematic")
    return (
        schematic_number(atoms[1], "x coordinate"),
        schematic_number(atoms[2], "y coordinate"),
        schematic_number(atoms[3], "angle") if angle_required else 0.0,
    )


def schematic_property(source: str, parent: _Span, name: str) -> str:
    for node in schematic_nodes(source, parent, "property"):
        atoms = _atoms(source, node)
        if len(atoms) == 3 and atoms[1] == name:
            return atoms[2]
    return ""


def schematic_property_aliases(source: str, parent: _Span, names: tuple[str, ...]) -> str:
    values = [
        atoms[2]
        for node in schematic_nodes(source, parent, "property")
        if len(atoms := _atoms(source, node)) == 3 and atoms[1] in names
    ]
    if len(values) > 1:
        raise ValueError(f"Duplicate KiCad property aliases: {', '.join(names)}")
    return values[0] if values else ""


def schematic_library_symbols(source: str, root: _Span) -> dict[str, _Span]:
    sections = schematic_nodes(source, root, "lib_symbols")
    if len(sections) != 1:
        raise ValueError("Expected one embedded lib_symbols section")
    result: dict[str, _Span] = {}
    for symbol in schematic_nodes(source, sections[0], "symbol"):
        atoms = _atoms(source, symbol)
        if len(atoms) != 2 or not atoms[1] or atoms[1] in result:
            raise ValueError("Malformed or duplicate embedded symbol identity")
        result[atoms[1]] = symbol
    return result
