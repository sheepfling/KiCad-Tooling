"""Source-bound integrity checks for embedded schematic library symbols."""

from __future__ import annotations

from pathlib import Path

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .kicad_sexpr import sexpr_atoms
from .project_models import ProjectConfig, ProjectKind
from .schematic_geometry_models import VerifiedSchematicSourceTree
from .schematic_geometry_source import (
    schematic_library_symbols,
    schematic_nodes,
    schematic_property,
    schematic_root,
    schematic_scalar,
)
from .schematic_source_tree import verified_schematic_sources
from .source_state_models import SourceHashInventory

_RULE_ID: DesignLintRuleId = "schematic.missing_embedded_symbol_definition"
_DUPLICATE_RULE_ID: DesignLintRuleId = "schematic.duplicate_embedded_symbol_definition"
_SUPPORTED_KICAD_VERSION = "10.0.5"
_UNPARSEABLE_SOURCE_ERRORS = frozenset(
    {"Malformed KiCad schematic source", "Expected one kicad_sch root"}
)


def missing_embedded_library_symbol_candidates(
    root: Path,
    config: ProjectConfig,
    source_hashes: SourceHashInventory,
) -> tuple[Candidate, ...]:
    """Find placed symbols whose exact library IDs have no embedded definition."""
    source_tree = _integrity_source_tree(root, config, source_hashes)
    if source_tree is None:
        return ()

    candidates: list[Candidate] = []
    for source_file in source_tree.source_files:
        try:
            document = schematic_root(source_file.contents)
        except ValueError as exc:
            if str(exc) in _UNPARSEABLE_SOURCE_ERRORS:
                continue
            raise
        text = document.text
        sections = schematic_nodes(text, document.root, "lib_symbols")
        if len(sections) > 1:
            continue
        try:
            embedded = schematic_library_symbols(text, document.root) if sections else {}
        except ValueError:
            continue
        embedded_ids = tuple(sorted(embedded))
        for symbol in schematic_nodes(text, document.root, "symbol"):
            try:
                library_id = schematic_scalar(text, symbol, "lib_id")
            except ValueError:
                continue
            if library_id in embedded:
                continue

            uuid_nodes = schematic_nodes(text, symbol, "uuid")
            symbol_uuid = (
                schematic_scalar(text, symbol, "uuid") if len(uuid_nodes) == 1 else "<unknown>"
            )
            reference = schematic_property(text, symbol, "Reference") or "<unknown>"
            source_line = text.count("\n", 0, symbol.start) + 1
            candidates.append(
                Candidate(
                    rule_id=_RULE_ID,
                    subject=f"{source_file.source_path}:{source_line}:{reference}",
                    message=(
                        f"Placed symbol {reference} references embedded library ID "
                        f"{library_id!r}, but this schematic has no matching definition."
                    ),
                    evidence={
                        "source_path": (source_file.source_path,),
                        "source_sha256": (source_file.source_sha256,),
                        "source_line": (str(source_line),),
                        "reference": (reference,),
                        "symbol_uuid": (symbol_uuid,),
                        "library_id": (library_id,),
                        "embedded_library_ids": embedded_ids or ("<none>",),
                    },
                )
            )
    return tuple(candidates)


def duplicate_embedded_library_symbol_candidates(
    root: Path,
    config: ProjectConfig,
    source_hashes: SourceHashInventory,
) -> tuple[Candidate, ...]:
    """Review placed library IDs with multiple direct embedded definitions."""
    source_tree = _integrity_source_tree(root, config, source_hashes)
    if source_tree is None:
        return ()

    candidates: list[Candidate] = []
    for source_file in source_tree.source_files:
        try:
            document = schematic_root(source_file.contents)
        except ValueError as exc:
            if str(exc) in _UNPARSEABLE_SOURCE_ERRORS:
                continue
            raise
        text = document.text
        sections = schematic_nodes(text, document.root, "lib_symbols")
        if len(sections) != 1:
            continue

        definitions: dict[str, list[int]] = {}
        for definition in schematic_nodes(text, sections[0], "symbol"):
            atoms = sexpr_atoms(text, definition)
            if len(atoms) == 2 and atoms[0] == "symbol":
                line = text.count("\n", 0, definition.start) + 1
                definitions.setdefault(atoms[1], []).append(line)
        duplicate_lines = {
            library_id: tuple(str(line) for line in lines)
            for library_id, lines in definitions.items()
            if len(lines) > 1
        }
        if not duplicate_lines:
            continue

        placed_references: dict[str, set[str]] = {}
        for symbol in schematic_nodes(text, document.root, "symbol"):
            try:
                library_id = schematic_scalar(text, symbol, "lib_id")
            except ValueError:
                continue
            if library_id not in duplicate_lines:
                continue
            reference = schematic_property(text, symbol, "Reference") or "<unknown>"
            placed_references.setdefault(library_id, set()).add(reference)

        for library_id, definition_lines in sorted(duplicate_lines.items()):
            references = tuple(sorted(placed_references.get(library_id, ())))
            if not references:
                continue
            source_line = int(definition_lines[1])
            candidates.append(
                Candidate(
                    rule_id=_DUPLICATE_RULE_ID,
                    subject=f"{source_file.source_path}:{source_line}:{library_id}",
                    message=(
                        f"Placed symbol ID {library_id!r} has multiple embedded definitions "
                        f"on lines {', '.join(definition_lines)}; review which definition "
                        f"KiCad should use for {', '.join(references)}."
                    ),
                    evidence={
                        "source_path": (source_file.source_path,),
                        "source_sha256": (source_file.source_sha256,),
                        "library_id": (library_id,),
                        "definition_lines": definition_lines,
                        "definition_count": (str(len(definition_lines)),),
                        "references": references,
                    },
                )
            )
    return tuple(candidates)


def _integrity_source_tree(
    root: Path,
    config: ProjectConfig,
    source_hashes: SourceHashInventory,
) -> VerifiedSchematicSourceTree | None:
    if config.kind is ProjectKind.PCB_ONLY or config.kicad_version != _SUPPORTED_KICAD_VERSION:
        return None

    primary_path = Path(config.project).with_suffix(".kicad_sch").as_posix()
    project_directory = Path(primary_path).parent.as_posix()
    try:
        return verified_schematic_sources(
            root,
            primary_path,
            project_directory,
            source_hashes,
        )
    except ValueError as exc:
        if str(exc) in _UNPARSEABLE_SOURCE_ERRORS:
            return None
        raise
