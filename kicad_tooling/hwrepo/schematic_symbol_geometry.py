"""Placed symbol pins and conservative symbol-body envelopes."""

from __future__ import annotations

import math

from .model_inventory import _atoms, _children, _Span  # pyright: ignore[reportPrivateUsage]
from .schematic_geometry_primitives import transform_point
from .schematic_geometry_source import (
    schematic_at,
    schematic_nodes,
    schematic_number,
    schematic_property,
    schematic_scalar,
)
from .schematic_geometry_types import SUBSYMBOL_UNIT, SchematicPin, SymbolBodyEnvelope


def instance_pin_uuids(source: str, placed: _Span) -> dict[str, str]:
    result: dict[str, str] = {}
    for node in schematic_nodes(source, placed, "pin"):
        atoms = _atoms(source, node)
        if len(atoms) != 2 or not atoms[1] or atoms[1] in result:
            raise ValueError("Malformed or duplicate placed symbol pin")
        uuids = schematic_nodes(source, node, "uuid")
        result[atoms[1]] = _atoms(source, uuids[0])[1] if len(uuids) == 1 else ""
    return result


def pins_for_instance(
    source: str,
    placed: _Span,
    libraries: dict[str, _Span],
    *,
    reference_override: str | None = None,
) -> tuple[tuple[SchematicPin, ...], str | None]:
    symbol_uuids = schematic_nodes(source, placed, "uuid")
    if len(symbol_uuids) != 1:
        return (), "symbol instance has no unique UUID"
    symbol_uuid = _atoms(source, symbol_uuids[0])[1]
    reference = (
        reference_override
        if reference_override is not None
        else schematic_property(source, placed, "Reference")
    )
    if not reference or reference.startswith("#"):
        return (), "non-component or anonymous symbol"
    library_id = schematic_scalar(source, placed, "lib_id")
    library = libraries.get(library_id)
    if library is None:
        return (), f"embedded symbol unavailable for {library_id}"
    unit_text = schematic_scalar(source, placed, "unit")
    if not unit_text.isdecimal() or int(unit_text) != 1:
        return (), f"multi-unit symbol {reference} is outside this prototype"
    unit = int(unit_text)
    position = schematic_at(source, placed, angle_required=True)
    if position[2] not in {0.0, 90.0, 180.0, 270.0}:
        return (), f"non-orthogonal symbol rotation on {reference}"
    mirrors = schematic_nodes(source, placed, "mirror")
    if len(mirrors) > 1:
        return (), f"ambiguous mirror state on {reference}"
    mirror: str | None = None
    if mirrors:
        mirror_atoms = _atoms(source, mirrors[0])
        if len(mirror_atoms) != 2 or mirror_atoms[1] not in {"x", "y"}:
            return (), f"unsupported mirror state on {reference}"
        mirror = mirror_atoms[1]

    sub_symbols = schematic_nodes(source, library, "symbol")
    parsed: list[tuple[int, int, _Span]] = []
    for sub_symbol in sub_symbols:
        atoms = _atoms(source, sub_symbol)
        suffix = SUBSYMBOL_UNIT.search(atoms[1]) if len(atoms) == 2 else None
        if suffix is None:
            return (), f"unrecognized embedded unit on {reference}"
        parsed.append((int(suffix[1]), int(suffix[2]), sub_symbol))
    unit_numbers = {subunit for subunit, _, _ in parsed if subunit > 0}
    if unit_numbers != {unit} or any(conversion != 1 for _, conversion, _ in parsed):
        return (), f"multi-unit or multi-conversion symbol {reference} is outside this prototype"

    instance_uuids = instance_pin_uuids(source, placed)
    pins: list[SchematicPin] = []
    seen_numbers: set[str] = set()
    for subunit, _, sub_symbol in parsed:
        if subunit not in {0, unit}:
            continue
        for pin_node in schematic_nodes(source, sub_symbol, "pin"):
            pin_number = schematic_scalar(source, pin_node, "number")
            if not pin_number or pin_number in seen_numbers:
                return (), f"duplicate or empty pin number on {reference}"
            seen_numbers.add(pin_number)
            pin_name = schematic_scalar(source, pin_node, "name")
            tip_x, tip_y, pin_angle = schematic_at(source, pin_node, angle_required=True)
            lengths = schematic_nodes(source, pin_node, "length")
            if len(lengths) != 1:
                return (), f"pin length unavailable for {reference}.{pin_number}"
            length_atoms = _atoms(source, lengths[0])
            if len(length_atoms) != 2:
                return (), f"malformed pin length for {reference}.{pin_number}"
            pin_length = schematic_number(length_atoms[1], "pin length")
            if pin_length <= 0:
                return (), f"non-positive pin length for {reference}.{pin_number}"
            radians = math.radians(pin_angle)
            body_x = tip_x + pin_length * math.cos(radians)
            body_y = tip_y + pin_length * math.sin(radians)
            pin_uuid = instance_uuids.get(pin_number) or None
            pins.append(
                SchematicPin(
                    reference=reference,
                    library_id=library_id,
                    symbol_uuid=symbol_uuid,
                    number=pin_number,
                    name=pin_name,
                    pin_uuid=pin_uuid,
                    tip=transform_point((tip_x, tip_y), position[:2], position[2], mirror),
                    body_end=transform_point((body_x, body_y), position[:2], position[2], mirror),
                )
            )
    return tuple(pins), None


def body_primitive_points(
    source: str,
    primitive: _Span,
    kind: str,
) -> tuple[tuple[float, float], ...]:
    if kind == "rectangle":
        starts = schematic_nodes(source, primitive, "start")
        ends = schematic_nodes(source, primitive, "end")
        if len(starts) != 1 or len(ends) != 1:
            raise ValueError("symbol rectangle needs one start and end point")
        start = _atoms(source, starts[0])
        end = _atoms(source, ends[0])
        if len(start) != 3 or len(end) != 3:
            raise ValueError("symbol rectangle has malformed coordinates")
        x0, y0 = (
            schematic_number(start[1], "symbol x coordinate"),
            schematic_number(start[2], "symbol y coordinate"),
        )
        x1, y1 = (
            schematic_number(end[1], "symbol x coordinate"),
            schematic_number(end[2], "symbol y coordinate"),
        )
        return ((x0, y0), (x0, y1), (x1, y0), (x1, y1))
    if kind in {"polyline", "bezier"}:
        points_sections = schematic_nodes(source, primitive, "pts")
        if len(points_sections) != 1:
            raise ValueError(f"symbol {kind} needs one point list")
        points = schematic_nodes(source, points_sections[0], "xy")
        coordinates: list[tuple[float, float]] = []
        for point in points:
            atoms = _atoms(source, point)
            if len(atoms) != 3:
                raise ValueError(f"symbol {kind} has malformed coordinates")
            coordinates.append(
                (
                    schematic_number(atoms[1], "symbol x coordinate"),
                    schematic_number(atoms[2], "symbol y coordinate"),
                )
            )
        if len(coordinates) < (4 if kind == "bezier" else 2):
            raise ValueError(f"symbol {kind} has too few points")
        return tuple(coordinates)
    if kind == "circle":
        centers = schematic_nodes(source, primitive, "center")
        radii = schematic_nodes(source, primitive, "radius")
        if len(centers) != 1 or len(radii) != 1:
            raise ValueError("symbol circle needs one center and radius")
        center = _atoms(source, centers[0])
        radius_atoms = _atoms(source, radii[0])
        if len(center) != 3 or len(radius_atoms) != 2:
            raise ValueError("symbol circle has malformed geometry")
        x = schematic_number(center[1], "symbol x coordinate")
        y = schematic_number(center[2], "symbol y coordinate")
        radius = schematic_number(radius_atoms[1], "symbol radius")
        if radius <= 0.0:
            raise ValueError("symbol circle radius must be positive")
        return (
            (x - radius, y - radius),
            (x - radius, y + radius),
            (x + radius, y - radius),
            (x + radius, y + radius),
        )
    raise ValueError(f"symbol body primitive {kind!r} is outside the measured geometry")


def symbol_body_envelope_for_instance(
    source: str,
    placed: _Span,
    libraries: dict[str, _Span],
    *,
    reference_override: str | None = None,
) -> tuple[SymbolBodyEnvelope | None, str | None]:
    symbol_uuids = schematic_nodes(source, placed, "uuid")
    if len(symbol_uuids) != 1:
        return None, "symbol body has no unique instance UUID"
    uuid_atoms = _atoms(source, symbol_uuids[0])
    if len(uuid_atoms) != 2 or not uuid_atoms[1]:
        return None, "symbol body has a malformed instance UUID"
    symbol_uuid = uuid_atoms[1]
    reference = (
        reference_override
        if reference_override is not None
        else schematic_property(source, placed, "Reference")
    )
    if not reference or reference.startswith("#"):
        return None, None
    library_id = schematic_scalar(source, placed, "lib_id")
    library = libraries.get(library_id)
    if library is None:
        return None, f"embedded symbol unavailable for body geometry on {reference}"
    unit_text = schematic_scalar(source, placed, "unit")
    if not unit_text.isdecimal() or int(unit_text) != 1:
        return None, f"multi-unit symbol body is outside this prototype: {reference}"
    position = schematic_at(source, placed, angle_required=True)
    if position[2] not in {0.0, 90.0, 180.0, 270.0}:
        return None, f"non-orthogonal symbol body rotation on {reference}"
    mirrors = schematic_nodes(source, placed, "mirror")
    if len(mirrors) > 1:
        return None, f"ambiguous symbol body mirror state on {reference}"
    mirror: str | None = None
    if mirrors:
        mirror_atoms = _atoms(source, mirrors[0])
        if len(mirror_atoms) != 2 or mirror_atoms[1] not in {"x", "y"}:
            return None, f"unsupported symbol body mirror state on {reference}"
        mirror = mirror_atoms[1]

    parsed_subsymbols: list[tuple[int, int, _Span]] = []
    for subsymbol in schematic_nodes(source, library, "symbol"):
        atoms = _atoms(source, subsymbol)
        suffix = SUBSYMBOL_UNIT.search(atoms[1]) if len(atoms) == 2 else None
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
                local_points.extend(body_primitive_points(source, child, kind))
            except ValueError as exc:
                return None, f"symbol body geometry is unsupported on {reference}: {exc}"
    if not saw_primitive or not local_points:
        return None, None

    points = tuple(
        transform_point(point, position[:2], position[2], mirror) for point in local_points
    )
    x_values = tuple(point[0] for point in points)
    y_values = tuple(point[1] for point in points)
    box = (min(x_values), min(y_values), max(x_values), max(y_values))
    if box[0] >= box[2] or box[1] >= box[3]:
        return None, f"symbol body has no two-dimensional envelope on {reference}"
    return SymbolBodyEnvelope(reference, library_id, symbol_uuid, box), None
