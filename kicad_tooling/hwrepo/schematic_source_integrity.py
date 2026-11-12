"""Source-bound structural integrity checks for KiCad schematics."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .kicad_sexpr import SExprSpan, sexpr_atoms, sexpr_children
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
_PIN_NUMBER_MISMATCH_RULE_ID: DesignLintRuleId = "schematic.embedded_symbol_pin_number_mismatch"
_DUPLICATE_OBJECT_UUID_RULE_ID: DesignLintRuleId = "schematic.duplicate_object_uuid"
_SUPPORTED_KICAD_VERSION = "10.0.5"
_SYMBOL_UNIT_CONVERT_SUFFIX = re.compile(r"_(?P<unit>[1-9][0-9]*)_(?P<convert>[1-9][0-9]*)$")
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


def embedded_symbol_pin_number_mismatch_candidates(
    root: Path,
    config: ProjectConfig,
    source_hashes: SourceHashInventory,
) -> tuple[Candidate, ...]:
    """Review mismatched pin numbers for unambiguous single-group symbols."""
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
        try:
            embedded = schematic_library_symbols(text, document.root)
        except ValueError:
            continue

        for symbol in schematic_nodes(text, document.root, "symbol"):
            try:
                library_id = schematic_scalar(text, symbol, "lib_id")
                unit = schematic_scalar(text, symbol, "unit")
            except ValueError:
                continue
            definition = embedded.get(library_id)
            if definition is None:
                continue
            convert_nodes = schematic_nodes(text, symbol, "convert")
            if len(convert_nodes) > 1:
                continue
            if convert_nodes:
                try:
                    convert = schematic_scalar(text, symbol, "convert")
                except ValueError:
                    continue
            else:
                convert = "1"

            pin_groups: list[tuple[str, tuple[str, ...]]] = []
            for sub_symbol in schematic_nodes(text, definition, "symbol"):
                sub_atoms = sexpr_atoms(text, sub_symbol)
                if len(sub_atoms) != 2:
                    continue
                pin_nodes = schematic_nodes(text, sub_symbol, "pin")
                if not pin_nodes:
                    continue
                pin_numbers = _pin_numbers(text, pin_nodes)
                if pin_numbers is None:
                    pin_groups = []
                    break
                pin_groups.append((sub_atoms[1], pin_numbers))
            if len(pin_groups) != 1:
                continue

            group_name, definition_pin_numbers = pin_groups[0]
            suffix = _SYMBOL_UNIT_CONVERT_SUFFIX.search(group_name)
            if suffix is None or (suffix["unit"], suffix["convert"]) != (unit, convert):
                continue
            placed_pin_nodes = schematic_nodes(text, symbol, "pin")
            placed_pin_numbers = _placed_pin_numbers(text, placed_pin_nodes)
            if not placed_pin_numbers:
                continue
            if Counter(definition_pin_numbers) == Counter(placed_pin_numbers):
                continue

            definition_only, placed_only = _number_multiset_difference(
                definition_pin_numbers,
                placed_pin_numbers,
            )
            reference = schematic_property(text, symbol, "Reference") or "<unknown>"
            uuid_nodes = schematic_nodes(text, symbol, "uuid")
            symbol_uuid = (
                schematic_scalar(text, symbol, "uuid") if len(uuid_nodes) == 1 else "<unknown>"
            )
            source_line = text.count("\n", 0, symbol.start) + 1
            candidates.append(
                Candidate(
                    rule_id=_PIN_NUMBER_MISMATCH_RULE_ID,
                    subject=f"{source_file.source_path}:{source_line}:{reference}",
                    message=(
                        f"Placed symbol {reference} has pin numbers "
                        f"{', '.join(placed_pin_numbers)} while its embedded definition "
                        f"for {library_id!r} has {', '.join(definition_pin_numbers)}; "
                        "review which source representation matches the intended symbol."
                    ),
                    evidence={
                        "source_path": (source_file.source_path,),
                        "source_sha256": (source_file.source_sha256,),
                        "source_line": (str(source_line),),
                        "reference": (reference,),
                        "symbol_uuid": (symbol_uuid,),
                        "library_id": (library_id,),
                        "unit": (unit,),
                        "convert": (convert,),
                        "definition_pin_numbers": definition_pin_numbers,
                        "placed_pin_numbers": placed_pin_numbers,
                        "definition_only_pin_numbers": definition_only,
                        "placed_only_pin_numbers": placed_only,
                    },
                )
            )
    return tuple(candidates)


def duplicate_schematic_object_uuid_candidates(
    root: Path,
    config: ProjectConfig,
    source_hashes: SourceHashInventory,
) -> tuple[Candidate, ...]:
    """Review repeated object UUIDs within each verified schematic source file."""
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

        occurrences: dict[str, list[tuple[int, str]]] = {}
        pending: list[tuple[SExprSpan, str]] = [(document.root, "kicad_sch")]
        while pending:
            parent, parent_kind = pending.pop()
            for child in sexpr_children(document.text, parent.start + 1, parent.end - 1):
                atoms = sexpr_atoms(document.text, child)
                if atoms[:1] == ("uuid",):
                    if len(atoms) == 2:
                        line = document.text.count("\n", 0, child.start) + 1
                        occurrences.setdefault(atoms[1], []).append((line, parent_kind))
                    continue
                child_kind = atoms[0] if atoms else "<unknown>"
                pending.append((child, child_kind))

        for object_uuid, entries in sorted(occurrences.items()):
            if len(entries) < 2:
                continue
            source_lines = tuple(str(line) for line, _kind in sorted(entries))
            object_kinds = tuple(sorted({kind for _line, kind in entries}))
            first_line = source_lines[0]
            candidates.append(
                Candidate(
                    rule_id=_DUPLICATE_OBJECT_UUID_RULE_ID,
                    subject=f"{source_file.source_path}:{first_line}:{object_uuid}",
                    message=(
                        f"Schematic UUID {object_uuid!r} is assigned to {len(entries)} "
                        f"objects in this source file on lines {', '.join(source_lines)}; "
                        "review the object identities before release."
                    ),
                    evidence={
                        "source_path": (source_file.source_path,),
                        "source_sha256": (source_file.source_sha256,),
                        "object_uuid": (object_uuid,),
                        "occurrence_count": (str(len(entries)),),
                        "source_lines": source_lines,
                        "object_kinds": object_kinds,
                    },
                )
            )
    return tuple(candidates)


def _pin_numbers(source: str, pin_nodes: tuple[SExprSpan, ...]) -> tuple[str, ...] | None:
    values: list[str] = []
    for pin in pin_nodes:
        try:
            values.append(schematic_scalar(source, pin, "number"))
        except ValueError:
            return None
    return tuple(sorted(values, key=_pin_number_sort_key))


def _placed_pin_numbers(source: str, pin_nodes: tuple[SExprSpan, ...]) -> tuple[str, ...] | None:
    values: list[str] = []
    for pin in pin_nodes:
        atoms = sexpr_atoms(source, pin)
        if len(atoms) != 2 or atoms[0] != "pin":
            return None
        values.append(atoms[1])
    return tuple(sorted(values, key=_pin_number_sort_key))


def _pin_number_sort_key(value: str) -> tuple[int, int | str]:
    return (0, int(value)) if value.isdigit() else (1, value)


def _number_multiset_difference(
    definition_numbers: tuple[str, ...],
    placed_numbers: tuple[str, ...],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    definition_only = tuple(
        sorted(
            (Counter(definition_numbers) - Counter(placed_numbers)).elements(),
            key=_pin_number_sort_key,
        )
    )
    placed_only = tuple(
        sorted(
            (Counter(placed_numbers) - Counter(definition_numbers)).elements(),
            key=_pin_number_sort_key,
        )
    )
    return definition_only, placed_only


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
