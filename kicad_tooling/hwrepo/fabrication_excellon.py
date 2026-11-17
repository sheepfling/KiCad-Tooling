"""Read the bounded Excellon drill subset used by fabrication analysis."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from .fabrication_artwork import UnsupportedFabricationFormat


@dataclass(frozen=True)
class DrillHit:
    """One exported drill hit, with the precision declared by its source text."""

    x_mm: float
    y_mm: float
    diameter_mm: float
    end_mm: tuple[float, float] | None = None
    coordinate_resolution_nm: int = 1
    diameter_resolution_nm: int = 1


_COORDINATE_FIELD_RE = re.compile(r"([XY])([+-]?(?:\d+(?:\.\d*)?|\.\d+))")


def _coordinate_fields(raw: str) -> dict[str, str]:
    """Parse a complete X/Y field sequence without accepting ignored suffixes."""
    fields: dict[str, str] = {}
    cursor = 0
    for match in _COORDINATE_FIELD_RE.finditer(raw):
        if match.start() != cursor:
            raise UnsupportedFabricationFormat("malformed Excellon coordinate fields")
        axis, value = match.groups()
        if axis in fields:
            raise UnsupportedFabricationFormat(f"Excellon coordinate field {axis} is repeated")
        fields[axis] = value
        cursor = match.end()
    if cursor != len(raw):
        raise UnsupportedFabricationFormat("malformed Excellon coordinate fields")
    return fields


def _resolution_nm(raw: str, metric: bool, coordinate_format: tuple[int, int] | None) -> int:
    if "." in raw:
        decimals = len(raw.partition(".")[2])
    else:
        decimals = (coordinate_format or ((3, 3) if metric else (2, 4)))[1]
    millimeters = 1.0 if metric else 25.4
    return max(1, round((10**-decimals) * millimeters * 1_000_000))


def parse_excellon(text: str) -> tuple[DrillHit, ...]:
    """Read decimal and fixed-width Excellon coordinates used by KiCad exports."""
    metric = True
    zero_mode = "L"
    coordinate_format: tuple[int, int] | None = None
    tools: dict[int, tuple[float, int]] = {}
    selected: int | None = None
    hits: list[DrillHit] = []
    x = y = 0.0
    x_resolution_nm = y_resolution_nm = 1
    slot_start: tuple[float, float] | None = None
    format_lines = [line for line in text.splitlines() if "FILE_FORMAT" in line.upper()]
    if len(format_lines) > 1:
        raise UnsupportedFabricationFormat("Excellon has multiple FILE_FORMAT declarations")
    if format_lines:
        header = re.fullmatch(
            r"\s*;?\s*FILE_FORMAT\s*=\s*(\d):([0-8])\s*",
            format_lines[0],
            flags=re.IGNORECASE,
        )
        if header is None:
            raise UnsupportedFabricationFormat(
                "Excellon has an unsupported FILE_FORMAT declaration"
            )
        coordinate_format = int(header.group(1)), int(header.group(2))

    def coordinate(raw: str) -> float:
        try:
            if "." in raw:
                value = float(raw)
            else:
                integer, decimals = coordinate_format or ((3, 3) if metric else (2, 4))
                sign = -1 if raw.startswith("-") else 1
                digits = raw.lstrip("+-")
                width = integer + decimals
                digits = digits.ljust(width, "0") if zero_mode == "T" else digits.rjust(width, "0")
                value = sign * int(digits or "0") / 10**decimals
        except (OverflowError, ValueError) as exc:
            raise UnsupportedFabricationFormat("Excellon coordinate cannot be represented") from exc
        if any(digit in "123456789" for digit in raw) and value == 0.0:
            raise UnsupportedFabricationFormat("Excellon coordinate underflows its numeric format")
        if not metric:
            value *= 25.4
        if not math.isfinite(value):
            raise UnsupportedFabricationFormat("Excellon coordinate is non-finite")
        if any(digit in "123456789" for digit in raw) and value == 0.0:
            raise UnsupportedFabricationFormat("Excellon coordinate underflows its unit conversion")
        if not math.isfinite(value * 1_000_000):
            raise UnsupportedFabricationFormat(
                "Excellon coordinate exceeds the finite nanometer range"
            )
        return value

    def selected_drill_geometry() -> tuple[float, int]:
        if selected is None:
            raise UnsupportedFabricationFormat("Excellon drill hit has no selected tool")
        try:
            return tools[selected]
        except KeyError as exc:
            raise UnsupportedFabricationFormat(
                f"Excellon selects undefined tool T{selected}"
            ) from exc

    for raw_line in text.splitlines():
        line = raw_line.strip()
        upper = line.upper()
        if not line or line.startswith(";"):
            continue
        if upper.startswith(("METRIC", "M71", "INCH", "M72")):
            metric = upper.startswith(("METRIC", "M71"))
            zero_mode = "T" if "TZ" in upper else "L"
            continue
        tool = re.fullmatch(r"T(\d+)(?:F\d+S\d+)?C([\d.]+)", upper)
        if tool:
            tool_id = int(tool.group(1))
            raw_diameter = tool.group(2)
            diameter = float(raw_diameter)
            if not math.isfinite(diameter):
                raise UnsupportedFabricationFormat(
                    f"Excellon tool T{tool_id} has a non-finite diameter"
                )
            if diameter <= 0:
                raise UnsupportedFabricationFormat(
                    f"Excellon tool T{tool_id} has a non-positive diameter"
                )
            if not math.isfinite(diameter * 1_000_000):
                raise UnsupportedFabricationFormat(
                    f"Excellon tool T{tool_id} diameter exceeds the finite nanometer range"
                )
            geometry = (
                diameter if metric else diameter * 25.4,
                _resolution_nm(raw_diameter, metric, coordinate_format),
            )
            previous = tools.get(tool_id)
            if previous is not None and previous != geometry:
                raise UnsupportedFabricationFormat(
                    f"Excellon tool T{tool_id} has conflicting diameter definitions"
                )
            tools[tool_id] = geometry
            continue
        selection = re.fullmatch(r"T(\d+)", upper)
        if selection:
            selected = int(selection.group(1))
            if selected not in tools:
                raise UnsupportedFabricationFormat(f"Excellon selects undefined tool T{selected}")
            continue
        if upper.startswith("M15"):
            slot_start = (x, y)
            continue
        if upper.startswith(("M16", "M17")):
            slot_start = None
            continue
        if upper.startswith(("M48", "FMAT", "%", "G90", "G05", "M30")):
            continue
        slot_parts = re.split(r"G85", upper)
        if len(slot_parts) > 2:
            raise UnsupportedFabricationFormat("Excellon command has multiple G85 slot separators")
        coordinate_text = slot_parts[0]
        if upper.startswith(("G00", "G01")):
            coordinate_text = coordinate_text[3:]
        coords = _coordinate_fields(coordinate_text)
        if not coords:
            if upper.startswith(("G00", "G01")):
                continue
            raise UnsupportedFabricationFormat(f"unsupported Excellon command {line!r}")
        if "X" in coords:
            nx = coordinate(coords["X"])
            x_resolution_nm = _resolution_nm(coords["X"], metric, coordinate_format)
        else:
            nx = x
        if "Y" in coords:
            ny = coordinate(coords["Y"])
            y_resolution_nm = _resolution_nm(coords["Y"], metric, coordinate_format)
        else:
            ny = y
        coordinate_resolution_nm = max(x_resolution_nm, y_resolution_nm)
        if len(slot_parts) > 1:
            diameter, diameter_resolution_nm = selected_drill_geometry()
            end_fields = _coordinate_fields(slot_parts[1])
            end = (
                coordinate(end_fields["X"]) if "X" in end_fields else nx,
                coordinate(end_fields["Y"]) if "Y" in end_fields else ny,
            )
            hits.append(
                DrillHit(
                    nx,
                    ny,
                    diameter,
                    end,
                    coordinate_resolution_nm,
                    diameter_resolution_nm,
                )
            )
            x, y = end
        elif upper.startswith("G00"):
            x, y = nx, ny
        elif upper.startswith("G01") and slot_start is not None:
            diameter, diameter_resolution_nm = selected_drill_geometry()
            hits.append(
                DrillHit(
                    x,
                    y,
                    diameter,
                    (nx, ny),
                    coordinate_resolution_nm,
                    diameter_resolution_nm,
                )
            )
            x, y = nx, ny
        else:
            diameter, diameter_resolution_nm = selected_drill_geometry()
            hits.append(
                DrillHit(
                    nx,
                    ny,
                    diameter,
                    coordinate_resolution_nm=coordinate_resolution_nm,
                    diameter_resolution_nm=diameter_resolution_nm,
                )
            )
            x, y = nx, ny
    return tuple(hits)
