"""Resolve paired KiCad footprint/model sources and preserve their authored transforms.

This adapter proves numbered pad geometry correspondence, not manufacturer fit.
It never moves a footprint, edits a pad, guesses a package, or fetches a network URL.
"""
from __future__ import annotations

import math
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from .contracts import read_model, repo_path
from .discovery import load_config, load_registry
from .model_inventory import _atoms, _children, _Span  # pyright: ignore[reportPrivateUsage]
from .model_population import _validate_shared_roots  # pyright: ignore[reportPrivateUsage]
from .models import ProjectManifest
from .part_cad import (
    _field,  # pyright: ignore[reportPrivateUsage]
    _nodes,  # pyright: ignore[reportPrivateUsage]
    _properties,  # pyright: ignore[reportPrivateUsage]
    _property,  # pyright: ignore[reportPrivateUsage]
    _quote,  # pyright: ignore[reportPrivateUsage]
    _root,  # pyright: ignore[reportPrivateUsage]
    _scalar,  # pyright: ignore[reportPrivateUsage]
    _tokens,  # pyright: ignore[reportPrivateUsage]
)


class MissingFootprintError(ValueError):
    """The exact requested footprint is unavailable, allowing an explicit provider fallback."""


@dataclass(frozen=True)
class PadSignature:
    number: str
    kind: str
    shape: str
    x: float
    y: float
    angle: float
    size: tuple[float, float]
    drill: tuple[float, float]
    drill_offset: tuple[float, float]
    layers: tuple[str, ...]
    roundrect_ratio: float


@dataclass(frozen=True)
class ResolvedModel:
    source_path: Path
    source_bytes: bytes
    source_model_reference: str
    model_expression: str


@dataclass(frozen=True)
class ResolvedFootprint:
    footprint_id: str
    source_path: Path
    source_text: str
    models: tuple[ResolvedModel, ...]
    pads: tuple[PadSignature, ...]
    provenance: str
    official_library: bool = False

    @property
    def source_bytes(self) -> bytes:
        return self.source_text.encode("utf-8")


@dataclass(frozen=True)
class PlacedFootprint:
    reference: str
    footprint_id: str
    layer: str
    rotation: float
    position: tuple[float, float]
    instance_path: str
    pads: tuple[PadSignature, ...]
    model_expressions: tuple[str, ...]
    start: int
    end: int
    geometry_issue: str | None = None


@dataclass(frozen=True)
class BoardInventory:
    path: Path
    source: str
    footprints: tuple[PlacedFootprint, ...]


@dataclass(frozen=True)
class _Library:
    path: Path
    roots: tuple[Path, ...]
    model_roots: tuple[Path, ...]
    provenance: str
    official: bool = False


def _number(value: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("CAD coordinates and transforms must be finite numbers")
    return result


def _values(source: str, parent: _Span, name: str, count: int,
            default: tuple[float, ...] = ()) -> tuple[float, ...]:
    values = _field(source, parent, name, required=False)
    if not values:
        return default
    if len(values) != count:
        raise ValueError(f"Malformed {name} geometry")
    return tuple(_number(value) for value in values)


def _angle(value: float) -> float:
    return round(value % 360, 6) % 360


def _pair(values: tuple[float, ...]) -> tuple[float, float]:
    if len(values) != 2:
        raise ValueError("Expected two coordinates")
    return values[0], values[1]


def _pads(source: str, parent: _Span, rotation: float = 0,
          bottom: bool = False) -> tuple[PadSignature, ...]:
    result: list[PadSignature] = []
    sign = -1 if bottom else 1
    for pad in _nodes(source, parent, "pad"):
        atoms = _atoms(source, pad)
        if len(atoms) != 4 or atoms[3] not in {"rect", "circle", "oval", "roundrect"}:
            raise ValueError("Automatic model alignment supports rectangular, circular, oval and roundrect pads; review custom pads in KiCad")
        if any(_nodes(source, pad, name) for name in ("primitives", "chamfer", "rect_delta")):
            raise ValueError("Automatic model alignment cannot establish custom pad geometry")
        at = _field(source, pad, "at")
        if len(at) not in {2, 3}:
            raise ValueError("Malformed pad position")
        x, y = _number(at[0]), sign * _number(at[1])
        angle = _angle(sign * ((_number(at[2]) if len(at) == 3 else 0) - rotation))
        size = _pair(_values(source, pad, "size", 2))
        drill_nodes = _nodes(source, pad, "drill")
        if len(drill_nodes) > 1:
            raise ValueError("Duplicate drill definition")
        drill = (0.0, 0.0)
        offset = (0.0, 0.0)
        if drill_nodes:
            fields = _atoms(source, drill_nodes[0])[1:]
            if len(fields) == 1:
                drill = (_number(fields[0]), _number(fields[0]))
            elif len(fields) == 3 and fields[0] == "oval":
                drill = (_number(fields[1]), _number(fields[2]))
            else:
                raise ValueError("Malformed pad drill")
            dx, dy = _pair(_values(source, drill_nodes[0], "offset", 2, (0.0, 0.0)))
            offset = (dx, sign * dy)
        if any(value <= 0 for value in size) or any(value < 0 for value in drill):
            raise ValueError("Invalid pad size or drill")
        layers = _field(source, pad, "layers")
        normalized = tuple(sorted(("F." + value[2:] if value.startswith("B.") else
                                   "B." + value[2:] if value.startswith("F.") else value)
                                  if bottom else value for value in layers))
        ratio = _values(source, pad, "roundrect_rratio", 1, (0.0,))[0]
        result.append(PadSignature(atoms[1], atoms[2], atoms[3], x, y, angle,
                                   size, drill, offset, normalized, ratio))
    if not result:
        raise ValueError("The footprint has no pad geometry to confirm model alignment")
    return tuple(sorted(result, key=lambda pad: (pad.number, pad.x, pad.y, pad.kind)))


def _safe_file(path: Path, roots: tuple[Path, ...]) -> Path:
    absolute = Path(os.path.abspath(path))
    if not any(absolute.is_relative_to(root) for root in roots):
        raise ValueError(f"CAD asset escapes its declared source directory: {path}")
    current = absolute
    while True:
        if current.is_symlink():
            raise ValueError(f"Linked CAD asset is not an independent source: {path}")
        if current.parent == current:
            break
        current = current.parent
    if not absolute.is_file():
        raise ValueError(f"CAD source is missing: {absolute}")
    return absolute


def _standard_locations(major: str, explicit: Path | None) -> tuple[tuple[Path, Path], ...]:
    if explicit is not None:
        base = explicit.absolute()
        footprints = base / "footprints" if (base / "footprints").is_dir() else base
        return ((footprints, footprints.parent / "3dmodels"),)
    result: list[tuple[Path, Path]] = []
    footprint_env = os.environ.get(f"KICAD{major}_FOOTPRINT_DIR")
    model_env = os.environ.get(f"KICAD{major}_3DMODEL_DIR")
    if footprint_env:
        directory = Path(footprint_env).absolute()
        result.append((directory, Path(model_env).absolute() if model_env else directory.parent / "3dmodels"))
    candidates = [Path("/Applications/KiCad/KiCad.app/Contents/SharedSupport"),
                  Path("/usr/share/kicad"), Path("/usr/local/share/kicad")]
    for key in ("ProgramFiles", "ProgramFiles(x86)"):
        if os.environ.get(key):
            candidates.extend(sorted((Path(os.environ[key]) / "KiCad").glob(f"{major}*/share/kicad")))
    for base in candidates:
        model_dir = Path(model_env).absolute() if model_env else base / "3dmodels"
        result.append((base / "footprints", model_dir))
    return tuple(result)


def _library(root: Path, project_id: str, nickname: str, explicit: Path | None) -> tuple[_Library, str]:
    registry = load_registry(root)
    record = next((item for item in registry.projects if item.id == project_id), None)
    if record is None:
        raise ValueError(f"Unknown project {project_id!r}")
    config = load_config(root, record.config)
    manifest_path = repo_path(root, record.config)
    manifest = read_model(manifest_path, ProjectManifest)
    _validate_shared_roots(root, registry, manifest)
    roots = tuple(repo_path(root, name) for name in config.source_roots)
    project_dir = repo_path(root, config.project).parent
    major = config.kicad_version.split(".")[0]
    locations = _standard_locations(major, explicit)
    table = project_dir / "fp-lib-table"
    if explicit is None and table.is_file():
        text = table.read_bytes().decode("utf-8")
        parent = _root(text, "fp_lib_table")
        seen: set[str] = set()
        for entry in _nodes(text, parent, "lib"):
            name = _scalar(text, entry, "name")
            if name in seen:
                raise ValueError("Duplicate footprint library nickname in project table")
            seen.add(name)
            if name != nickname:
                continue
            if _scalar(text, entry, "type") != "KiCad":
                raise ValueError("Automatic CAD retrieval needs a native KiCad footprint library")
            uri = _scalar(text, entry, "uri")
            prefix = f"${{KICAD{major}_FOOTPRINT_DIR}}/"
            if uri.startswith(prefix):
                relative = uri[len(prefix):]
                if relative != nickname + ".pretty":
                    raise ValueError("Standard library entry must name its exact library directory")
                break
            if "$" in uri.replace("${KIPRJMOD}", "") or "\\" in uri or ":" in uri or Path(uri).is_absolute():
                raise ValueError("Project footprint library must use a portable KIPRJMOD path")
            directory = Path(uri.replace("${KIPRJMOD}", str(project_dir)))
            if not directory.is_absolute():
                directory = project_dir / directory
            directory = Path(os.path.abspath(directory))
            if not any(directory.is_relative_to(source_root) for source_root in roots):
                raise ValueError("Project footprint library is outside this project's declared sources")
            return _Library(directory, roots, tuple(path for _, path in locations),
                            f"Project-declared footprint source: {directory}"), major
    for footprints, models in locations:
        directory = footprints / (nickname + ".pretty")
        if directory.is_dir():
            if (directory.is_relative_to(root) and not directory.is_relative_to(root / "build")
                    and not any(directory.is_relative_to(source_root) for source_root in roots)):
                raise ValueError("Cannot borrow a different project's private CAD source")
            return _Library(directory, (footprints, models), (models,),
                            (f"Explicit paired CAD library: {footprints}" if explicit is not None else
                             f"Installed KiCad {major} footprint/model pair: {footprints}; exact library revision unverified"),
                            explicit is None and str(footprints) in {
                                "/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints",
                                "/usr/share/kicad/footprints", "/usr/local/share/kicad/footprints"}), major
    raise MissingFootprintError(f"Footprint library {nickname!r} is unavailable. Install the project's KiCad {major} libraries or provide its paired CAD library.")


def _model_path(reference: str, library: _Library, major: str, project_dir: Path) -> Path:
    if "\\" in reference or reference.startswith(("/", "~")) or ":" in reference:
        raise ValueError("Model source path must be local and portable")
    prefix = f"${{KICAD{major}_3DMODEL_DIR}}/"
    if reference.startswith(prefix):
        relative = reference[len(prefix):]
        if "$" in relative or any(part in {"", ".", ".."} for part in relative.split("/")):
            raise ValueError("Unsafe standard 3D model reference")
        for directory in library.model_roots:
            path = directory / relative
            if path.is_file():
                return _safe_file(path, (directory,))
        raise ValueError(f"Paired 3D model is missing: {reference}")
    if reference.startswith("${KIPRJMOD}/"):
        path = project_dir / reference[len("${KIPRJMOD}/"):]
    elif "$" in reference:
        raise ValueError("Unresolved or wrong-version 3D model variable")
    else:
        path = library.path / reference
    return _safe_file(path, library.roots)


def _model_signature(expression: str) -> tuple[str, tuple[float, ...], tuple[float, ...], tuple[float, ...], bool]:
    parent = _root(expression, "model")
    atoms = _atoms(expression, parent)
    if len(atoms) != 2:
        raise ValueError("Malformed model path")
    transforms: list[tuple[float, ...]] = []
    for name, default in (("offset", (0.0, 0.0, 0.0)), ("scale", (1.0, 1.0, 1.0)), ("rotate", (0.0, 0.0, 0.0))):
        nodes = _nodes(expression, parent, name)
        if len(nodes) > 1:
            raise ValueError("Duplicate model transform")
        value = _values(expression, nodes[0], "xyz", 3) if nodes else default
        if len(value) != 3 or (name == "scale" and any(number <= 0 for number in value)):
            raise ValueError("Invalid authored model transform")
        transforms.append(value)
    known = {"offset", "scale", "rotate", "hide", "opacity"}
    if any(_atoms(expression, child)[0] not in known for child in _children(expression, parent.start + 1, parent.end - 1)):
        raise ValueError("Unsupported model expression needs review in KiCad")
    hide = _field(expression, parent, "hide", required=False)
    if hide and hide not in {("yes",), ("no",)}:
        raise ValueError("Malformed model visibility")
    hidden = bool(_nodes(expression, parent, "hide")) and hide != ("no",)
    return atoms[1], transforms[0], transforms[1], transforms[2], hidden


def resolve_footprint(root: Path, project_id: str, footprint_id: str,
                      library_root: Path | None = None) -> ResolvedFootprint:
    """Read one exact footprint and every model paired by its authored expressions."""
    root = root.resolve()
    pieces = footprint_id.split(":")
    if len(pieces) != 2 or any(not value or any(char in value for char in "/\\$") or value in {".", ".."} for value in pieces):
        raise ValueError("Choose an exact KiCad library:footprint identity")
    nickname, name = pieces
    library, major = _library(root, project_id, nickname, library_root)
    member = library.path / (name + ".kicad_mod")
    if not member.exists() and not member.is_symlink():
        if library.provenance.startswith("Project-declared"):
            raise ValueError(f"Declared project footprint is missing: {member}; restore that source before automatic population")
        raise MissingFootprintError(f"Exact footprint member is unavailable: {member}")
    path = _safe_file(member, library.roots)
    source = path.read_bytes().decode("utf-8")
    parent = _root(source, "footprint")
    if _atoms(source, parent) != ("footprint", name):
        raise ValueError("Resolved footprint's name differs from requested identity")
    if _scalar(source, parent, "layer") != "F.Cu":
        raise ValueError("Library footprint must use the standard front-side coordinate system")
    registry = load_registry(root)
    record = next(item for item in registry.projects if item.id == project_id)
    project_dir = repo_path(root, record.project).parent
    models: list[ResolvedModel] = []
    for model in _nodes(source, parent, "model"):
        expression = source[model.start:model.end]
        reference, _, _, _, hidden = _model_signature(expression)
        if hidden:
            raise ValueError("The library's paired model is hidden; review it in KiCad before automatic population")
        target = _model_path(reference, library, major, project_dir)
        if target.suffix.lower() not in {".step", ".stp", ".wrl", ".igs", ".iges"}:
            raise ValueError("Unsupported paired 3D source format")
        models.append(ResolvedModel(target, target.read_bytes(), reference, expression))
    if not models:
        raise ValueError("This footprint has no paired 3D model; obtain the manufacturer's paired CAD data")
    return ResolvedFootprint(footprint_id, path, source, tuple(models), _pads(source, parent), library.provenance, library.official)


def _placed(source: str) -> tuple[PlacedFootprint, ...]:
    parent = _root(source, "kicad_pcb")
    if _nodes(source, parent, "module"):
        raise ValueError("Upgrade legacy PCB modules in KiCad before automatic model population")
    result: list[PlacedFootprint] = []
    for span in _nodes(source, parent, "footprint"):
        atoms = _atoms(source, span)
        if len(atoms) != 2:
            raise ValueError("Malformed placed footprint identity")
        properties = _properties(source, span)
        reference = _property(source, properties, "Reference")
        legacy = tuple(_atoms(source, item) for item in _nodes(source, span, "fp_text")
                       if _atoms(source, item)[:2] == ("fp_text", "reference"))
        if len(legacy) > 1 or (legacy and (len(legacy[0]) != 3 or reference and legacy[0][2] != reference)):
            raise ValueError("Conflicting footprint reference")
        if legacy:
            reference = legacy[0][2]
        if not reference or reference in {item.reference for item in result}:
            raise ValueError("Missing or duplicate footprint reference")
        layer = _scalar(source, span, "layer")
        if layer not in {"F.Cu", "B.Cu"}:
            raise ValueError("Footprint is not on a board copper side")
        at = _field(source, span, "at")
        if len(at) not in {2, 3}:
            raise ValueError("Malformed footprint placement")
        rotation = _number(at[2]) if len(at) == 3 else 0.0
        expressions = tuple(source[node.start:node.end] for node in _nodes(source, span, "model"))
        geometry_issue: str | None = None
        try:
            pads = _pads(source, span, rotation, layer == "B.Cu")
        except ValueError as error:
            pads = ()
            geometry_issue = str(error)
        result.append(PlacedFootprint(reference, atoms[1], layer, rotation,
            (_number(at[0]), _number(at[1])), _scalar(source, span, "path", default=""),
            pads, expressions, span.start, span.end, geometry_issue))
    return tuple(result)


def inventory(root: Path, project_id: str) -> BoardInventory:
    registry = load_registry(root)
    record = next((item for item in registry.projects if item.id == project_id), None)
    if record is None:
        raise ValueError(f"Unknown project {project_id!r}")
    path = repo_path(root, record.project).with_suffix(".kicad_pcb")
    source = path.read_bytes().decode("utf-8")
    return BoardInventory(path, source, _placed(source))


def _same_pads(actual: tuple[PadSignature, ...], expected: tuple[PadSignature, ...]) -> bool:
    if len(actual) != len(expected):
        return False
    for a, b in zip(actual, expected):
        if (a.number, a.kind, a.shape, a.layers) != (b.number, b.kind, b.shape, b.layers):
            return False
        values_a = (a.x, a.y, a.angle, *a.size, *a.drill, *a.drill_offset, a.roundrect_ratio)
        values_b = (b.x, b.y, b.angle, *b.size, *b.drill, *b.drill_offset, b.roundrect_ratio)
        if any(abs(x - y) > 0.000001 for x, y in zip(values_a, values_b)):
            return False
    return True


def plan_model_assignment(board_source: str, reference: str, resolved: ResolvedFootprint,
                          model_references: Mapping[str, str]) -> str:
    """Attach the exact source's model expressions only after numbered-pad matching.

    Mappings replace source model paths with vendored portable paths. Existing
    identical assignments are retained byte-for-byte; other assignments conflict.
    """
    placed = next((item for item in _placed(board_source) if item.reference == reference), None)
    if placed is None:
        raise ValueError(f"{reference}: footprint is not placed; update the PCB in KiCad first")
    if placed.footprint_id != resolved.footprint_id:
        raise ValueError(f"{reference}: placed footprint identity differs from paired CAD source")
    if placed.geometry_issue is not None:
        raise ValueError(f"{reference}: {placed.geometry_issue}")
    if not _same_pads(placed.pads, resolved.pads):
        raise ValueError(f"{reference}: numbered pad geometry, spacing, orientation or drills differ from the paired footprint. Update/review the footprint in KiCad; no model was attached.")
    if set(model_references) != {model.source_model_reference for model in resolved.models}:
        raise ValueError("Every paired model needs exactly one portable destination")
    expressions: list[str] = []
    for model in resolved.models:
        destination = model_references[model.source_model_reference]
        if not destination.startswith("${KIPRJMOD}/") or "$" in destination[len("${KIPRJMOD}/"):]:
            raise ValueError("Imported model paths must be portable KIPRJMOD references")
        text = model.model_expression
        token = _tokens(text, _root(text, "model"))[1]
        expressions.append(text[:token.start] + _quote(destination) + text[token.end:])
    if placed.model_expressions:
        existing = tuple(_model_signature(item) for item in placed.model_expressions)
        desired = tuple(_model_signature(item) for item in expressions)
        original = tuple(_model_signature(item.model_expression) for item in resolved.models)
        if len(existing) != len(desired) or any(
            actual != wanted and actual != authored
            for actual, wanted, authored in zip(existing, desired, original)
        ):
            raise ValueError(f"{reference}: existing 3D assignment differs from the paired source; review/remove that assignment in KiCad before replacing it")
        if existing == desired:
            return board_source
        footprint_span = _Span(placed.start, placed.end)
        spans = _nodes(board_source, footprint_span, "model")
        replacements = [(token.start, token.end, _quote(signature[0]))
                        for span, signature in zip(spans, desired)
                        for token in (_tokens(board_source, span)[1],)]
        result = board_source
        for start, end, value in reversed(replacements):
            result = result[:start] + value + result[end:]
        return result
    newline = "\r\n" if "\r\n" in board_source else "\n"
    insertion = newline + newline.join("    " + expression.replace("\r\n", "\n").replace("\n", newline)
                                       for expression in expressions) + newline + "  "
    return board_source[:placed.end - 1] + insertion + board_source[placed.end - 1:]
