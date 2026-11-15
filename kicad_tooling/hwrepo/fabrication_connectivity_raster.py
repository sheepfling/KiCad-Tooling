"""Rasterize supported artwork and build copper connectivity components."""

from __future__ import annotations

import math
from dataclasses import dataclass
from importlib import import_module
from typing import Protocol, cast

import numpy as np
from numpy.typing import NDArray
from PIL import Image, ImageDraw

from .fabrication_artwork import Contact, DrillHit, GerberFeature, GerberLayer

_PIXEL_LIMIT = 24_000_000


class _NdimageLabel(Protocol):
    def __call__(self, input: NDArray[np.bool_]) -> tuple[NDArray[np.int32], int]: ...


class _ScipyNdimage(Protocol):
    label: _NdimageLabel


_label_components = cast(_ScipyNdimage, import_module("scipy.ndimage")).label


@dataclass(frozen=True)
class PadAssignment:
    contact: Contact
    components: tuple[int, ...]


@dataclass(frozen=True)
class RasterAnalysis:
    assignments: tuple[PadAssignment, ...]
    opens: tuple[tuple[str, tuple[str, ...]], ...]
    shorts: tuple[tuple[str, ...], ...]
    no_copper: tuple[Contact, ...]
    no_drill: tuple[Contact, ...]


@dataclass(frozen=True)
class _Canvas:
    bounds: tuple[float, float, float, float]
    density: int
    width: int
    height: int

    def point(self, x_mm: float, y_mm: float) -> tuple[int, int]:
        x0, _, _, y1 = self.bounds
        return round((x_mm - x0) * self.density), round((y1 - y_mm) * self.density)


class _UnionFind:
    def __init__(self, size: int) -> None:
        self.parent = list(range(size))

    def find(self, item: int) -> int:
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, left: int, right: int) -> None:
        self.parent[self.find(right)] = self.find(left)


def _coordinates(
    layers: tuple[GerberLayer, ...], contacts: tuple[Contact, ...], drills: tuple[DrillHit, ...]
) -> list[tuple[float, float]]:
    points = [(contact.x_mm, contact.y_mm) for contact in contacts]
    for hit in drills:
        points.append((hit.x_mm, hit.y_mm))
        if hit.end_mm:
            points.append(hit.end_mm)
    for layer in layers:
        for feature in layer.features:
            points.extend(feature.points)
            if feature.aperture:
                radius = max(feature.aperture[1][:2], default=0.0) / 2
                x, y = feature.points[0]
                points.extend(((x - radius, y - radius), (x + radius, y + radius)))
            elif feature.width_mm:
                radius = feature.width_mm / 2
                points.extend(
                    (x + sx * radius, y + sy * radius)
                    for x, y in feature.points
                    for sx, sy in ((-1, -1), (1, 1))
                )
    return points


def _canvas(
    layers: tuple[GerberLayer, ...],
    contacts: tuple[Contact, ...],
    drills: tuple[DrillHit, ...],
    density: int,
) -> _Canvas:
    points = _coordinates(layers, contacts, drills)
    if not points:
        raise ValueError("no supported artwork or contact coordinates")
    xs, ys = zip(*points, strict=True)
    margin = 1.0
    bounds = min(xs) - margin, min(ys) - margin, max(xs) + margin, max(ys) + margin
    width = math.ceil((bounds[2] - bounds[0]) * density)
    height = math.ceil((bounds[3] - bounds[1]) * density)
    if width <= 0 or height <= 0 or width * height * len(layers) > _PIXEL_LIMIT:
        raise ValueError("raster exceeds the configured analyzer pixel budget")
    return _Canvas(bounds, density, width, height)


def _draw_feature(draw: ImageDraw.ImageDraw, canvas: _Canvas, feature: GerberFeature) -> None:
    points = [canvas.point(x, y) for x, y in feature.points]
    if feature.kind == "region":
        draw.polygon(points, fill=255)
    elif feature.kind == "stroke":
        width = max(1, round(feature.width_mm * canvas.density))
        draw.line(points, fill=255, width=width)
        radius = width / 2
        for x, y in points:
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=255)
    elif feature.aperture is not None:
        kind, sizes = feature.aperture
        x, y = points[0]
        if kind == "C":
            radius = max(0.5, sizes[0] * canvas.density / 2)
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=255)
        elif kind in {"R", "O"}:
            width = sizes[0] * canvas.density
            height = sizes[1] * canvas.density if len(sizes) > 1 else width
            box = (x - width / 2, y - height / 2, x + width / 2, y + height / 2)
            if kind == "O":
                draw.rounded_rectangle(box, radius=min(width, height) / 2, fill=255)
            else:
                draw.rectangle(box, fill=255)
        elif kind == "P":
            diameter, vertices = sizes[:2]
            rotation = sizes[2] if len(sizes) > 2 else 0.0
            points = [
                (
                    x
                    + diameter
                    * canvas.density
                    / 2
                    * math.cos(math.radians(rotation) + 2 * math.pi * i / int(vertices)),
                    y
                    - diameter
                    * canvas.density
                    / 2
                    * math.sin(math.radians(rotation) + 2 * math.pi * i / int(vertices)),
                )
                for i in range(int(vertices))
            ]
            draw.polygon(points, fill=255)


def _render(layer: GerberLayer, canvas: _Canvas) -> np.ndarray:
    image = Image.new("L", (canvas.width, canvas.height), 0)
    draw = ImageDraw.Draw(image)
    for feature in layer.features:
        _draw_feature(draw, canvas, feature)
    return np.asarray(image) > 127


def _component_at(
    labels: np.ndarray, canvas: _Canvas, x_mm: float, y_mm: float, size_mm: float
) -> int | None:
    x, y = canvas.point(x_mm, y_mm)
    if 0 <= x < canvas.width and 0 <= y < canvas.height and labels[y, x] != 0:
        return int(labels[y, x])
    radius = max(size_mm * 0.44, 0.08) * canvas.density
    for ring in (0.5, 0.75, 1.0):
        for step in range(24):
            angle = step * math.tau / 24
            px = round(x + radius * ring * math.cos(angle))
            py = round(y - radius * ring * math.sin(angle))
            if 0 <= px < canvas.width and 0 <= py < canvas.height and labels[py, px] != 0:
                return int(labels[py, px])
    return None


def _hit_samples(hit: DrillHit) -> tuple[tuple[float, float], ...]:
    if hit.end_mm is None:
        return ((hit.x_mm, hit.y_mm),)
    x2, y2 = hit.end_mm
    return tuple(
        (hit.x_mm + (x2 - hit.x_mm) * portion, hit.y_mm + (y2 - hit.y_mm) * portion)
        for portion in (0.0, 0.25, 0.5, 0.75, 1.0)
    )


def analyze_raster(
    layers: tuple[GerberLayer, ...],
    contacts: tuple[Contact, ...],
    plated_drills: tuple[DrillHit, ...],
    density: int,
) -> RasterAnalysis:
    """Return deterministic net-to-island differences for a two-layer board."""
    canvas = _canvas(layers, contacts, plated_drills, density)
    labels: dict[str, np.ndarray] = {}
    base: dict[str, int] = {}
    component_count = 0
    for layer in layers:
        labels[layer.side], count = _label_components(_render(layer, canvas))
        base[layer.side] = component_count
        component_count += int(count) + 1
    union = _UnionFind(component_count + 1)

    def node(side: str, x_mm: float, y_mm: float, size_mm: float = 0.0) -> int | None:
        part = _component_at(labels[side], canvas, x_mm, y_mm, size_mm)
        return None if part is None else base[side] + part

    for hit in plated_drills:
        for x_mm, y_mm in _hit_samples(hit):
            across_layers = [
                candidate
                for side in ("top", "bottom")
                if (candidate := node(side, x_mm, y_mm)) is not None
            ]
            for candidate in across_layers[1:]:
                union.union(across_layers[0], candidate)

    assignments: list[PadAssignment] = []
    no_copper: list[Contact] = []
    no_drill: list[Contact] = []
    for contact in contacts:
        sides = ("top", "bottom") if contact.layer == "through" else (contact.layer,)
        parts = [
            part
            for side in sides
            if (part := node(side, contact.x_mm, contact.y_mm, contact.size_mm)) is not None
        ]
        if not parts:
            no_copper.append(contact)
        assignments.append(PadAssignment(contact, tuple(union.find(part) for part in parts)))
        if contact.layer == "through" and not any(
            math.dist((contact.x_mm, contact.y_mm), sample) <= max(contact.size_mm / 2, 0.20)
            for hit in plated_drills
            for sample in _hit_samples(hit)
        ):
            no_drill.append(contact)

    by_island: dict[int, set[str]] = {}
    by_island_contacts: dict[int, set[str]] = {}
    by_net: dict[str, dict[int, set[str]]] = {}
    for assignment in assignments:
        contact = assignment.contact
        label = f"{contact.net}:{contact.label}"
        for component in assignment.components:
            root = union.find(component)
            by_island.setdefault(root, set()).add(contact.net)
            by_island_contacts.setdefault(root, set()).add(label)
            by_net.setdefault(contact.net, {}).setdefault(root, set()).add(contact.label)

    shorts = tuple(
        tuple(sorted(by_island_contacts[root]))
        for root in sorted(by_island)
        if len(by_island[root]) > 1
    )
    opens = tuple(
        (net, tuple(sorted({label for values in components.values() for label in values})))
        for net, components in sorted(by_net.items())
        if len(components) > 1 and not net.startswith("N/C:")
    )
    return RasterAnalysis(
        assignments=tuple(assignments),
        opens=opens,
        shorts=shorts,
        no_copper=tuple(no_copper),
        no_drill=tuple(no_drill),
    )
