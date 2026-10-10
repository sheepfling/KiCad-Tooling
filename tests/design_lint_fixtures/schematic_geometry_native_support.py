"""Native SVG and geometry measurements shared by schematic parity tests."""

from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET


def _native_svg_text_strokes(
    svg_root: ET.Element, wanted: str
) -> tuple[tuple[tuple[float, float], tuple[float, float]], ...]:
    """Read KiCad's standard-stroke SVG line segments for one unique text object."""
    matches: list[ET.Element] = []
    for node in svg_root.iter():
        if node.tag.endswith("}g") and node.attrib.get("class") == "stroked-text":
            description = next((child.text for child in node if child.tag.endswith("}desc")), None)
            if description == wanted:
                matches.append(node)
    if len(matches) != 1:
        raise AssertionError(f"native SVG did not contain one stroked-text group for {wanted!r}")

    segments: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for path in matches[0].iter():
        if not path.tag.endswith("}path"):
            continue
        tokens = re.findall(r"[ML]|[-+]?(?:\d+\.\d*|\.\d+|\d+)", path.attrib.get("d", ""))
        current: tuple[float, float] | None = None
        index = 0
        while index < len(tokens):
            command = tokens[index]
            if command not in {"M", "L"}:
                raise AssertionError(f"unsupported KiCad stroked-text path command {command!r}")
            point = (float(tokens[index + 1]), float(tokens[index + 2]))
            if command == "L" and current is not None:
                segments.append((current, point))
            current = point
            index += 3
    return tuple(segments)


def _native_svg_matching_line(
    svg_root: ET.Element,
    start: tuple[float, float],
    end: tuple[float, float],
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Read one exact native SVG line segment by its expected schematic endpoints."""
    matches: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for path in svg_root.iter():
        if not path.tag.endswith("}path"):
            continue
        tokens = re.findall(r"[ML]|[-+]?(?:\d+\.\d*|\.\d+|\d+)", path.attrib.get("d", ""))
        current: tuple[float, float] | None = None
        index = 0
        while index < len(tokens):
            command = tokens[index]
            if command not in {"M", "L"}:
                raise AssertionError(f"unsupported native SVG line command {command!r}")
            point = (float(tokens[index + 1]), float(tokens[index + 2]))
            if command == "L" and current is not None:
                forward = math.dist(current, start) <= 0.0001 and math.dist(point, end) <= 0.0001
                reverse = math.dist(current, end) <= 0.0001 and math.dist(point, start) <= 0.0001
                if forward or reverse:
                    matches.append((current, point))
            current = point
            index += 3
    if len(matches) != 1:
        raise AssertionError(f"native SVG did not contain one expected line segment: {matches!r}")
    return matches[0]


def _native_svg_matching_rect(
    svg_root: ET.Element,
    x: float,
    y: float,
    width: float,
    height: float,
) -> tuple[float, float, float, float]:
    """Read one exact native SVG rectangle by its schematic-space bounds."""
    matches = [
        (
            float(node.attrib["x"]),
            float(node.attrib["y"]),
            float(node.attrib["width"]),
            float(node.attrib["height"]),
        )
        for node in svg_root.iter()
        if node.tag.endswith("}rect")
        and all(
            abs(float(node.attrib[key]) - expected) <= 0.0001
            for key, expected in (
                ("x", x),
                ("y", y),
                ("width", width),
                ("height", height),
            )
        )
    ]
    if len(matches) != 1:
        raise AssertionError(f"native SVG did not contain one expected rectangle: {matches!r}")
    return matches[0]


def _netlist_components_without_sheetfile(netlist: ET.Element) -> bytes:
    """Normalize project-path metadata before comparing native component maps."""
    components = netlist.find("./components")
    if components is None:
        raise AssertionError("native netlist has no components section")
    normalized = ET.fromstring(ET.tostring(components))
    for parent in normalized.iter():
        for child in tuple(parent):
            if child.tag == "property" and child.attrib.get("name") == "Sheetfile":
                parent.remove(child)
    return ET.tostring(normalized)


def _segment_distance(
    first_start: tuple[float, float],
    first_end: tuple[float, float],
    second_start: tuple[float, float],
    second_end: tuple[float, float],
) -> float:
    def subtract(first: tuple[float, float], second: tuple[float, float]) -> tuple[float, float]:
        return first[0] - second[0], first[1] - second[1]

    def cross(first: tuple[float, float], second: tuple[float, float]) -> float:
        return first[0] * second[1] - first[1] * second[0]

    def point_segment(
        point: tuple[float, float], start: tuple[float, float], end: tuple[float, float]
    ) -> float:
        direction = subtract(end, start)
        length_squared = direction[0] ** 2 + direction[1] ** 2
        if length_squared == 0.0:
            return math.dist(point, start)
        projection = (
            (point[0] - start[0]) * direction[0] + (point[1] - start[1]) * direction[1]
        ) / length_squared
        parameter = min(1.0, max(0.0, projection))
        nearest = (
            start[0] + parameter * direction[0],
            start[1] + parameter * direction[1],
        )
        return math.dist(point, nearest)

    first_direction = subtract(first_end, first_start)
    second_direction = subtract(second_end, second_start)
    denominator = cross(first_direction, second_direction)
    offset = subtract(second_start, first_start)
    if denominator != 0.0:
        first_parameter = cross(offset, second_direction) / denominator
        second_parameter = cross(offset, first_direction) / denominator
        if 0.0 <= first_parameter <= 1.0 and 0.0 <= second_parameter <= 1.0:
            return 0.0
    return min(
        point_segment(first_start, second_start, second_end),
        point_segment(first_end, second_start, second_end),
        point_segment(second_start, first_start, first_end),
        point_segment(second_end, first_start, first_end),
    )
