"""Lossless, read-only plans for reviewed part fields and existing PCB model bodies."""
from __future__ import annotations

import math
import os
import re
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from .contracts import read_model, repo_path
from .discovery import load_config, load_registry
from .model_inventory import (
    _atoms,  # pyright: ignore[reportPrivateUsage]
    _children,  # pyright: ignore[reportPrivateUsage]
    _Span,  # pyright: ignore[reportPrivateUsage]
)
from .model_population import _validate_shared_roots  # pyright: ignore[reportPrivateUsage]
from .models import (
    PartCadChanges,
    PartCadComponent,
    PartRecord,
    PartSourceEdit,
    ProjectKind,
    ProjectManifest,
)


@dataclass(frozen=True)
class _Token:
    start: int
    end: int
    quoted: bool


@dataclass(frozen=True)
class _Change:
    start: int
    end: int
    replacement: str


@dataclass(frozen=True)
class _Placed:
    component: PartCadComponent
    span: _Span
    properties: Mapping[str, _Span]
    instance_path: str
    unit: int
    multiunit: bool
    on_board: bool


@dataclass(frozen=True)
class _Schematic:
    path: Path
    source: str
    symbols: tuple[_Placed, ...]
    board: Path


def _root(source: str, kind: str) -> _Span:
    roots = _children(source, 0, len(source))
    if len(roots) != 1 or _atoms(source, roots[0])[:1] != (kind,):
        raise ValueError(f"Expected exactly one {kind} root")
    for outside in (source[:roots[0].start], source[roots[0].end:]):
        if any(line.split("#", 1)[0].strip() for line in outside.splitlines()):
            raise ValueError(f"Unexpected text outside {kind} root")
    return roots[0]


def _nodes(source: str, parent: _Span, name: str) -> tuple[_Span, ...]:
    return tuple(child for child in _children(source, parent.start + 1, parent.end - 1)
                 if _atoms(source, child)[:1] == (name,))


def _field(source: str, parent: _Span, name: str, *, required: bool = True) -> tuple[str, ...]:
    found = _nodes(source, parent, name)
    if len(found) > 1 or (required and not found):
        raise ValueError(f"Expected one {name} node in CAD source")
    if not found:
        return ()
    return _atoms(source, found[0])[1:]


def _scalar(source: str, parent: _Span, name: str, *, default: str | None = None) -> str:
    values = _field(source, parent, name, required=default is None)
    if not values and default is not None:
        return default
    if len(values) != 1:
        raise ValueError(f"Expected a single {name} value in CAD source")
    return values[0]


def _uuid(value: str) -> str:
    try:
        if str(UUID(value)) != value.casefold():
            raise ValueError("noncanonical UUID")
    except ValueError as exc:
        raise ValueError(f"Invalid CAD UUID: {value!r}") from exc
    return value


def _properties(source: str, parent: _Span) -> dict[str, _Span]:
    result: dict[str, _Span] = {}
    for node in _nodes(source, parent, "property"):
        atoms = _atoms(source, node)
        if len(atoms) != 3 or not atoms[1] or atoms[1] in result:
            raise ValueError("Malformed or duplicate CAD property")
        tokens = _tokens(source, node)
        if len(tokens) != 3 or not tokens[1].quoted or not tokens[2].quoted:
            raise ValueError("CAD property names and values must be quoted strings")
        result[atoms[1]] = node
    return result


def _property(source: str, properties: Mapping[str, _Span], name: str,
              *, required: bool = False) -> str:
    if name not in properties:
        if required:
            raise ValueError(f"Missing {name} property")
        return ""
    return _atoms(source, properties[name])[2]


def _yes_no(source: str, span: _Span, name: str, default: str) -> bool:
    value = _scalar(source, span, name, default=default)
    if value not in {"yes", "no"}:
        raise ValueError(f"Invalid {name} flag")
    return value == "yes"


def _library_units(source: str, root: _Span) -> set[str]:
    libraries = _nodes(source, root, "lib_symbols")
    if len(libraries) != 1:
        raise ValueError("Expected one embedded lib_symbols section")
    multiunit: set[str] = set()
    seen: set[str] = set()
    for symbol in _nodes(source, libraries[0], "symbol"):
        atoms = _atoms(source, symbol)
        if len(atoms) != 2 or atoms[1] in seen:
            raise ValueError("Malformed or duplicate embedded symbol identity")
        seen.add(atoms[1])
        for unit in _nodes(source, symbol, "symbol"):
            name = _atoms(source, unit)
            match = re.search(r"_(\d+)_\d+$", name[1]) if len(name) == 2 else None
            if match is None:
                raise ValueError("Unsupported embedded symbol unit name")
            if int(match[1]) > 1:
                multiunit.add(atoms[1])
    return multiunit


def _read_schematic(root: Path, project_id: str) -> _Schematic:
    root = root.resolve()
    record = next((item for item in load_registry(root).projects if item.id == project_id), None)
    if record is None:
        raise ValueError(f"Unknown project {project_id!r}")
    config = load_config(root, record.config)
    if config.kind not in {ProjectKind.PCB, ProjectKind.SCHEMATIC}:
        raise ValueError("Part selection requires a schematic-backed PCB or schematic project")
    project = repo_path(root, config.project)
    path = repo_path(root, project.with_suffix(".kicad_sch").relative_to(root).as_posix())
    source = path.read_bytes().decode("utf-8")
    parent = _root(source, "kicad_sch")
    if _nodes(source, parent, "sheet"):
        raise ValueError("Hierarchical or reused sheets require part assignment in KiCad; "
                         "the picker currently supports a single top-level schematic")
    if _nodes(source, parent, "symbol_instances"):
        raise ValueError("Legacy symbol_instances annotation requires review and save in KiCad")
    root_uuid = _uuid(_scalar(source, parent, "uuid"))
    multiunit = _library_units(source, parent)
    placed: list[_Placed] = []
    uuids: set[str] = set()
    for span in _nodes(source, parent, "symbol"):
        properties = _properties(source, span)
        reference = _property(source, properties, "Reference", required=True)
        if reference.startswith("#"):
            continue
        symbol_id = _scalar(source, span, "lib_id")
        if not symbol_id:
            raise ValueError(f"{reference}: missing symbol library identity")
        value = _property(source, properties, "Value", required=True)
        symbol_uuid = _uuid(_scalar(source, span, "uuid"))
        if symbol_uuid in uuids:
            raise ValueError("Duplicate placed schematic symbol UUID")
        uuids.add(symbol_uuid)
        unit_text = _scalar(source, span, "unit")
        if not unit_text.isdecimal() or int(unit_text) < 1:
            raise ValueError(f"{reference}: invalid symbol unit")
        unit = int(unit_text)
        instances = _nodes(source, span, "instances")
        projects = _nodes(source, instances[0], "project") if len(instances) == 1 else ()
        if len(projects) != 1 or _atoms(source, projects[0]) != ("project", project.stem):
            raise ValueError(f"{reference}: ambiguous or mismatched KiCad project instance")
        paths = _nodes(source, projects[0], "path")
        if len(paths) != 1 or _atoms(source, paths[0]) != ("path", "/" + root_uuid):
            raise ValueError(f"{reference}: ambiguous or hierarchical schematic instance path")
        if (_scalar(source, paths[0], "reference") != reference
                or _scalar(source, paths[0], "unit") != unit_text):
            raise ValueError(f"{reference}: displayed reference/unit differs from its project instance")
        component = PartCadComponent(
            reference=reference, symbol_id=symbol_id, value=value,
            footprint=_property(source, properties, "Footprint"),
            part_id=_property(source, properties, "PART_ID") or None,
            source_path=path.relative_to(root).as_posix(), uuid=symbol_uuid,
            dnp=_yes_no(source, span, "dnp", "no"),
            exclude_from_bom=not _yes_no(source, span, "in_bom", "yes"),
        )
        placed.append(_Placed(component, span, properties, "/" + root_uuid + "/" + symbol_uuid,
                              unit, symbol_id in multiunit,
                              _yes_no(source, span, "on_board", "yes")))
    board = repo_path(root, project.with_suffix(".kicad_pcb").relative_to(root).as_posix())
    return _Schematic(path, source, tuple(placed), board)


def _grouped(schematic: _Schematic) -> dict[str, list[_Placed]]:
    grouped: dict[str, list[_Placed]] = defaultdict(list)
    for placed in schematic.symbols:
        grouped[placed.component.reference].append(placed)
    for reference, group in grouped.items():
        first = group[0].component.model_dump(exclude={"uuid"})
        if any(item.component.model_dump(exclude={"uuid"}) != first for item in group):
            raise ValueError(f"{reference}: multi-unit or duplicate references have conflicting fields")
        units = [item.unit for item in group]
        if len(units) != len(set(units)):
            raise ValueError(f"{reference}: duplicate schematic reference and unit")
    return grouped


def read_cad_components(root: Path, project_id: str) -> tuple[PartCadComponent, ...]:
    """Inventory unambiguous top-level instances; selecting multiple units is unsupported."""
    groups = _grouped(_read_schematic(root, project_id))
    return tuple(min(group, key=lambda item: item.unit).component
                 for _, group in sorted(groups.items()))


def _tokens(source: str, span: _Span) -> tuple[_Token, ...]:
    tokens: list[_Token] = []
    position = span.start + 1
    while position < span.end - 1:
        if source[position].isspace():
            position += 1
            continue
        if source[position] in "()":
            break
        if source[position] == "#":
            newline = source.find("\n", position, span.end)
            position = span.end if newline == -1 else newline + 1
            continue
        start = position
        quoted = source[position] == '"'
        if quoted:
            position += 1
            while position < span.end - 1:
                if source[position] == "\\":
                    position += 2
                elif source[position] == '"':
                    position += 1
                    break
                else:
                    position += 1
            else:
                raise ValueError("Unterminated CAD property string")
        else:
            while (position < span.end - 1 and not source[position].isspace()
                   and source[position] not in "()"):
                position += 1
        tokens.append(_Token(start, position, quoted))
    return tuple(tokens)


def _quote(value: str) -> str:
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError("Reviewed CAD field contains a control character")
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _property_change(source: str, properties: Mapping[str, _Span], name: str,
                     value: str) -> _Change | None:
    span = properties.get(name)
    if span is None or _property(source, properties, name) == value:
        return None
    tokens = _tokens(source, span)
    if len(tokens) != 3 or not tokens[2].quoted:
        raise ValueError(f"{name}: expected a quoted native property value")
    token = tokens[2]
    return _Change(token.start, token.end, _quote(value))


def _insertion(source: str, span: _Span, expressions: list[str]) -> _Change:
    newline = "\r\n" if "\r\n" in source else "\n"
    position = span.end - 1
    start = source.rfind("\n", 0, span.start) + 1
    indent = source[start:span.start]
    if indent.strip():
        indent = ""
    value = "".join(newline + indent + "  " + expression for expression in expressions)
    return _Change(position, position, value + newline + indent)


def _apply(source: str, changes: list[_Change], kind: str) -> str:
    end = -1
    for change in sorted(changes, key=lambda item: (item.start, item.end)):
        if change.start < end:
            raise ValueError("Overlapping CAD edits")
        end = change.end
    updated = source
    for change in sorted(changes, key=lambda item: item.start, reverse=True):
        updated = updated[:change.start] + change.replacement + updated[change.end:]
    _root(updated, kind)
    return updated


def _schematic_changes(source: str, symbol: _Placed, part: PartRecord) -> list[_Change]:
    binding = part.cad
    if binding is None:
        raise ValueError(f"{part.id}: missing reviewed CAD binding")
    if symbol.multiunit or symbol.unit != 1:
        raise ValueError(f"{symbol.component.reference}: multi-unit symbols must be assigned in KiCad")
    if (symbol.component.symbol_id != binding.symbol_id or symbol.component.value != binding.value):
        raise ValueError(f"{symbol.component.reference}: reviewed symbol/value does not match")
    changes: list[_Change] = []
    additions: list[str] = []
    for name, value in (("PART_ID", part.id), ("Footprint", binding.footprint),
                        ("Manufacturer", part.manufacturer), ("MPN", part.mpn),
                        ("Datasheet", part.datasheet_url)):
        if name in symbol.properties:
            change = _property_change(source, symbol.properties, name, value)
            if change is not None:
                changes.append(change)
        else:
            at = _field(source, symbol.span, "at")
            if len(at) != 3 or not all(math.isfinite(float(item)) for item in at):
                raise ValueError("Expected finite schematic symbol position")
            additions.append(f'(property {_quote(name)} {_quote(value)} (at {at[0]} {at[1]} 0) '
                             '(effects (font (size 1.27 1.27)) hide))')
    if additions:
        changes.append(_insertion(source, symbol.span, additions))
    return changes


def _board_changes(source: str, selected: Mapping[str, PartRecord],
                   symbols: Mapping[str, _Placed], models: Mapping[str, str],
                   ) -> tuple[list[_Change], tuple[str, ...]]:
    parent = _root(source, "kicad_pcb")
    footprints: dict[str, tuple[_Span, Mapping[str, _Span], str]] = {}
    for span in (*_nodes(source, parent, "footprint"), *_nodes(source, parent, "module")):
        header = _atoms(source, span)
        if len(header) != 2:
            raise ValueError("Malformed PCB footprint identity")
        properties = _properties(source, span)
        reference = _property(source, properties, "Reference")
        legacy = tuple(item for item in _nodes(source, span, "fp_text")
                       if _atoms(source, item)[:2] == ("fp_text", "reference"))
        if len(legacy) > 1:
            raise ValueError("Duplicate PCB reference text")
        if legacy:
            atoms = _atoms(source, legacy[0])
            if len(atoms) != 3 or (reference and atoms[2] != reference):
                raise ValueError("Conflicting PCB reference representations")
            reference = atoms[2]
        if not reference or reference in footprints:
            raise ValueError("Missing or duplicate PCB footprint reference")
        footprints[reference] = (span, properties, header[1])
    changes: list[_Change] = []
    pending: list[str] = []
    for reference, part in sorted(selected.items()):
        binding = part.cad
        assert binding is not None
        if reference not in footprints:
            pending.append(reference)
            continue
        span, properties, footprint_id = footprints[reference]
        path = _scalar(source, span, "path", default="")
        value = _property(source, properties, "Value")
        legacy_values = tuple(item for item in _nodes(source, span, "fp_text")
                              if _atoms(source, item)[:2] == ("fp_text", "value"))
        if len(legacy_values) > 1:
            raise ValueError(f"{reference}: duplicate PCB value text")
        if legacy_values:
            atoms = _atoms(source, legacy_values[0])
            if len(atoms) != 3 or (value and value != atoms[2]):
                raise ValueError(f"{reference}: conflicting PCB value representations")
            value = atoms[2]
        attributes = _field(source, span, "attr", required=False)
        if (footprint_id != binding.footprint or path != symbols[reference].instance_path
                or value != binding.value or {"dnp", "exclude_from_bom"}.intersection(attributes)):
            pending.append(reference)
            continue
        model = models[reference]
        if not model.startswith("${KIPRJMOD}/"):
            raise ValueError("Reviewed model reference must use a portable KIPRJMOD path")
        _quote(model)
        assigned = _nodes(source, span, "model")
        if len(assigned) > 1 or (assigned and _atoms(source, assigned[0]) != ("model", model)):
            raise ValueError(f"{reference}: a different existing 3D model needs review in KiCad")
        additions: list[str] = []
        for name, value in (("PART_ID", part.id), ("Manufacturer", part.manufacturer),
                            ("MPN", part.mpn), ("Datasheet", part.datasheet_url)):
            if name in properties:
                change = _property_change(source, properties, name, value)
                if change is not None:
                    changes.append(change)
            else:
                layer = _scalar(source, span, "layer")
                if layer not in {"F.Cu", "B.Cu"}:
                    raise ValueError(f"{reference}: unsupported footprint layer")
                side = "B" if layer == "B.Cu" else "F"
                additions.append(f'(property {_quote(name)} {_quote(value)} (at 0 0 0) '
                                 f'(layer "{side}.Fab") (hide yes) '
                                 '(effects (font (size 1 1) (thickness 0.15))))')
        if additions:
            changes.append(_insertion(source, span, additions))
    return changes, tuple(pending)


def _attach_authored_models(root: Path, project_id: str, source: str,
                            selected: Mapping[str, PartRecord],
                            model_references: Mapping[str, str],
                            pending: tuple[str, ...]) -> str:
    # Local import avoids a cycle with the shared lossless S-expression adapter.
    from .cad_assets import plan_model_assignment, resolve_footprint

    for reference, part in sorted(selected.items()):
        if reference in pending:
            continue
        parent = _root(source, "kicad_pcb")
        if _nodes(source, parent, "module"):
            raise ValueError("Upgrade legacy PCB modules in KiCad before automatic model population")
        footprint = next(span for span in _nodes(source, parent, "footprint")
                         if _property(source, _properties(source, span), "Reference") == reference
                         or any(_atoms(source, item) == ("fp_text", "reference", reference)
                                for item in _nodes(source, span, "fp_text")))
        if _nodes(source, footprint, "model"):
            # Existing user-authored transforms remain unchanged. Their presence
            # does not establish paired-source alignment or physical fit.
            continue
        binding = part.cad
        assert binding is not None
        resolved = resolve_footprint(root, project_id, binding.footprint)
        expected_model = repo_path(root, binding.model)
        if len(resolved.models) != 1 or resolved.models[0].source_path != expected_model:
            raise ValueError(f"{reference}: catalog model must match the model paired in the reviewed footprint; "
                             "update its authored model assignment before selecting this part")
        source = plan_model_assignment(source, reference, resolved,
            {resolved.models[0].source_model_reference: model_references[reference]})
    return source


def validate_footprint_binding(root: Path, project_id: str, footprint: str) -> None:
    """Require a resolvable, declared repository footprint before promising an F8 update."""
    root = root.resolve()
    registry = load_registry(root)
    record = next((item for item in registry.projects if item.id == project_id), None)
    if record is None:
        raise ValueError(f"Unknown project {project_id!r}")
    manifest = read_model(repo_path(root, record.config), ProjectManifest)
    config = load_config(root, record.config)
    _validate_shared_roots(root, registry, manifest)
    pieces = footprint.split(":")
    if len(pieces) != 2 or not all(pieces):
        raise ValueError("Reviewed footprint must use an exact library:name identity")
    library, name = pieces
    if "/" in name or "\\" in name or name in {".", ".."}:
        raise ValueError("Reviewed footprint name must identify one library member")
    project_dir = repo_path(root, config.project).parent
    table_name = (project_dir / "fp-lib-table").relative_to(root).as_posix()
    if table_name not in config.required_inputs:
        raise ValueError("Declare the project's fp-lib-table before selecting a reviewed footprint")
    table = repo_path(root, table_name)
    if not table.is_file():
        raise ValueError("Project fp-lib-table is missing; declare a reviewed footprint library in KiCad")
    source = table.read_bytes().decode("utf-8")
    parent = _root(source, "fp_lib_table")
    entries: dict[str, _Span] = {}
    for entry in _nodes(source, parent, "lib"):
        identifier = _scalar(source, entry, "name")
        if not identifier or identifier in entries:
            raise ValueError("Duplicate or empty footprint library nickname")
        entries[identifier] = entry
    if library not in entries:
        raise ValueError(f"Footprint library {library!r} is not in the declared project fp-lib-table; "
                         "add its reviewed repository library before using the picker")
    entry = entries[library]
    if _scalar(source, entry, "type") != "KiCad":
        raise ValueError("The picker requires a native KiCad footprint library")
    uri = _scalar(source, entry, "uri")
    if (not uri or "\\" in uri or Path(uri).is_absolute() or ":" in uri
            or "$" in uri.replace("${KIPRJMOD}", "") or uri.count("${KIPRJMOD}") > 1):
        raise ValueError("Footprint library is global, machine-specific or unresolved; "
                         "declare a reviewed repository library using KIPRJMOD")
    target = Path(uri.replace("${KIPRJMOD}", str(project_dir)))
    if not target.is_absolute():
        target = project_dir / target
    normalized = Path(os.path.abspath(target / (name + ".kicad_mod")))
    try:
        member_name = normalized.relative_to(root).as_posix()
    except ValueError as exc:
        raise ValueError("Reviewed footprint library escapes the repository") from exc
    member = repo_path(root, member_name)
    if member_name not in config.required_inputs or not any(
        member_name.startswith(source_root + "/") for source_root in config.source_roots
    ):
        raise ValueError(f"Reviewed footprint {member_name} must be declared in this project's inputs")
    if not member.is_file():
        raise ValueError(f"Reviewed footprint file is missing: {member_name}")
    text = member.read_bytes().decode("utf-8")
    footprint_root = _root(text, "footprint")
    if _atoms(text, footprint_root) != ("footprint", name):
        raise ValueError(f"Reviewed footprint file identity differs from {footprint}")


def preview_cad(root: Path, project_id: str, selected: Mapping[str, PartRecord],
                model_references: Mapping[str, str]) -> PartCadChanges:
    """Plan part fields and model links without writing or moving any CAD geometry."""
    root = root.resolve()
    if set(selected) != set(model_references):
        raise ValueError("Every selected reference needs exactly one reviewed model path")
    schematic = _read_schematic(root, project_id)
    groups = _grouped(schematic)
    edits: list[PartSourceEdit] = []
    changes: list[_Change] = []
    symbols: dict[str, _Placed] = {}
    for reference, part in sorted(selected.items()):
        if reference not in groups:
            raise ValueError(f"Unknown schematic reference: {reference}")
        group = groups[reference]
        if len(group) != 1:
            raise ValueError(f"{reference}: multi-unit symbols must be assigned in KiCad")
        symbol = group[0]
        if not symbol.on_board:
            raise ValueError(f"{reference}: off-board components must be assigned in KiCad; "
                             "the board picker cannot add a PCB footprint for them")
        if symbol.component.dnp or symbol.component.exclude_from_bom:
            raise ValueError(f"{reference}: excluded components cannot be selected for purchasing")
        if part.cad is None:
            raise ValueError(f"{part.id}: missing reviewed CAD binding")
        validate_footprint_binding(root, project_id, part.cad.footprint)
        symbols[reference] = symbol
        changes.extend(_schematic_changes(schematic.source, symbol, part))
    after = _apply(schematic.source, changes, "kicad_sch")
    if after != schematic.source:
        edits.append(PartSourceEdit(path=schematic.path.relative_to(root).as_posix(),
                                    before=schematic.source, after=after))
    pending = tuple(sorted(selected))
    if schematic.board.is_file():
        source = schematic.board.read_bytes().decode("utf-8")
        changes, pending = _board_changes(source, selected, symbols, model_references)
        after = _apply(source, changes, "kicad_pcb")
        after = _attach_authored_models(root, project_id, after, selected, model_references, pending)
        if after != source:
            edits.append(PartSourceEdit(path=schematic.board.relative_to(root).as_posix(),
                                       before=source, after=after))
    return PartCadChanges(edits=tuple(edits), pending_references=pending)
