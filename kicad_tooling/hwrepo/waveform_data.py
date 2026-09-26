"""Strict reader for the ngspice ASCII raw waveforms retained in electrical receipts."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from typing import Literal

AxisName = Literal["time", "frequency"]


@dataclass(frozen=True)
class WaveformSeries:
    """One named ngspice variable; unit preserves its raw variable type label."""

    name: str
    unit: str
    values: tuple[complex, ...]


@dataclass(frozen=True)
class WaveformData:
    """A complete transient or AC waveform with its physical sample coordinates."""

    axis_name: AxisName
    axis: tuple[float, ...]
    series: tuple[WaveformSeries, ...]


def _section_index(lines: list[str], section: str) -> int:
    matches = [index for index, line in enumerate(lines) if line.strip() == section]
    if len(matches) != 1:
        raise ValueError(f"Missing or duplicate ASCII waveform {section} section")
    return matches[0]


def _header(lines: list[str], name: str) -> str:
    prefix = f"{name}:"
    matches = [line[len(prefix):].strip() for line in lines if line.startswith(prefix)]
    if len(matches) != 1 or not matches[0]:
        raise ValueError(f"Missing or duplicate ASCII waveform {name} header")
    return matches[0]


def _count(lines: list[str], name: str) -> int:
    value = _header(lines, name)
    if not value.isdecimal() or int(value) < 1:
        raise ValueError(f"Invalid ASCII waveform {name} header")
    return int(value)


def _number(token: str) -> float:
    try:
        value = float(token)
    except ValueError as exc:
        raise ValueError(f"Invalid waveform numeric value: {token}") from exc
    if not math.isfinite(value):
        raise ValueError("Non-finite waveform data")
    return value


def _sample(token: str, *, complex_mode: bool) -> complex:
    parts = token.split(",")
    if len(parts) != (2 if complex_mode else 1):
        raise ValueError("Waveform value does not match real or complex Flags header")
    real = _number(parts[0])
    imag = _number(parts[1]) if complex_mode else 0.0
    return complex(real, imag)


def read_waveform(path: Path, expected_axis: AxisName | None = None) -> WaveformData:
    """Read complete ASCII raw data; reject inconsistent counts, axes and samples."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeError as exc:
        raise ValueError("Waveform artifact is not UTF-8 ASCII raw data") from exc
    variables_index = _section_index(lines, "Variables:")
    values_index = _section_index(lines, "Values:")
    if variables_index >= values_index:
        raise ValueError("ASCII waveform Variables section must precede Values")
    header = lines[:variables_index]
    width = _count(header, "No. Variables")
    count = _count(header, "No. Points")
    if count < 2:
        raise ValueError("Insufficient waveform samples")
    flags = _header(header, "Flags").lower().split()
    modes = {flag for flag in flags if flag in {"real", "complex"}}
    if len(modes) != 1:
        raise ValueError("ASCII waveform needs exactly one real or complex Flags mode")
    complex_mode = "complex" in modes

    declared = [line.split() for line in lines[variables_index + 1:values_index] if line.strip()]
    if len(declared) != width:
        raise ValueError("Waveform variable count does not match header")
    names: list[str] = []
    units: list[str] = []
    for index, fields in enumerate(declared):
        if len(fields) < 3 or fields[0] != str(index):
            raise ValueError("Invalid waveform variable index or declaration")
        names.append(fields[1])
        units.append(fields[2])
    if len({name.casefold() for name in names}) != width:
        raise ValueError("Duplicate waveform variable name")
    axis_name: AxisName
    if names[0] == "time" and units[0] == "time":
        axis_name = "time"
    elif names[0] == "frequency" and units[0] == "frequency":
        axis_name = "frequency"
    else:
        raise ValueError("First waveform variable must be the time or frequency axis")
    if expected_axis is not None and axis_name != expected_axis:
        raise ValueError("Waveform analysis does not match the requested case")

    tokens = re.sub(r",\s+", ",", "\n".join(lines[values_index + 1:])).split()
    if len(tokens) != count * (width + 1):
        raise ValueError("Truncated or extra waveform values")
    values: list[list[complex]] = [[] for _ in range(width)]
    for point in range(count):
        offset = point * (width + 1)
        if tokens[offset] != str(point):
            raise ValueError("Invalid waveform point index")
        for variable, token in enumerate(tokens[offset + 1:offset + width + 1]):
            values[variable].append(_sample(token, complex_mode=complex_mode))
    if any(value.imag != 0 for value in values[0]):
        raise ValueError("Waveform axis has a nonzero imaginary component")
    axis = tuple(value.real for value in values[0])
    if axis_name == "time" and axis[0] < 0:
        raise ValueError("Waveform time axis must be nonnegative")
    if axis_name == "frequency" and axis[0] <= 0:
        raise ValueError("Waveform frequency axis must be positive")
    if any(right <= left for left, right in pairwise(axis)):
        raise ValueError("Waveform scale is not strictly increasing")
    return WaveformData(
        axis_name=axis_name,
        axis=axis,
        series=tuple(WaveformSeries(name=names[index], unit=units[index], values=tuple(values[index]))
                     for index in range(1, width)),
    )
