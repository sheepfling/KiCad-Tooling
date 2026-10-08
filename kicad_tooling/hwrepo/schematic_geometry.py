"""Synthetic, source-bound schematic geometry review for KiCad 10.0.5 and 10.0.6."""

from __future__ import annotations

import hashlib
import math
import posixpath
import re
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from functools import lru_cache
from importlib.resources import files
from itertools import pairwise
from pathlib import PurePosixPath
from typing import Literal

from .contracts import parse_model_text
from .model_inventory import (  # pyright: ignore[reportPrivateUsage]
    _atoms,  # pyright: ignore[reportPrivateUsage]
    _children,  # pyright: ignore[reportPrivateUsage]
    _Span,  # pyright: ignore[reportPrivateUsage]
)
from .models import SchematicTextMetricsResource

SUPPORTED_KICAD_VERSION = "10.0.6"
SUPPORTED_KICAD_VERSIONS = frozenset({"10.0.5", "10.0.6"})
SUPPORTED_SCHEMATIC_VERSION = "20231120"
POINT_TOLERANCE_MM = 0.001
MAX_LABEL_ENDPOINT_GAP_MM = 1.27
MAX_PIN_ENDPOINT_GAP_MM = 0.5
DISTANCE_COMPARISON_EPSILON_MM = 1e-9
MAX_SHEET_OCCURRENCES = 1024
_SCHEMATIC_GEOMETRY_RULE_IDS = (
    "schematic.wire_end_on_pin_line",
    "schematic.pin_tip_on_wire_interior",
    "schematic.wire_endpoint_near_pin_tip",
    "schematic.label_near_wire_endpoint",
    "schematic.unmarked_wire_crossing",
    "schematic.unmarked_t_junction",
    "schematic.coincident_text_anchors",
    "schematic.free_text_overlap",
    "schematic.free_text_over_wire",
    "schematic.free_text_over_symbol_body",
    "schematic.wire_through_symbol_body",
)
_PIN_GEOMETRY_RULE_IDS = _SCHEMATIC_GEOMETRY_RULE_IDS[:3]
_SYMBOL_BODY_RULE_IDS = (
    "schematic.free_text_over_symbol_body",
    "schematic.wire_through_symbol_body",
)
_WIRE_GEOMETRY_RULE_IDS = (
    *_PIN_GEOMETRY_RULE_IDS,
    "schematic.label_near_wire_endpoint",
    "schematic.unmarked_wire_crossing",
    "schematic.unmarked_t_junction",
    "schematic.free_text_over_wire",
    "schematic.wire_through_symbol_body",
)
_SUBSYMBOL_UNIT = re.compile(r"_(\d+)_(\d+)\Z")
_TEXT_MARKUP = re.compile(r"[~_^]\{[^{}]*\}")
_TEXT_OVERLAP_GUARD_MM = 0.08
_TEXT_OVERLAP_MIN_AREA_MM2 = 0.05
_TEXT_WIRE_GUARD_MM = 0.12
_TEXT_WIRE_MIN_OVERLAP_MM = 0.2
_TEXT_WIRE_LENGTH_EPSILON_MM = 1e-9
_SYMBOL_BODY_WIRE_GUARD_MM = 0.2
_SYMBOL_BODY_WIRE_MIN_OVERLAP_MM = 0.3
_SYMBOL_BODY_WIRE_LENGTH_EPSILON_MM = 1e-9
_TEXT_BODY_TEXT_GUARD_MM = 0.1
_TEXT_BODY_SYMBOL_GUARD_MM = 0.15
_TEXT_BODY_MIN_OVERLAP_AREA_MM2 = 0.1
_TEXT_BODY_AREA_EPSILON_MM2 = 1e-9
_LABEL_KINDS: tuple[Literal["label", "global_label", "hierarchical_label"], ...] = (
    "label",
    "global_label",
    "hierarchical_label",
)


def _source_tree_sha256(source_hashes: Mapping[str, str]) -> str:
    """Hash a canonical path/hash inventory for one or more source files."""
    tree_hasher = hashlib.sha256()
    for path, source_sha256 in sorted(source_hashes.items()):
        tree_hasher.update(path.encode("utf-8"))
        tree_hasher.update(b"\0")
        tree_hasher.update(source_sha256.encode("ascii"))
        tree_hasher.update(b"\n")
    return tree_hasher.hexdigest()


@dataclass(frozen=True)
class WireEndOnPinLine:
    """A native-unconnected pin whose tip-to-body line meets a wire endpoint."""

    reference: str
    symbol_library_id: str
    symbol_uuid: str
    pin_number: str
    pin_name: str
    pin_uuid: str | None
    pin_tip_mm: tuple[float, float]
    pin_body_end_mm: tuple[float, float]
    wire_uuid: str
    wire_endpoint_mm: tuple[float, float]
    distance_to_pin_tip_mm: float
    distance_along_pin_mm: float
    sheet_instance_path: str = "/"


@dataclass(frozen=True)
class PinTipOnWireInterior:
    """A native-unconnected pin tip intersects the interior of a wire segment."""

    reference: str
    symbol_library_id: str
    symbol_uuid: str
    pin_number: str
    pin_name: str
    pin_uuid: str | None
    pin_tip_mm: tuple[float, float]
    wire_uuid: str
    wire_segment_start_mm: tuple[float, float]
    wire_segment_end_mm: tuple[float, float]
    distance_to_wire_mm: float
    sheet_instance_path: str = "/"


@dataclass(frozen=True)
class WireEndpointNearPinTip:
    """A wire endpoint close to, but not touching, a native-unconnected pin tip."""

    reference: str
    symbol_library_id: str
    symbol_uuid: str
    pin_number: str
    pin_name: str
    pin_uuid: str | None
    pin_tip_mm: tuple[float, float]
    wire_uuid: str
    wire_endpoint_mm: tuple[float, float]
    distance_to_pin_tip_mm: float
    sheet_instance_path: str = "/"


@dataclass(frozen=True)
class LabelWireEndpointCandidate:
    """A wire endpoint within the review radius of an unattached label."""

    wire_uuid: str
    wire_endpoint_mm: tuple[float, float]
    distance_mm: float


@dataclass(frozen=True)
class LabelNearWireEndpoint:
    """A label anchor that narrowly misses nearby wire-endpoint geometry."""

    label_kind: Literal["label", "global_label", "hierarchical_label"]
    text: str
    label_uuid: str
    anchor_mm: tuple[float, float]
    candidates: tuple[LabelWireEndpointCandidate, ...]
    sheet_instance_path: str = "/"


@dataclass(frozen=True)
class UnmarkedWireCrossing:
    """Orthogonal wire interiors intersect without a junction marker."""

    wire_uuids: tuple[str, ...]
    crossing_mm: tuple[float, float]
    sheet_instance_path: str = "/"


@dataclass(frozen=True)
class UnmarkedTJunction:
    """A wire endpoint touches another wire's interior without a junction marker."""

    endpoint_wire_uuid: str
    interior_wire_uuid: str
    junction_mm: tuple[float, float]
    sheet_instance_path: str = "/"


@dataclass(frozen=True)
class CoincidentTextAnchors:
    """Two free-text insertion anchors occupy the same schematic coordinate."""

    first_text: str
    first_uuid: str
    second_text: str
    second_uuid: str
    anchor_mm: tuple[float, float]
    sheet_instance_path: str = "/"


@dataclass(frozen=True)
class FreeTextOverlap:
    """Two distinct free-text anchors have intersecting conservative glyph envelopes."""

    first_text: str
    first_uuid: str
    first_box_mm: tuple[float, float, float, float]
    second_text: str
    second_uuid: str
    second_box_mm: tuple[float, float, float, float]
    overlap_box_mm: tuple[float, float, float, float]
    sheet_instance_path: str = "/"


@dataclass(frozen=True)
class FreeTextWireOverlap:
    """A wire segment crosses the guarded envelope of one supported free-text item."""

    text: str
    text_uuid: str
    text_box_mm: tuple[float, float, float, float]
    wire_uuid: str
    wire_segment_start_mm: tuple[float, float]
    wire_segment_end_mm: tuple[float, float]
    overlap_length_mm: float
    sheet_instance_path: str = "/"


@dataclass(frozen=True)
class FreeTextSymbolBodyOverlap:
    """A supported free-text envelope overlaps a symbol-body envelope."""

    text: str
    text_uuid: str
    text_box_mm: tuple[float, float, float, float]
    reference: str
    symbol_library_id: str
    symbol_uuid: str
    body_box_mm: tuple[float, float, float, float]
    overlap_box_mm: tuple[float, float, float, float]
    overlap_area_mm2: float
    sheet_instance_path: str = "/"


@dataclass(frozen=True)
class WireThroughSymbolBody:
    """A native wire segment crosses a guarded symbol-body envelope."""

    reference: str
    symbol_library_id: str
    symbol_uuid: str
    wire_uuid: str
    body_box_mm: tuple[float, float, float, float]
    overlap_start_mm: tuple[float, float]
    overlap_end_mm: tuple[float, float]
    overlap_length_mm: float
    sheet_instance_path: str = "/"


@dataclass(frozen=True)
class SchematicSourceBinding:
    """One source file and instance path covered by a geometry scan."""

    source_path: str
    source_sha256: str
    sheet_instance_path: str
    sheet_path: tuple[str, ...]


@dataclass(frozen=True)
class SchematicSheetReference:
    """A child sheet declared by one schematic source file."""

    uuid: str
    name: str
    file: str


def _empty_unsupported_by_rule() -> dict[str, tuple[str, ...]]:
    return {}


@dataclass(frozen=True)
class SchematicGeometryScan:
    """Version and source binding for this limited read-only geometry pass."""

    status: Literal["COMPLETE", "PARTIAL", "UNSUPPORTED"]
    source_path: str
    source_sha256: str
    kicad_version: str
    schematic_version: str | None
    findings: tuple[WireEndOnPinLine, ...] = ()
    pin_tip_on_wire_interiors: tuple[PinTipOnWireInterior, ...] = ()
    wire_endpoints_near_pin_tips: tuple[WireEndpointNearPinTip, ...] = ()
    labels_near_wire_endpoints: tuple[LabelNearWireEndpoint, ...] = ()
    unmarked_wire_crossings: tuple[UnmarkedWireCrossing, ...] = ()
    unmarked_t_junctions: tuple[UnmarkedTJunction, ...] = ()
    coincident_text_anchors: tuple[CoincidentTextAnchors, ...] = ()
    free_text_overlaps: tuple[FreeTextOverlap, ...] = ()
    free_text_wire_overlaps: tuple[FreeTextWireOverlap, ...] = ()
    free_text_symbol_body_overlaps: tuple[FreeTextSymbolBodyOverlap, ...] = ()
    wires_through_symbol_bodies: tuple[WireThroughSymbolBody, ...] = ()
    source_tree_sha256: str | None = None
    source_bindings: tuple[SchematicSourceBinding, ...] = ()
    unsupported: tuple[str, ...] = ()
    unsupported_by_rule: Mapping[str, tuple[str, ...]] = field(
        default_factory=_empty_unsupported_by_rule
    )


@dataclass(frozen=True)
class _Pin:
    reference: str
    library_id: str
    symbol_uuid: str
    number: str
    name: str
    pin_uuid: str | None
    tip: tuple[float, float]
    body_end: tuple[float, float]


@dataclass(frozen=True)
class _WireEnd:
    uuid: str
    point: tuple[float, float]


@dataclass(frozen=True)
class _WireSegment:
    uuid: str
    start: tuple[float, float]
    end: tuple[float, float]


@dataclass(frozen=True)
class _LabelAnchor:
    kind: Literal["label", "global_label", "hierarchical_label"]
    text: str
    uuid: str
    point: tuple[float, float]


@dataclass(frozen=True)
class _TextAnchor:
    text: str
    uuid: str
    point: tuple[float, float]


@dataclass(frozen=True)
class _SchematicTextMetrics:
    advances_mm: Mapping[str, float]
    reference_size_mm: float
    single_glyph_end_spacing_mm: float
    line_end_spacing_mm: float
    multiline_line_spacing_mm: float
    vertical_top_ratio: float
    vertical_bottom_ratio: float
    stroke_width_mm: float


@dataclass(frozen=True)
class _FreeTextGeometry:
    anchor: _TextAnchor
    box_mm: tuple[float, float, float, float]


@dataclass(frozen=True)
class _SymbolBodyEnvelope:
    reference: str
    library_id: str
    symbol_uuid: str
    box_mm: tuple[float, float, float, float]


def _nodes(source: str, parent: _Span, name: str) -> tuple[_Span, ...]:
    return tuple(
        node
        for node in _children(source, parent.start + 1, parent.end - 1)
        if _atoms(source, node)[:1] == (name,)
    )


def _scalar(source: str, parent: _Span, name: str) -> str:
    found = _nodes(source, parent, name)
    if len(found) != 1:
        raise ValueError(f"Expected exactly one {name} field in KiCad schematic")
    atoms = _atoms(source, found[0])
    if len(atoms) != 2:
        raise ValueError(f"Malformed {name} field in KiCad schematic")
    return atoms[1]


def _schematic_root(source: bytes) -> tuple[str, _Span]:
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
    text, root = _schematic_root(source)
    result: list[SchematicSheetReference] = []
    seen_uuids: set[str] = set()
    seen_names: set[str] = set()
    for sheet in _nodes(text, root, "sheet"):
        sheet_uuid = _scalar(text, sheet, "uuid")
        sheet_name = _property_aliases(text, sheet, ("Sheet name", "Sheetname"))
        sheet_file = _property_aliases(text, sheet, ("Sheet file", "Sheetfile"))
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


def _instance_references(
    source: str,
    root: _Span,
    project_name: str,
    sheet_instance_path: str,
) -> tuple[dict[str, str], tuple[str, ...]]:
    references: dict[str, str] = {}
    issues: list[str] = []
    for symbol in _nodes(source, root, "symbol"):
        symbol_uuids = _nodes(source, symbol, "uuid")
        if len(symbol_uuids) != 1:
            issues.append("A placed symbol has no unique UUID for instance mapping")
            continue
        symbol_uuid = _atoms(source, symbol_uuids[0])[1]
        instance_sections = _nodes(source, symbol, "instances")
        matches: list[str] = []
        for section in instance_sections:
            for project in _nodes(source, section, "project"):
                project_atoms = _atoms(source, project)
                if len(project_atoms) != 2 or project_atoms[1] != project_name:
                    continue
                for path in _nodes(source, project, "path"):
                    path_atoms = _atoms(source, path)
                    if len(path_atoms) != 2 or path_atoms[1] != sheet_instance_path:
                        continue
                    reference_nodes = _nodes(source, path, "reference")
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


def _number(value: str, field: str) -> float:
    try:
        result = float(value)
    except ValueError as exc:
        raise ValueError(f"Invalid numeric {field} in KiCad schematic") from exc
    if not math.isfinite(result):
        raise ValueError(f"Non-finite numeric {field} in KiCad schematic")
    return result


def _at(source: str, parent: _Span, *, angle_required: bool) -> tuple[float, float, float]:
    found = _nodes(source, parent, "at")
    if len(found) != 1:
        raise ValueError("Expected exactly one at field in KiCad schematic")
    atoms = _atoms(source, found[0])
    expected = 4 if angle_required else 3
    if len(atoms) != expected:
        raise ValueError("Malformed at field in KiCad schematic")
    return (
        _number(atoms[1], "x coordinate"),
        _number(atoms[2], "y coordinate"),
        _number(atoms[3], "angle") if angle_required else 0.0,
    )


def _point_to_segment(
    point: tuple[float, float],
    start: tuple[float, float],
    end: tuple[float, float],
) -> tuple[float, float, float] | None:
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length_squared = dx * dx + dy * dy
    if length_squared <= 0.0:
        return None
    projection = ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / length_squared
    length = math.sqrt(length_squared)
    parameter_tolerance = POINT_TOLERANCE_MM / length
    if projection < -parameter_tolerance or projection > 1.0 + parameter_tolerance:
        return None
    clamped = min(1.0, max(0.0, projection))
    closest = (start[0] + clamped * dx, start[1] + clamped * dy)
    distance = math.hypot(point[0] - closest[0], point[1] - closest[1])
    along = clamped * length
    return distance, along, length


def _transform_point(
    point: tuple[float, float],
    origin: tuple[float, float],
    angle: float,
    mirror: str | None,
) -> tuple[float, float]:
    """Match the KiCad 10.0.6 schematic transform, verified with kicad-cli."""
    local_x, local_y = point
    screen_y = -local_y
    radians = math.radians(angle)
    cosine = math.cos(radians)
    sine = math.sin(radians)
    rotated_x = local_x * cosine + screen_y * sine
    rotated_y = -local_x * sine + screen_y * cosine
    if mirror == "x":
        rotated_y = -rotated_y
    elif mirror == "y":
        rotated_x = -rotated_x
    return round(origin[0] + rotated_x, 6), round(origin[1] + rotated_y, 6)


def _property(source: str, parent: _Span, name: str) -> str:
    for node in _nodes(source, parent, "property"):
        atoms = _atoms(source, node)
        if len(atoms) == 3 and atoms[1] == name:
            return atoms[2]
    return ""


def _property_aliases(source: str, parent: _Span, names: tuple[str, ...]) -> str:
    values = [
        atoms[2]
        for node in _nodes(source, parent, "property")
        if len(atoms := _atoms(source, node)) == 3 and atoms[1] in names
    ]
    if len(values) > 1:
        raise ValueError(f"Duplicate KiCad property aliases: {', '.join(names)}")
    return values[0] if values else ""


def _library_symbols(source: str, root: _Span) -> dict[str, _Span]:
    sections = _nodes(source, root, "lib_symbols")
    if len(sections) != 1:
        raise ValueError("Expected one embedded lib_symbols section")
    result: dict[str, _Span] = {}
    for symbol in _nodes(source, sections[0], "symbol"):
        atoms = _atoms(source, symbol)
        if len(atoms) != 2 or not atoms[1] or atoms[1] in result:
            raise ValueError("Malformed or duplicate embedded symbol identity")
        result[atoms[1]] = symbol
    return result


def _instance_pin_uuids(source: str, placed: _Span) -> dict[str, str]:
    result: dict[str, str] = {}
    for node in _nodes(source, placed, "pin"):
        atoms = _atoms(source, node)
        if len(atoms) != 2 or not atoms[1] or atoms[1] in result:
            raise ValueError("Malformed or duplicate placed symbol pin")
        uuids = _nodes(source, node, "uuid")
        result[atoms[1]] = _atoms(source, uuids[0])[1] if len(uuids) == 1 else ""
    return result


def _pins_for_instance(
    source: str,
    placed: _Span,
    libraries: dict[str, _Span],
    *,
    reference_override: str | None = None,
) -> tuple[tuple[_Pin, ...], str | None]:
    symbol_uuids = _nodes(source, placed, "uuid")
    if len(symbol_uuids) != 1:
        return (), "symbol instance has no unique UUID"
    symbol_uuid = _atoms(source, symbol_uuids[0])[1]
    reference = (
        reference_override
        if reference_override is not None
        else _property(source, placed, "Reference")
    )
    if not reference or reference.startswith("#"):
        return (), "non-component or anonymous symbol"
    library_id = _scalar(source, placed, "lib_id")
    library = libraries.get(library_id)
    if library is None:
        return (), f"embedded symbol unavailable for {library_id}"
    unit_text = _scalar(source, placed, "unit")
    if not unit_text.isdecimal() or int(unit_text) != 1:
        return (), f"multi-unit symbol {reference} is outside this prototype"
    unit = int(unit_text)
    position = _at(source, placed, angle_required=True)
    if position[2] not in {0.0, 90.0, 180.0, 270.0}:
        return (), f"non-orthogonal symbol rotation on {reference}"
    mirrors = _nodes(source, placed, "mirror")
    if len(mirrors) > 1:
        return (), f"ambiguous mirror state on {reference}"
    mirror: str | None = None
    if mirrors:
        mirror_atoms = _atoms(source, mirrors[0])
        if len(mirror_atoms) != 2 or mirror_atoms[1] not in {"x", "y"}:
            return (), f"unsupported mirror state on {reference}"
        mirror = mirror_atoms[1]

    sub_symbols = _nodes(source, library, "symbol")
    parsed: list[tuple[int, int, _Span]] = []
    for sub_symbol in sub_symbols:
        atoms = _atoms(source, sub_symbol)
        suffix = _SUBSYMBOL_UNIT.search(atoms[1]) if len(atoms) == 2 else None
        if suffix is None:
            return (), f"unrecognized embedded unit on {reference}"
        parsed.append((int(suffix[1]), int(suffix[2]), sub_symbol))
    unit_numbers = {subunit for subunit, _, _ in parsed if subunit > 0}
    if unit_numbers != {unit} or any(conversion != 1 for _, conversion, _ in parsed):
        return (), f"multi-unit or multi-conversion symbol {reference} is outside this prototype"

    instance_uuids = _instance_pin_uuids(source, placed)
    pins: list[_Pin] = []
    seen_numbers: set[str] = set()
    for subunit, _, sub_symbol in parsed:
        if subunit not in {0, unit}:
            continue
        for pin_node in _nodes(source, sub_symbol, "pin"):
            pin_number = _scalar(source, pin_node, "number")
            if not pin_number or pin_number in seen_numbers:
                return (), f"duplicate or empty pin number on {reference}"
            seen_numbers.add(pin_number)
            pin_name = _scalar(source, pin_node, "name")
            tip_x, tip_y, pin_angle = _at(source, pin_node, angle_required=True)
            lengths = _nodes(source, pin_node, "length")
            if len(lengths) != 1:
                return (), f"pin length unavailable for {reference}.{pin_number}"
            length_atoms = _atoms(source, lengths[0])
            if len(length_atoms) != 2:
                return (), f"malformed pin length for {reference}.{pin_number}"
            pin_length = _number(length_atoms[1], "pin length")
            if pin_length <= 0:
                return (), f"non-positive pin length for {reference}.{pin_number}"
            radians = math.radians(pin_angle)
            body_x = tip_x + pin_length * math.cos(radians)
            body_y = tip_y + pin_length * math.sin(radians)
            pin_uuid = instance_uuids.get(pin_number) or None
            pins.append(
                _Pin(
                    reference=reference,
                    library_id=library_id,
                    symbol_uuid=symbol_uuid,
                    number=pin_number,
                    name=pin_name,
                    pin_uuid=pin_uuid,
                    tip=_transform_point((tip_x, tip_y), position[:2], position[2], mirror),
                    body_end=_transform_point((body_x, body_y), position[:2], position[2], mirror),
                )
            )
    return tuple(pins), None


def _body_primitive_points(
    source: str,
    primitive: _Span,
    kind: str,
) -> tuple[tuple[float, float], ...]:
    if kind == "rectangle":
        starts = _nodes(source, primitive, "start")
        ends = _nodes(source, primitive, "end")
        if len(starts) != 1 or len(ends) != 1:
            raise ValueError("symbol rectangle needs one start and end point")
        start = _atoms(source, starts[0])
        end = _atoms(source, ends[0])
        if len(start) != 3 or len(end) != 3:
            raise ValueError("symbol rectangle has malformed coordinates")
        x0, y0 = _number(start[1], "symbol x coordinate"), _number(start[2], "symbol y coordinate")
        x1, y1 = _number(end[1], "symbol x coordinate"), _number(end[2], "symbol y coordinate")
        return ((x0, y0), (x0, y1), (x1, y0), (x1, y1))
    if kind in {"polyline", "bezier"}:
        points_sections = _nodes(source, primitive, "pts")
        if len(points_sections) != 1:
            raise ValueError(f"symbol {kind} needs one point list")
        points = _nodes(source, points_sections[0], "xy")
        coordinates: list[tuple[float, float]] = []
        for point in points:
            atoms = _atoms(source, point)
            if len(atoms) != 3:
                raise ValueError(f"symbol {kind} has malformed coordinates")
            coordinates.append(
                (
                    _number(atoms[1], "symbol x coordinate"),
                    _number(atoms[2], "symbol y coordinate"),
                )
            )
        if len(coordinates) < (4 if kind == "bezier" else 2):
            raise ValueError(f"symbol {kind} has too few points")
        return tuple(coordinates)
    if kind == "circle":
        centers = _nodes(source, primitive, "center")
        radii = _nodes(source, primitive, "radius")
        if len(centers) != 1 or len(radii) != 1:
            raise ValueError("symbol circle needs one center and radius")
        center = _atoms(source, centers[0])
        radius_atoms = _atoms(source, radii[0])
        if len(center) != 3 or len(radius_atoms) != 2:
            raise ValueError("symbol circle has malformed geometry")
        x = _number(center[1], "symbol x coordinate")
        y = _number(center[2], "symbol y coordinate")
        radius = _number(radius_atoms[1], "symbol radius")
        if radius <= 0.0:
            raise ValueError("symbol circle radius must be positive")
        return (
            (x - radius, y - radius),
            (x - radius, y + radius),
            (x + radius, y - radius),
            (x + radius, y + radius),
        )
    raise ValueError(f"symbol body primitive {kind!r} is outside the measured geometry")


def _symbol_body_envelope_for_instance(
    source: str,
    placed: _Span,
    libraries: dict[str, _Span],
    *,
    reference_override: str | None = None,
) -> tuple[_SymbolBodyEnvelope | None, str | None]:
    symbol_uuids = _nodes(source, placed, "uuid")
    if len(symbol_uuids) != 1:
        return None, "symbol body has no unique instance UUID"
    uuid_atoms = _atoms(source, symbol_uuids[0])
    if len(uuid_atoms) != 2 or not uuid_atoms[1]:
        return None, "symbol body has a malformed instance UUID"
    symbol_uuid = uuid_atoms[1]
    reference = (
        reference_override
        if reference_override is not None
        else _property(source, placed, "Reference")
    )
    if not reference or reference.startswith("#"):
        return None, None
    library_id = _scalar(source, placed, "lib_id")
    library = libraries.get(library_id)
    if library is None:
        return None, f"embedded symbol unavailable for body geometry on {reference}"
    unit_text = _scalar(source, placed, "unit")
    if not unit_text.isdecimal() or int(unit_text) != 1:
        return None, f"multi-unit symbol body is outside this prototype: {reference}"
    position = _at(source, placed, angle_required=True)
    if position[2] not in {0.0, 90.0, 180.0, 270.0}:
        return None, f"non-orthogonal symbol body rotation on {reference}"
    mirrors = _nodes(source, placed, "mirror")
    if len(mirrors) > 1:
        return None, f"ambiguous symbol body mirror state on {reference}"
    mirror: str | None = None
    if mirrors:
        mirror_atoms = _atoms(source, mirrors[0])
        if len(mirror_atoms) != 2 or mirror_atoms[1] not in {"x", "y"}:
            return None, f"unsupported symbol body mirror state on {reference}"
        mirror = mirror_atoms[1]

    parsed_subsymbols: list[tuple[int, int, _Span]] = []
    for subsymbol in _nodes(source, library, "symbol"):
        atoms = _atoms(source, subsymbol)
        suffix = _SUBSYMBOL_UNIT.search(atoms[1]) if len(atoms) == 2 else None
        if suffix is None:
            return None, f"unrecognized embedded symbol body unit on {reference}"
        parsed_subsymbols.append((int(suffix[1]), int(suffix[2]), subsymbol))
    unit_numbers = {unit for unit, _, _ in parsed_subsymbols if unit > 0}
    if unit_numbers != {1} or any(conversion != 1 for _, conversion, _ in parsed_subsymbols):
        return (
            None,
            f"multi-unit or multi-conversion symbol body is outside this prototype: {reference}",
        )

    local_points: list[tuple[float, float]] = []
    saw_primitive = False
    supported = {"rectangle", "polyline", "bezier", "circle"}
    for unit, _, subsymbol in parsed_subsymbols:
        if unit not in {0, 1}:
            continue
        for child in _children(source, subsymbol.start + 1, subsymbol.end - 1):
            atoms = _atoms(source, child)
            if not atoms:
                continue
            kind = atoms[0]
            if kind == "pin":
                continue
            if kind not in supported:
                return None, f"symbol body primitive {kind!r} is unsupported on {reference}"
            saw_primitive = True
            try:
                local_points.extend(_body_primitive_points(source, child, kind))
            except ValueError as exc:
                return None, f"symbol body geometry is unsupported on {reference}: {exc}"
    if not saw_primitive or not local_points:
        return None, None

    points = tuple(
        _transform_point(point, position[:2], position[2], mirror) for point in local_points
    )
    x_values = tuple(point[0] for point in points)
    y_values = tuple(point[1] for point in points)
    box = (min(x_values), min(y_values), max(x_values), max(y_values))
    if box[0] >= box[2] or box[1] >= box[3]:
        return None, f"symbol body has no two-dimensional envelope on {reference}"
    return _SymbolBodyEnvelope(reference, library_id, symbol_uuid, box), None


def _wire_geometry(
    source: str, root: _Span
) -> tuple[tuple[_WireEnd, ...], tuple[_WireSegment, ...], tuple[str, ...]]:
    ends: list[_WireEnd] = []
    segments: list[_WireSegment] = []
    unsupported: list[str] = []
    for wire in _nodes(source, root, "wire"):
        uuids = _nodes(source, wire, "uuid")
        points_sections = _nodes(source, wire, "pts")
        if len(uuids) != 1 or len(points_sections) != 1:
            unsupported.append("wire without a unique UUID or point list")
            continue
        uuid_atoms = _atoms(source, uuids[0])
        if len(uuid_atoms) != 2:
            unsupported.append("wire with malformed UUID")
            continue
        coords: list[tuple[float, float]] = []
        for point in _nodes(source, points_sections[0], "xy"):
            atoms = _atoms(source, point)
            if len(atoms) != 3:
                unsupported.append(f"wire {uuid_atoms[1]} has malformed coordinate")
                coords = []
                break
            coords.append(
                (_number(atoms[1], "wire x coordinate"), _number(atoms[2], "wire y coordinate"))
            )
        if len(coords) < 2:
            unsupported.append(f"wire {uuid_atoms[1]} has fewer than two points")
            continue
        ends.extend(
            (
                _WireEnd(uuid=uuid_atoms[1], point=coords[0]),
                _WireEnd(uuid=uuid_atoms[1], point=coords[-1]),
            )
        )
        segments.extend(
            _WireSegment(uuid=uuid_atoms[1], start=start, end=end)
            for start, end in pairwise(coords)
        )
    return tuple(ends), tuple(segments), tuple(unsupported)


def _no_connect_points(source: str, root: _Span) -> tuple[tuple[float, float], ...]:
    points: list[tuple[float, float]] = []
    for node in _nodes(source, root, "no_connect"):
        x, y, _ = _at(source, node, angle_required=False)
        points.append((x, y))
    return tuple(points)


def _junction_points(
    source: str, root: _Span
) -> tuple[tuple[tuple[float, float], ...], tuple[str, ...]]:
    points: list[tuple[float, float]] = []
    unsupported: list[str] = []
    for node in _nodes(source, root, "junction"):
        uuids = _nodes(source, node, "uuid")
        try:
            x, y, _angle = _at(source, node, angle_required=False)
        except ValueError as exc:
            identity = _atoms(source, uuids[0])[-1] if len(uuids) == 1 else "unknown"
            unsupported.append(f"junction {identity} has invalid location: {exc}")
            continue
        points.append((x, y))
    return tuple(points), tuple(unsupported)


def _strictly_inside(value: float, start: float, end: float) -> bool:
    lower, upper = sorted((start, end))
    return value - lower > POINT_TOLERANCE_MM and upper - value > POINT_TOLERANCE_MM


def _unmarked_orthogonal_crossings(
    segments: tuple[_WireSegment, ...], junctions: tuple[tuple[float, float], ...]
) -> tuple[UnmarkedWireCrossing, ...]:
    wires_by_point: dict[tuple[float, float], set[str]] = {}
    for index, first in enumerate(segments):
        first_horizontal = abs(first.start[1] - first.end[1]) <= POINT_TOLERANCE_MM
        first_vertical = abs(first.start[0] - first.end[0]) <= POINT_TOLERANCE_MM
        if first_horizontal == first_vertical:
            continue
        for second in segments[index + 1 :]:
            if first.uuid == second.uuid:
                continue
            second_horizontal = abs(second.start[1] - second.end[1]) <= POINT_TOLERANCE_MM
            second_vertical = abs(second.start[0] - second.end[0]) <= POINT_TOLERANCE_MM
            if first_horizontal and second_vertical:
                horizontal, vertical = first, second
            elif first_vertical and second_horizontal:
                horizontal, vertical = second, first
            else:
                continue
            x = (vertical.start[0] + vertical.end[0]) / 2
            y = (horizontal.start[1] + horizontal.end[1]) / 2
            if (
                abs(vertical.start[0] - vertical.end[0]) > POINT_TOLERANCE_MM
                or abs(horizontal.start[1] - horizontal.end[1]) > POINT_TOLERANCE_MM
                or not _strictly_inside(x, horizontal.start[0], horizontal.end[0])
                or not _strictly_inside(y, vertical.start[1], vertical.end[1])
                or any(math.dist((x, y), marker) <= POINT_TOLERANCE_MM for marker in junctions)
            ):
                continue
            point = (round(x, 6), round(y, 6))
            wires_by_point.setdefault(point, set()).update((first.uuid, second.uuid))
    return tuple(
        UnmarkedWireCrossing(wire_uuids=tuple(sorted(uuids)), crossing_mm=point)
        for point, uuids in sorted(wires_by_point.items())
    )


def _unmarked_t_junctions(
    wire_ends: tuple[_WireEnd, ...],
    segments: tuple[_WireSegment, ...],
    junctions: tuple[tuple[float, float], ...],
) -> tuple[UnmarkedTJunction, ...]:
    findings: dict[tuple[str, str, tuple[float, float]], UnmarkedTJunction] = {}
    for endpoint in wire_ends:
        for segment in segments:
            if endpoint.uuid == segment.uuid:
                continue
            measurement = _point_to_segment(endpoint.point, segment.start, segment.end)
            if measurement is None:
                continue
            distance, along, length = measurement
            if (
                distance > POINT_TOLERANCE_MM
                or along <= POINT_TOLERANCE_MM
                or length - along <= POINT_TOLERANCE_MM
                or any(
                    math.dist(endpoint.point, marker) <= POINT_TOLERANCE_MM for marker in junctions
                )
            ):
                continue
            point = (round(endpoint.point[0], 6), round(endpoint.point[1], 6))
            key = (endpoint.uuid, segment.uuid, point)
            findings[key] = UnmarkedTJunction(
                endpoint_wire_uuid=endpoint.uuid,
                interior_wire_uuid=segment.uuid,
                junction_mm=point,
            )
    return tuple(
        findings[key] for key in sorted(findings, key=lambda item: (item[2], item[0], item[1]))
    )


def _label_anchors(source: str, root: _Span) -> tuple[tuple[_LabelAnchor, ...], tuple[str, ...]]:
    labels: list[_LabelAnchor] = []
    unsupported: list[str] = []
    for kind in _LABEL_KINDS:
        for node in _nodes(source, root, kind):
            atoms = _atoms(source, node)
            uuids = _nodes(source, node, "uuid")
            if len(atoms) < 2 or len(uuids) != 1:
                unsupported.append(f"{kind} without a name or unique UUID")
                continue
            uuid_atoms = _atoms(source, uuids[0])
            if len(uuid_atoms) != 2 or not uuid_atoms[1]:
                unsupported.append(f"{kind} with malformed UUID")
                continue
            try:
                x, y, _angle = _at(source, node, angle_required=True)
            except ValueError as exc:
                unsupported.append(f"{kind} {uuid_atoms[1]} has invalid anchor: {exc}")
                continue
            labels.append(
                _LabelAnchor(
                    kind=kind,
                    text=atoms[1],
                    uuid=uuid_atoms[1],
                    point=(x, y),
                )
            )
    return tuple(labels), tuple(unsupported)


def _labels_near_wire_endpoints(
    labels: tuple[_LabelAnchor, ...],
    pins: list[_Pin],
    wire_ends: tuple[_WireEnd, ...],
    wire_segments: tuple[_WireSegment, ...],
) -> tuple[LabelNearWireEndpoint, ...]:
    findings: list[LabelNearWireEndpoint] = []
    for label in labels:
        if any(
            (measurement := _point_to_segment(label.point, segment.start, segment.end)) is not None
            and measurement[0] <= POINT_TOLERANCE_MM
            for segment in wire_segments
        ) or any(math.dist(label.point, pin.tip) <= POINT_TOLERANCE_MM for pin in pins):
            continue

        candidates = tuple(
            sorted(
                {
                    (wire_end.uuid, wire_end.point): LabelWireEndpointCandidate(
                        wire_uuid=wire_end.uuid,
                        wire_endpoint_mm=wire_end.point,
                        distance_mm=round(distance, 6),
                    )
                    for wire_end in wire_ends
                    if POINT_TOLERANCE_MM
                    < (distance := math.dist(label.point, wire_end.point))
                    <= MAX_LABEL_ENDPOINT_GAP_MM + DISTANCE_COMPARISON_EPSILON_MM
                }.values(),
                key=lambda item: (
                    item.distance_mm,
                    item.wire_uuid,
                    item.wire_endpoint_mm,
                ),
            )
        )
        if candidates:
            findings.append(
                LabelNearWireEndpoint(
                    label_kind=label.kind,
                    text=label.text,
                    label_uuid=label.uuid,
                    anchor_mm=label.point,
                    candidates=candidates,
                )
            )
    return tuple(sorted(findings, key=lambda item: (item.label_kind, item.label_uuid)))


def _coincident_text_anchors(
    source: str,
    root: _Span,
) -> tuple[tuple[CoincidentTextAnchors, ...], tuple[str, ...]]:
    """Report free-text objects whose insertion anchors coincide within tolerance.

    This intentionally does not estimate rendered glyph bounds. The result is a
    review prompt about coincident source anchors, not a claim that text overlaps
    or that either placement is unintended.
    """
    anchors: list[_TextAnchor] = []
    unsupported: list[str] = []
    for node in _nodes(source, root, "text"):
        atoms = _atoms(source, node)
        uuids = _nodes(source, node, "uuid")
        if len(atoms) < 2 or not atoms[1].strip() or len(uuids) != 1:
            unsupported.append("free text without non-empty content or one unique UUID")
            continue
        uuid_atoms = _atoms(source, uuids[0])
        if len(uuid_atoms) != 2 or not uuid_atoms[1]:
            unsupported.append("free text with malformed UUID")
            continue
        try:
            x, y, _angle = _at(source, node, angle_required=True)
        except ValueError as exc:
            unsupported.append(f"free text {uuid_atoms[1]} has invalid anchor: {exc}")
            continue
        anchors.append(_TextAnchor(atoms[1], uuid_atoms[1], (x, y)))

    uuid_counts: dict[str, int] = {}
    for anchor in anchors:
        uuid_counts[anchor.uuid] = uuid_counts.get(anchor.uuid, 0) + 1
    duplicate_uuids = {uuid for uuid, count in uuid_counts.items() if count > 1}
    unsupported.extend(f"duplicate free-text UUID: {uuid}" for uuid in sorted(duplicate_uuids))
    anchors = [anchor for anchor in anchors if anchor.uuid not in duplicate_uuids]
    anchors.sort(key=lambda item: (item.point, item.uuid, item.text))

    findings: list[CoincidentTextAnchors] = []
    for index, first in enumerate(anchors):
        for second in anchors[index + 1 :]:
            if second.point[0] - first.point[0] > POINT_TOLERANCE_MM:
                break
            if math.dist(first.point, second.point) <= POINT_TOLERANCE_MM:
                findings.append(
                    CoincidentTextAnchors(
                        first_text=first.text,
                        first_uuid=first.uuid,
                        second_text=second.text,
                        second_uuid=second.uuid,
                        anchor_mm=first.point,
                    )
                )
    findings.sort(key=lambda item: (item.anchor_mm, item.first_uuid, item.second_uuid))
    return tuple(findings), tuple(unsupported)


@lru_cache(maxsize=1)
def _schematic_text_metrics() -> _SchematicTextMetrics:
    """Read bounded KiCad 10.0.6 standard-stroke metrics measured from native SVG."""
    content = (
        files("kicad_tooling.hwrepo")
        .joinpath("schematic-text-metrics.json")
        .read_text(encoding="utf-8")
    )
    document = parse_model_text(content, SchematicTextMetricsResource)
    top_ratio, bottom_ratio = document.vertical_ink_envelope_ratio
    return _SchematicTextMetrics(
        advances_mm=dict(document.advances_mm),
        reference_size_mm=document.reference_size_mm,
        single_glyph_end_spacing_mm=document.single_glyph_svg_end_spacing_mm,
        line_end_spacing_mm=document.line_end_spacing_mm,
        multiline_line_spacing_mm=document.multiline_line_spacing_mm,
        vertical_top_ratio=top_ratio,
        vertical_bottom_ratio=bottom_ratio,
        stroke_width_mm=document.stroke_width_mm,
    )


def _all_rules_unsupported(issues: tuple[str, ...]) -> dict[str, tuple[str, ...]]:
    return {rule_id: issues for rule_id in _SCHEMATIC_GEOMETRY_RULE_IDS}


def _free_text_lines(source: str, node: _Span) -> tuple[str, ...]:
    """Decode KiCad's escaped plain-text line breaks without confusing ``\\n``."""
    position = node.start + 1
    while position < node.end - 1 and source[position].isspace():
        position += 1
    token_start = position
    while (
        position < node.end - 1 and not source[position].isspace() and source[position] not in "()"
    ):
        position += 1
    if source[token_start:position] != "text":
        raise ValueError("free-text object has an unsupported content node")
    while position < node.end - 1 and source[position].isspace():
        position += 1
    if position >= node.end - 1 or source[position] != '"':
        raise ValueError("free text content is not one quoted string")

    position += 1
    lines: list[list[str]] = [[]]
    closed = False
    while position < node.end - 1:
        character = source[position]
        if character == '"':
            closed = True
            break
        if character in "\r\n":
            raise ValueError("literal source line breaks inside free text are unsupported")
        if character == "\\":
            if position + 1 >= node.end - 1:
                raise ValueError("free text ends with an incomplete escape")
            escaped = source[position + 1]
            if escaped == "n":
                lines.append([])
            elif escaped in {"\\", '"'}:
                lines[-1].append(escaped)
            elif escaped == "r":
                raise ValueError("carriage-return escapes in free text are unsupported")
            else:
                lines[-1].extend(("\\", escaped))
            position += 2
            continue
        lines[-1].append(character)
        position += 1

    if not closed:
        raise ValueError("free text has an unterminated quoted string")
    decoded = tuple("".join(line) for line in lines)
    if not any(line.strip() for line in decoded):
        raise ValueError("free text needs at least one non-empty line")
    return decoded


def _free_text_box_mm(
    source: str,
    node: _Span,
    metrics: _SchematicTextMetrics,
) -> tuple[_TextAnchor, tuple[float, float, float, float]]:
    atoms = _atoms(source, node)
    uuids = _nodes(source, node, "uuid")
    if len(atoms) < 2 or not atoms[1].strip() or len(uuids) != 1:
        raise ValueError("free text needs non-empty content and one unique UUID")
    uuid_atoms = _atoms(source, uuids[0])
    if len(uuid_atoms) != 2 or not uuid_atoms[1]:
        raise ValueError("free text has a malformed UUID")
    text_lines = _free_text_lines(source, node)
    text_value = "\n".join(text_lines)
    if _TEXT_MARKUP.search(text_value):
        raise ValueError("formatted free text is outside the measured geometry")
    if any(character not in metrics.advances_mm for line in text_lines for character in line):
        raise ValueError("free text contains glyphs outside the measured standard-stroke set")

    x, y, angle = _at(source, node, angle_required=True)
    if angle != 0.0:
        raise ValueError("free-text rotation must be horizontal")
    effects = _nodes(source, node, "effects")
    if len(effects) != 1:
        raise ValueError("free text must have one effects section")
    fonts = _nodes(source, effects[0], "font")
    if len(fonts) != 1:
        raise ValueError("free text must use one standard font section")
    font = fonts[0]
    if any(_nodes(source, font, name) for name in ("face", "bold", "italic", "thickness")):
        raise ValueError("custom, bold, italic, or thick free text is outside the measured font")
    sizes = _nodes(source, font, "size")
    if len(sizes) != 1:
        raise ValueError("free text must have one explicit font size")
    size_atoms = _atoms(source, sizes[0])
    if len(size_atoms) != 3:
        raise ValueError("free-text font size must contain width and height")
    size_width = _number(size_atoms[1], "free-text width")
    size_height = _number(size_atoms[2], "free-text height")
    if size_width <= 0.0 or size_height <= 0.0:
        raise ValueError("free-text font size must be positive")

    justify_nodes = _nodes(source, effects[0], "justify")
    horizontal_justification = "center"
    if justify_nodes:
        if len(justify_nodes) != 1:
            raise ValueError("free text must have at most one justification field")
        justification_atoms = _atoms(source, justify_nodes[0])
        options = justification_atoms[1:]
        if options == ():
            horizontal_justification = "center"
        elif options == ("left",):
            horizontal_justification = "left"
        elif options == ("right",):
            horizontal_justification = "right"
        else:
            raise ValueError(
                "free-text justification must be horizontal left or right; "
                "vertical alignment and mirrored text are outside the measured geometry"
            )

    scale_x = size_width / metrics.reference_size_mm
    scale_y = size_height / metrics.reference_size_mm
    line_widths = tuple(
        (
            sum(metrics.advances_mm[character] for character in line)
            + (
                metrics.single_glyph_end_spacing_mm
                if len(line) == 1
                else metrics.line_end_spacing_mm
            )
        )
        * scale_x
        if line
        else 0.0
        for line in text_lines
    )
    width = max(line_widths)
    stroke = metrics.stroke_width_mm * scale_y
    if horizontal_justification == "left":
        left, right = 0.0, width
    elif horizontal_justification == "right":
        left, right = -width, 0.0
    else:
        left, right = -width / 2.0, width / 2.0
    line_spacing = metrics.multiline_line_spacing_mm * scale_y
    row_offsets = tuple(
        (index - (len(text_lines) - 1) / 2.0) * line_spacing for index in range(len(text_lines))
    )
    top = min(row_offsets) + metrics.vertical_top_ratio * size_height - stroke / 2.0
    bottom = max(row_offsets) + metrics.vertical_bottom_ratio * size_height + stroke / 2.0
    box = (round(x + left, 6), round(y + top, 6), round(x + right, 6), round(y + bottom, 6))
    return _TextAnchor(text_value, uuid_atoms[1], (x, y)), box


def _free_text_overlaps(
    source: str,
    root: _Span,
) -> tuple[tuple[FreeTextOverlap, ...], tuple[str, ...]]:
    """Find likely text-envelope collisions using the pinned standard-stroke metrics."""
    metrics = _schematic_text_metrics()
    geometries: list[_FreeTextGeometry] = []
    unsupported: list[str] = []
    for node in _nodes(source, root, "text"):
        try:
            anchor, box = _free_text_box_mm(source, node, metrics)
        except ValueError as exc:
            unsupported.append(f"Free-text overlap geometry is unsupported: {exc}")
            continue
        geometries.append(_FreeTextGeometry(anchor, box))

    uuid_counts: dict[str, int] = {}
    for geometry in geometries:
        uuid_counts[geometry.anchor.uuid] = uuid_counts.get(geometry.anchor.uuid, 0) + 1
    duplicate_uuids = {uuid for uuid, count in uuid_counts.items() if count > 1}
    unsupported.extend(f"Duplicate free-text UUID: {uuid}" for uuid in sorted(duplicate_uuids))
    geometries = [
        geometry for geometry in geometries if geometry.anchor.uuid not in duplicate_uuids
    ]
    geometries.sort(
        key=lambda item: (item.box_mm[0], item.box_mm[1], item.anchor.uuid, item.anchor.text)
    )

    findings: list[FreeTextOverlap] = []
    for index, first in enumerate(geometries):
        first_box = first.box_mm
        first_interior = (
            first_box[0] + _TEXT_OVERLAP_GUARD_MM,
            first_box[1] + _TEXT_OVERLAP_GUARD_MM,
            first_box[2] - _TEXT_OVERLAP_GUARD_MM,
            first_box[3] - _TEXT_OVERLAP_GUARD_MM,
        )
        if first_interior[0] >= first_interior[2] or first_interior[1] >= first_interior[3]:
            continue
        for second in geometries[index + 1 :]:
            second_box = second.box_mm
            second_interior = (
                second_box[0] + _TEXT_OVERLAP_GUARD_MM,
                second_box[1] + _TEXT_OVERLAP_GUARD_MM,
                second_box[2] - _TEXT_OVERLAP_GUARD_MM,
                second_box[3] - _TEXT_OVERLAP_GUARD_MM,
            )
            if second_interior[0] >= first_interior[2]:
                break
            if (
                first.anchor.uuid == second.anchor.uuid
                or math.dist(first.anchor.point, second.anchor.point) <= POINT_TOLERANCE_MM
                or second_interior[1] >= first_interior[3]
                or first_interior[1] >= second_interior[3]
            ):
                continue
            overlap = (
                max(first_interior[0], second_interior[0]),
                max(first_interior[1], second_interior[1]),
                min(first_interior[2], second_interior[2]),
                min(first_interior[3], second_interior[3]),
            )
            if (overlap[2] - overlap[0]) * (overlap[3] - overlap[1]) < (_TEXT_OVERLAP_MIN_AREA_MM2):
                continue
            findings.append(
                FreeTextOverlap(
                    first_text=first.anchor.text,
                    first_uuid=first.anchor.uuid,
                    first_box_mm=first.box_mm,
                    second_text=second.anchor.text,
                    second_uuid=second.anchor.uuid,
                    second_box_mm=second.box_mm,
                    overlap_box_mm=(
                        round(overlap[0], 6),
                        round(overlap[1], 6),
                        round(overlap[2], 6),
                        round(overlap[3], 6),
                    ),
                )
            )
    findings.sort(key=lambda item: (item.overlap_box_mm, item.first_uuid, item.second_uuid))
    return tuple(findings), tuple(sorted(set(unsupported)))


def _clip_segment_to_box(
    start: tuple[float, float],
    end: tuple[float, float],
    box: tuple[float, float, float, float],
) -> tuple[tuple[float, float], tuple[float, float], float] | None:
    """Clip one straight segment to an axis-aligned rectangle using Liang-Barsky."""
    x0, y0, x1, y1 = box
    dx, dy = end[0] - start[0], end[1] - start[1]
    lower, upper = 0.0, 1.0
    for denominator, numerator in (
        (-dx, start[0] - x0),
        (dx, x1 - start[0]),
        (-dy, start[1] - y0),
        (dy, y1 - start[1]),
    ):
        if denominator == 0.0:
            if numerator < 0.0:
                return None
            continue
        ratio = numerator / denominator
        if denominator < 0.0:
            if ratio > upper:
                return None
            lower = max(lower, ratio)
        else:
            if ratio < lower:
                return None
            upper = min(upper, ratio)
    clipped_start = (start[0] + lower * dx, start[1] + lower * dy)
    clipped_end = (start[0] + upper * dx, start[1] + upper * dy)
    return clipped_start, clipped_end, math.dist(clipped_start, clipped_end)


def _wire_through_symbol_bodies(
    bodies: tuple[_SymbolBodyEnvelope, ...],
    wire_segments: tuple[_WireSegment, ...],
    *,
    sheet_instance_path: str,
) -> tuple[WireThroughSymbolBody, ...]:
    """Find wire centerlines with substantial overlap inside a guarded body box."""
    findings: list[WireThroughSymbolBody] = []
    for body in bodies:
        x0, y0, x1, y1 = body.box_mm
        guarded_box = (
            x0 + _SYMBOL_BODY_WIRE_GUARD_MM,
            y0 + _SYMBOL_BODY_WIRE_GUARD_MM,
            x1 - _SYMBOL_BODY_WIRE_GUARD_MM,
            y1 - _SYMBOL_BODY_WIRE_GUARD_MM,
        )
        if guarded_box[0] >= guarded_box[2] or guarded_box[1] >= guarded_box[3]:
            continue
        for segment in wire_segments:
            clipped = _clip_segment_to_box(segment.start, segment.end, guarded_box)
            if clipped is None:
                continue
            start, end, length = clipped
            if length + _SYMBOL_BODY_WIRE_LENGTH_EPSILON_MM < (_SYMBOL_BODY_WIRE_MIN_OVERLAP_MM):
                continue
            findings.append(
                WireThroughSymbolBody(
                    reference=body.reference,
                    symbol_library_id=body.library_id,
                    symbol_uuid=body.symbol_uuid,
                    wire_uuid=segment.uuid,
                    body_box_mm=body.box_mm,
                    overlap_start_mm=(round(start[0], 6), round(start[1], 6)),
                    overlap_end_mm=(round(end[0], 6), round(end[1], 6)),
                    overlap_length_mm=round(length, 6),
                    sheet_instance_path=sheet_instance_path,
                )
            )
    findings.sort(
        key=lambda item: (
            item.sheet_instance_path,
            item.reference,
            item.symbol_uuid,
            item.wire_uuid,
            item.overlap_start_mm,
        )
    )
    return tuple(findings)


def _free_text_wire_overlaps(
    source: str,
    root: _Span,
    wire_segments: tuple[_WireSegment, ...],
    *,
    sheet_instance_path: str,
) -> tuple[tuple[FreeTextWireOverlap, ...], tuple[str, ...]]:
    """Find wire centerlines that cross a guarded standard free-text envelope."""
    metrics = _schematic_text_metrics()
    geometries: list[_FreeTextGeometry] = []
    unsupported: list[str] = []
    for node in _nodes(source, root, "text"):
        try:
            anchor, box = _free_text_box_mm(source, node, metrics)
        except ValueError as exc:
            unsupported.append(f"Free-text wire-overlap geometry is unsupported: {exc}")
            continue
        geometries.append(_FreeTextGeometry(anchor, box))

    uuid_counts: dict[str, int] = {}
    for geometry in geometries:
        uuid_counts[geometry.anchor.uuid] = uuid_counts.get(geometry.anchor.uuid, 0) + 1
    duplicate_uuids = {uuid for uuid, count in uuid_counts.items() if count > 1}
    unsupported.extend(f"Duplicate free-text UUID: {uuid}" for uuid in sorted(duplicate_uuids))
    geometries = [
        geometry for geometry in geometries if geometry.anchor.uuid not in duplicate_uuids
    ]

    findings: list[FreeTextWireOverlap] = []
    for geometry in geometries:
        x0, y0, x1, y1 = geometry.box_mm
        guarded_box = (
            x0 + _TEXT_WIRE_GUARD_MM,
            y0 + _TEXT_WIRE_GUARD_MM,
            x1 - _TEXT_WIRE_GUARD_MM,
            y1 - _TEXT_WIRE_GUARD_MM,
        )
        if guarded_box[0] >= guarded_box[2] or guarded_box[1] >= guarded_box[3]:
            continue
        for segment in wire_segments:
            clipped = _clip_segment_to_box(segment.start, segment.end, guarded_box)
            if clipped is None:
                continue
            clipped_start, clipped_end, overlap_length = clipped
            if overlap_length + _TEXT_WIRE_LENGTH_EPSILON_MM < _TEXT_WIRE_MIN_OVERLAP_MM:
                continue
            findings.append(
                FreeTextWireOverlap(
                    text=geometry.anchor.text,
                    text_uuid=geometry.anchor.uuid,
                    text_box_mm=geometry.box_mm,
                    wire_uuid=segment.uuid,
                    wire_segment_start_mm=(
                        round(clipped_start[0], 6),
                        round(clipped_start[1], 6),
                    ),
                    wire_segment_end_mm=(round(clipped_end[0], 6), round(clipped_end[1], 6)),
                    overlap_length_mm=round(overlap_length, 6),
                    sheet_instance_path=sheet_instance_path,
                )
            )
    findings.sort(
        key=lambda item: (
            item.sheet_instance_path,
            item.text_uuid,
            item.wire_uuid,
            item.wire_segment_start_mm,
            item.wire_segment_end_mm,
        )
    )
    return tuple(findings), tuple(sorted(set(unsupported)))


def _free_text_over_symbol_bodies(
    source: str,
    root: _Span,
    bodies: tuple[_SymbolBodyEnvelope, ...],
    *,
    sheet_instance_path: str,
) -> tuple[tuple[FreeTextSymbolBodyOverlap, ...], tuple[str, ...]]:
    """Find supported top-level free-text envelopes inside symbol-body bounds."""
    metrics = _schematic_text_metrics()
    geometries: list[_FreeTextGeometry] = []
    unsupported: list[str] = []
    for node in _nodes(source, root, "text"):
        try:
            anchor, box = _free_text_box_mm(source, node, metrics)
        except ValueError as exc:
            unsupported.append(f"Free-text body-overlap geometry is unsupported: {exc}")
            continue
        geometries.append(_FreeTextGeometry(anchor, box))

    uuid_counts: dict[str, int] = {}
    for geometry in geometries:
        uuid_counts[geometry.anchor.uuid] = uuid_counts.get(geometry.anchor.uuid, 0) + 1
    duplicate_uuids = {uuid for uuid, count in uuid_counts.items() if count > 1}
    unsupported.extend(f"Duplicate free-text UUID: {uuid}" for uuid in sorted(duplicate_uuids))
    geometries = [
        geometry for geometry in geometries if geometry.anchor.uuid not in duplicate_uuids
    ]

    findings: list[FreeTextSymbolBodyOverlap] = []
    for geometry in geometries:
        x0, y0, x1, y1 = geometry.box_mm
        text_box = (
            x0 + _TEXT_BODY_TEXT_GUARD_MM,
            y0 + _TEXT_BODY_TEXT_GUARD_MM,
            x1 - _TEXT_BODY_TEXT_GUARD_MM,
            y1 - _TEXT_BODY_TEXT_GUARD_MM,
        )
        if text_box[0] >= text_box[2] or text_box[1] >= text_box[3]:
            continue
        for body in bodies:
            bx0, by0, bx1, by1 = body.box_mm
            body_box = (
                bx0 + _TEXT_BODY_SYMBOL_GUARD_MM,
                by0 + _TEXT_BODY_SYMBOL_GUARD_MM,
                bx1 - _TEXT_BODY_SYMBOL_GUARD_MM,
                by1 - _TEXT_BODY_SYMBOL_GUARD_MM,
            )
            if body_box[0] >= body_box[2] or body_box[1] >= body_box[3]:
                continue
            overlap = (
                max(text_box[0], body_box[0]),
                max(text_box[1], body_box[1]),
                min(text_box[2], body_box[2]),
                min(text_box[3], body_box[3]),
            )
            if overlap[0] >= overlap[2] or overlap[1] >= overlap[3]:
                continue
            overlap_area = (overlap[2] - overlap[0]) * (overlap[3] - overlap[1])
            if overlap_area + _TEXT_BODY_AREA_EPSILON_MM2 < _TEXT_BODY_MIN_OVERLAP_AREA_MM2:
                continue
            findings.append(
                FreeTextSymbolBodyOverlap(
                    text=geometry.anchor.text,
                    text_uuid=geometry.anchor.uuid,
                    text_box_mm=geometry.box_mm,
                    reference=body.reference,
                    symbol_library_id=body.library_id,
                    symbol_uuid=body.symbol_uuid,
                    body_box_mm=body.box_mm,
                    overlap_box_mm=(
                        round(overlap[0], 6),
                        round(overlap[1], 6),
                        round(overlap[2], 6),
                        round(overlap[3], 6),
                    ),
                    overlap_area_mm2=round(overlap_area, 6),
                    sheet_instance_path=sheet_instance_path,
                )
            )
    findings.sort(
        key=lambda item: (
            item.sheet_instance_path,
            item.reference,
            item.symbol_uuid,
            item.text_uuid,
            item.overlap_box_mm,
        )
    )
    return tuple(findings), tuple(sorted(set(unsupported)))


def scan_unconnected_pin_wire_geometry(
    source: bytes,
    *,
    source_path: str,
    kicad_version: str,
    unconnected_pins: frozenset[str],
    sheet_instance_path: str = "/",
    reference_overrides: Mapping[str, str] | None = None,
    require_reference_overrides: bool = False,
    allow_hierarchical_sheets: bool = False,
) -> SchematicGeometryScan:
    """Find bounded wire/pin near misses using native-unconnected pin evidence.

    This is a prototype for a review hint. It requires the native netlist's
    explicit unconnected pin set. It identifies either a wire endpoint on the
    interior of a pin segment or a pin tip on the interior of a wire segment.
    It refuses unvalidated KiCad versions and schematic format versions.
    Hierarchical sheets are rejected unless a tree scanner has already bound
    and will scan every sheet instance.
    """
    sha256 = hashlib.sha256(source).hexdigest()
    binding = SchematicSourceBinding(
        source_path=source_path,
        source_sha256=sha256,
        sheet_instance_path=sheet_instance_path,
        sheet_path=(),
    )
    if kicad_version not in SUPPORTED_KICAD_VERSIONS:
        supported_versions = ", ".join(sorted(SUPPORTED_KICAD_VERSIONS))
        issue = f"This prototype is validated only with KiCad {supported_versions}"
        return SchematicGeometryScan(
            status="UNSUPPORTED",
            source_path=source_path,
            source_sha256=sha256,
            kicad_version=kicad_version,
            schematic_version=None,
            source_tree_sha256=_source_tree_sha256({source_path: sha256}),
            source_bindings=(binding,),
            unsupported=(issue,),
            unsupported_by_rule=_all_rules_unsupported((issue,)),
        )
    text, root = _schematic_root(source)
    versions = _nodes(text, root, "version")
    if len(versions) != 1 or len(_atoms(text, versions[0])) != 2:
        raise ValueError("Expected one KiCad schematic version")
    schematic_version = _atoms(text, versions[0])[1]
    if schematic_version != SUPPORTED_SCHEMATIC_VERSION:
        issue = f"Schematic format {schematic_version} is outside this prototype's tested format"
        return SchematicGeometryScan(
            status="UNSUPPORTED",
            source_path=source_path,
            source_sha256=sha256,
            kicad_version=kicad_version,
            schematic_version=schematic_version,
            source_tree_sha256=_source_tree_sha256({source_path: sha256}),
            source_bindings=(binding,),
            unsupported=(issue,),
            unsupported_by_rule=_all_rules_unsupported((issue,)),
        )
    if _nodes(text, root, "sheet") and not allow_hierarchical_sheets:
        issue = "Hierarchical sheets are outside this single-sheet prototype"
        return SchematicGeometryScan(
            status="UNSUPPORTED",
            source_path=source_path,
            source_sha256=sha256,
            kicad_version=kicad_version,
            schematic_version=schematic_version,
            source_tree_sha256=_source_tree_sha256({source_path: sha256}),
            source_bindings=(binding,),
            unsupported=(issue,),
            unsupported_by_rule=_all_rules_unsupported((issue,)),
        )

    libraries = _library_symbols(text, root)
    pins: list[_Pin] = []
    body_envelopes: list[_SymbolBodyEnvelope] = []
    unsupported: list[str] = []
    unsupported_by_rule: dict[str, list[str]] = {}

    def record_unsupported(issues: tuple[str, ...], rule_ids: tuple[str, ...]) -> None:
        if not issues:
            return
        unsupported.extend(issues)
        for rule_id in rule_ids:
            unsupported_by_rule.setdefault(rule_id, []).extend(issues)

    for placed in _nodes(text, root, "symbol"):
        symbol_uuids = _nodes(text, placed, "uuid")
        symbol_uuid = _atoms(text, symbol_uuids[0])[1] if len(symbol_uuids) == 1 else None
        if require_reference_overrides and (
            symbol_uuid is None
            or reference_overrides is None
            or symbol_uuid not in reference_overrides
        ):
            record_unsupported(
                (
                    f"No unique project-instance reference mapping for symbol {symbol_uuid or '<unknown>'}",
                ),
                (*_PIN_GEOMETRY_RULE_IDS, *_SYMBOL_BODY_RULE_IDS),
            )
            continue
        reference_override = (
            None
            if reference_overrides is None or symbol_uuid is None
            else reference_overrides.get(symbol_uuid)
        )
        instance_pins, issue = _pins_for_instance(
            text,
            placed,
            libraries,
            reference_override=reference_override,
        )
        pins.extend(instance_pins)
        if issue is not None:
            record_unsupported((issue,), _PIN_GEOMETRY_RULE_IDS)
        body_envelope, body_issue = _symbol_body_envelope_for_instance(
            text,
            placed,
            libraries,
            reference_override=reference_override,
        )
        if body_envelope is not None:
            body_envelopes.append(body_envelope)
        if body_issue is not None:
            record_unsupported((body_issue,), _SYMBOL_BODY_RULE_IDS)

    wire_ends, wire_segments, wire_issues = _wire_geometry(text, root)
    record_unsupported(wire_issues, _WIRE_GEOMETRY_RULE_IDS)
    body_wire_findings = _wire_through_symbol_bodies(
        tuple(body_envelopes),
        wire_segments,
        sheet_instance_path=sheet_instance_path,
    )
    text_body_findings, text_body_issues = _free_text_over_symbol_bodies(
        text,
        root,
        tuple(body_envelopes),
        sheet_instance_path=sheet_instance_path,
    )
    record_unsupported(text_body_issues, ("schematic.free_text_over_symbol_body",))
    junctions, junction_issues = _junction_points(text, root)
    record_unsupported(
        junction_issues,
        ("schematic.unmarked_wire_crossing", "schematic.unmarked_t_junction"),
    )
    label_anchors, label_issues = _label_anchors(text, root)
    record_unsupported(label_issues, ("schematic.label_near_wire_endpoint",))
    text_anchor_findings, text_anchor_issues = _coincident_text_anchors(text, root)
    record_unsupported(text_anchor_issues, ("schematic.coincident_text_anchors",))
    text_overlap_findings, text_overlap_issues = _free_text_overlaps(text, root)
    record_unsupported(text_overlap_issues, ("schematic.free_text_overlap",))
    text_wire_findings, text_wire_issues = _free_text_wire_overlaps(
        text,
        root,
        wire_segments,
        sheet_instance_path=sheet_instance_path,
    )
    record_unsupported(text_wire_issues, ("schematic.free_text_over_wire",))
    no_connects = _no_connect_points(text, root)
    findings: list[WireEndOnPinLine] = []
    interior_touches: list[PinTipOnWireInterior] = []
    near_tip_endpoints: list[WireEndpointNearPinTip] = []
    seen: set[tuple[str, str, str, tuple[float, float]]] = set()
    seen_intersections: set[tuple[str, str, str, tuple[float, float], tuple[float, float]]] = set()
    seen_near_tips: set[tuple[str, str, str, tuple[float, float]]] = set()
    for pin in pins:
        pin_key = f"{pin.reference}.{pin.number}"
        if pin_key not in unconnected_pins:
            continue
        if any(math.dist(pin.tip, marker) <= POINT_TOLERANCE_MM for marker in no_connects):
            continue
        for wire_end in wire_ends:
            distance_to_tip = math.dist(pin.tip, wire_end.point)
            if (
                POINT_TOLERANCE_MM
                < distance_to_tip
                <= MAX_PIN_ENDPOINT_GAP_MM + DISTANCE_COMPARISON_EPSILON_MM
            ):
                measurement = _point_to_segment(wire_end.point, pin.tip, pin.body_end)
                on_pin_segment = measurement is not None and measurement[0] <= POINT_TOLERANCE_MM
                if not on_pin_segment:
                    key = (wire_end.uuid, pin.reference, pin.number, wire_end.point)
                    if key not in seen_near_tips:
                        seen_near_tips.add(key)
                        near_tip_endpoints.append(
                            WireEndpointNearPinTip(
                                reference=pin.reference,
                                symbol_library_id=pin.library_id,
                                symbol_uuid=pin.symbol_uuid,
                                pin_number=pin.number,
                                pin_name=pin.name,
                                pin_uuid=pin.pin_uuid,
                                pin_tip_mm=pin.tip,
                                wire_uuid=wire_end.uuid,
                                wire_endpoint_mm=wire_end.point,
                                distance_to_pin_tip_mm=round(distance_to_tip, 6),
                                sheet_instance_path=sheet_instance_path,
                            )
                        )
            measurement = _point_to_segment(wire_end.point, pin.tip, pin.body_end)
            if measurement is None:
                continue
            distance, along, _length = measurement
            distance_to_tip = math.dist(wire_end.point, pin.tip)
            if distance > POINT_TOLERANCE_MM or distance_to_tip <= POINT_TOLERANCE_MM:
                continue
            key = (wire_end.uuid, pin.reference, pin.number, wire_end.point)
            if key in seen:
                continue
            seen.add(key)
            findings.append(
                WireEndOnPinLine(
                    reference=pin.reference,
                    symbol_library_id=pin.library_id,
                    symbol_uuid=pin.symbol_uuid,
                    pin_number=pin.number,
                    pin_name=pin.name,
                    pin_uuid=pin.pin_uuid,
                    pin_tip_mm=pin.tip,
                    pin_body_end_mm=pin.body_end,
                    wire_uuid=wire_end.uuid,
                    wire_endpoint_mm=wire_end.point,
                    distance_to_pin_tip_mm=round(distance_to_tip, 6),
                    distance_along_pin_mm=round(along, 6),
                    sheet_instance_path=sheet_instance_path,
                )
            )
        for segment in wire_segments:
            measurement = _point_to_segment(pin.tip, segment.start, segment.end)
            if measurement is None:
                continue
            distance, along, length = measurement
            if (
                distance > POINT_TOLERANCE_MM
                or along <= POINT_TOLERANCE_MM
                or length - along <= POINT_TOLERANCE_MM
            ):
                continue
            key = (
                segment.uuid,
                pin.reference,
                pin.number,
                segment.start,
                segment.end,
            )
            if key in seen_intersections:
                continue
            seen_intersections.add(key)
            interior_touches.append(
                PinTipOnWireInterior(
                    reference=pin.reference,
                    symbol_library_id=pin.library_id,
                    symbol_uuid=pin.symbol_uuid,
                    pin_number=pin.number,
                    pin_name=pin.name,
                    pin_uuid=pin.pin_uuid,
                    pin_tip_mm=pin.tip,
                    wire_uuid=segment.uuid,
                    wire_segment_start_mm=segment.start,
                    wire_segment_end_mm=segment.end,
                    distance_to_wire_mm=round(distance, 6),
                    sheet_instance_path=sheet_instance_path,
                )
            )
    findings.sort(key=lambda item: (item.reference, item.pin_number, item.wire_uuid))
    interior_touches.sort(key=lambda item: (item.reference, item.pin_number, item.wire_uuid))
    near_tip_endpoints.sort(
        key=lambda item: (
            item.reference,
            item.pin_number,
            item.distance_to_pin_tip_mm,
            item.wire_uuid,
        )
    )
    label_findings = tuple(
        replace(item, sheet_instance_path=sheet_instance_path)
        for item in _labels_near_wire_endpoints(label_anchors, pins, wire_ends, wire_segments)
    )
    unmarked_crossings = tuple(
        replace(item, sheet_instance_path=sheet_instance_path)
        for item in _unmarked_orthogonal_crossings(wire_segments, junctions)
    )
    unmarked_t_junctions = tuple(
        replace(item, sheet_instance_path=sheet_instance_path)
        for item in _unmarked_t_junctions(wire_ends, wire_segments, junctions)
    )
    coincident_text_anchors = tuple(
        replace(item, sheet_instance_path=sheet_instance_path) for item in text_anchor_findings
    )
    free_text_overlaps = tuple(
        replace(item, sheet_instance_path=sheet_instance_path) for item in text_overlap_findings
    )
    return SchematicGeometryScan(
        status="PARTIAL" if unsupported else "COMPLETE",
        source_path=source_path,
        source_sha256=sha256,
        kicad_version=kicad_version,
        schematic_version=schematic_version,
        source_tree_sha256=_source_tree_sha256({source_path: sha256}),
        source_bindings=(binding,),
        findings=tuple(findings),
        pin_tip_on_wire_interiors=tuple(interior_touches),
        wire_endpoints_near_pin_tips=tuple(near_tip_endpoints),
        labels_near_wire_endpoints=label_findings,
        unmarked_wire_crossings=unmarked_crossings,
        unmarked_t_junctions=unmarked_t_junctions,
        coincident_text_anchors=coincident_text_anchors,
        free_text_overlaps=free_text_overlaps,
        free_text_wire_overlaps=text_wire_findings,
        free_text_symbol_body_overlaps=text_body_findings,
        wires_through_symbol_bodies=body_wire_findings,
        unsupported=tuple(sorted(set(unsupported))),
        unsupported_by_rule={
            rule_id: tuple(sorted(set(issues)))
            for rule_id, issues in sorted(unsupported_by_rule.items())
        },
    )


def scan_schematic_geometry_tree(
    source_files: Mapping[str, bytes],
    *,
    root_path: str,
    project_directory: str,
    project_name: str,
    kicad_version: str,
    unconnected_pins: frozenset[str],
) -> SchematicGeometryScan:
    """Scan every project-local hierarchical sheet instance with exact path refs.

    The caller supplies only the source files it resolved and hash-checked
    against the native verification snapshot. Reused child files are scanned
    once per sheet-instance path so instance-specific component references
    remain distinct in findings.
    """
    if root_path not in source_files:
        raise ValueError(f"Root schematic is absent from the source map: {root_path}")
    occurrences: list[SchematicGeometryScan] = []
    bindings: list[SchematicSourceBinding] = []
    occurrence_paths: set[str] = set()

    def visit(
        source_path: str,
        sheet_instance_path: str,
        sheet_path: tuple[str, ...],
        ancestors: tuple[str, ...],
    ) -> None:
        if source_path in ancestors:
            raise ValueError(f"Recursive schematic sheet reference: {source_path}")
        if len(occurrences) >= MAX_SHEET_OCCURRENCES:
            raise ValueError(f"Schematic hierarchy exceeds {MAX_SHEET_OCCURRENCES} sheet instances")
        source = source_files.get(source_path)
        if source is None:
            raise ValueError(f"Referenced schematic source is missing: {source_path}")
        text, root = _schematic_root(source)
        root_uuid = _scalar(text, root, "uuid")
        if not root_uuid:
            raise ValueError(f"Schematic source has an empty UUID: {source_path}")
        if sheet_instance_path in occurrence_paths:
            raise ValueError(f"Duplicate schematic sheet-instance path: {sheet_instance_path}")
        occurrence_paths.add(sheet_instance_path)
        references, reference_issues = _instance_references(
            text,
            root,
            project_name,
            sheet_instance_path,
        )
        scan = scan_unconnected_pin_wire_geometry(
            source,
            source_path=source_path,
            kicad_version=kicad_version,
            unconnected_pins=unconnected_pins,
            sheet_instance_path=sheet_instance_path,
            reference_overrides=references,
            require_reference_overrides=True,
            allow_hierarchical_sheets=True,
        )
        scan_issues = tuple(sorted(set(scan.unsupported) | set(reference_issues)))
        occurrence_issues = tuple(
            f"{source_path} at {sheet_instance_path}: {issue}" for issue in scan_issues
        )
        if occurrence_issues:
            occurrence_issues_by_rule = {
                rule_id: [f"{source_path} at {sheet_instance_path}: {issue}" for issue in issues]
                for rule_id, issues in scan.unsupported_by_rule.items()
            }
            if reference_issues:
                for rule_id in (*_PIN_GEOMETRY_RULE_IDS, *_SYMBOL_BODY_RULE_IDS):
                    occurrence_issues_by_rule.setdefault(rule_id, []).extend(
                        f"{source_path} at {sheet_instance_path}: {issue}"
                        for issue in reference_issues
                    )
            scan = replace(
                scan,
                status="UNSUPPORTED" if scan.status == "UNSUPPORTED" else "PARTIAL",
                unsupported=occurrence_issues,
                unsupported_by_rule={
                    rule_id: tuple(sorted(set(issues)))
                    for rule_id, issues in sorted(occurrence_issues_by_rule.items())
                },
            )
        occurrences.append(scan)
        bindings.append(
            SchematicSourceBinding(
                source_path=source_path,
                source_sha256=scan.source_sha256,
                sheet_instance_path=sheet_instance_path,
                sheet_path=sheet_path,
            )
        )
        if scan.schematic_version != SUPPORTED_SCHEMATIC_VERSION:
            return
        next_ancestors = (*ancestors, source_path)
        for sheet in schematic_sheet_references(source):
            child_path = resolve_schematic_sheet_path(
                source_path,
                project_directory,
                sheet.file,
            )
            child_instance_path = f"{sheet_instance_path}/{sheet.uuid}"
            visit(
                child_path,
                child_instance_path,
                (*sheet_path, sheet.name),
                next_ancestors,
            )

    root_source = source_files[root_path]
    root_text, root_node = _schematic_root(root_source)
    root_uuid = _scalar(root_text, root_node, "uuid")
    root_instance_path = f"/{root_uuid}"
    visit(root_path, root_instance_path, (), ())

    unique_sources = {binding.source_path: binding.source_sha256 for binding in bindings}

    statuses = {scan.status for scan in occurrences}
    status: Literal["COMPLETE", "PARTIAL", "UNSUPPORTED"] = (
        "COMPLETE"
        if statuses == {"COMPLETE"}
        else "UNSUPPORTED"
        if statuses == {"UNSUPPORTED"}
        else "PARTIAL"
    )
    root_scan = occurrences[0]
    unsupported = tuple(sorted({issue for scan in occurrences for issue in scan.unsupported}))
    unsupported_by_rule: dict[str, set[str]] = {}
    for occurrence in occurrences:
        for rule_id, issues in occurrence.unsupported_by_rule.items():
            unsupported_by_rule.setdefault(rule_id, set()).update(issues)
    return SchematicGeometryScan(
        status=status,
        source_path=root_path,
        source_sha256=root_scan.source_sha256,
        kicad_version=kicad_version,
        schematic_version=root_scan.schematic_version,
        findings=tuple(
            sorted(
                (item for scan in occurrences for item in scan.findings),
                key=lambda item: (
                    item.sheet_instance_path,
                    item.reference,
                    item.pin_number,
                    item.wire_uuid,
                ),
            )
        ),
        pin_tip_on_wire_interiors=tuple(
            sorted(
                (item for scan in occurrences for item in scan.pin_tip_on_wire_interiors),
                key=lambda item: (
                    item.sheet_instance_path,
                    item.reference,
                    item.pin_number,
                    item.wire_uuid,
                ),
            )
        ),
        wire_endpoints_near_pin_tips=tuple(
            sorted(
                (item for scan in occurrences for item in scan.wire_endpoints_near_pin_tips),
                key=lambda item: (
                    item.sheet_instance_path,
                    item.reference,
                    item.pin_number,
                    item.distance_to_pin_tip_mm,
                    item.wire_uuid,
                ),
            )
        ),
        labels_near_wire_endpoints=tuple(
            sorted(
                (item for scan in occurrences for item in scan.labels_near_wire_endpoints),
                key=lambda item: (item.sheet_instance_path, item.label_kind, item.label_uuid),
            )
        ),
        unmarked_wire_crossings=tuple(
            sorted(
                (item for scan in occurrences for item in scan.unmarked_wire_crossings),
                key=lambda item: (item.sheet_instance_path, item.crossing_mm, item.wire_uuids),
            )
        ),
        unmarked_t_junctions=tuple(
            sorted(
                (item for scan in occurrences for item in scan.unmarked_t_junctions),
                key=lambda item: (
                    item.sheet_instance_path,
                    item.junction_mm,
                    item.endpoint_wire_uuid,
                    item.interior_wire_uuid,
                ),
            )
        ),
        coincident_text_anchors=tuple(
            sorted(
                (item for scan in occurrences for item in scan.coincident_text_anchors),
                key=lambda item: (
                    item.sheet_instance_path,
                    item.anchor_mm,
                    item.first_uuid,
                    item.second_uuid,
                ),
            )
        ),
        free_text_overlaps=tuple(
            sorted(
                (item for scan in occurrences for item in scan.free_text_overlaps),
                key=lambda item: (
                    item.sheet_instance_path,
                    item.overlap_box_mm,
                    item.first_uuid,
                    item.second_uuid,
                ),
            )
        ),
        free_text_wire_overlaps=tuple(
            sorted(
                (item for scan in occurrences for item in scan.free_text_wire_overlaps),
                key=lambda item: (
                    item.sheet_instance_path,
                    item.text_uuid,
                    item.wire_uuid,
                    item.wire_segment_start_mm,
                    item.wire_segment_end_mm,
                ),
            )
        ),
        free_text_symbol_body_overlaps=tuple(
            sorted(
                (item for scan in occurrences for item in scan.free_text_symbol_body_overlaps),
                key=lambda item: (
                    item.sheet_instance_path,
                    item.reference,
                    item.symbol_uuid,
                    item.text_uuid,
                    item.overlap_box_mm,
                ),
            )
        ),
        wires_through_symbol_bodies=tuple(
            sorted(
                (item for scan in occurrences for item in scan.wires_through_symbol_bodies),
                key=lambda item: (
                    item.sheet_instance_path,
                    item.reference,
                    item.symbol_uuid,
                    item.wire_uuid,
                    item.overlap_start_mm,
                ),
            )
        ),
        source_tree_sha256=_source_tree_sha256(unique_sources),
        source_bindings=tuple(
            sorted(bindings, key=lambda binding: (binding.sheet_instance_path, binding.source_path))
        ),
        unsupported=unsupported,
        unsupported_by_rule={
            rule_id: tuple(sorted(issues))
            for rule_id, issues in sorted(unsupported_by_rule.items())
        },
    )


def scan_wire_ends_on_pin_lines(
    source: bytes,
    *,
    source_path: str,
    kicad_version: str,
    unconnected_pins: frozenset[str],
) -> SchematicGeometryScan:
    """Compatibility alias for the expanded pin/wire geometry scan."""
    return scan_unconnected_pin_wire_geometry(
        source,
        source_path=source_path,
        kicad_version=kicad_version,
        unconnected_pins=unconnected_pins,
    )
