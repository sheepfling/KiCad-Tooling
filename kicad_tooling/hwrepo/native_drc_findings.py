"""Typed projection of native KiCad DRC findings for visual review."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import cast

from pydantic import JsonValue


@dataclass(frozen=True, slots=True)
class NativeDrcItem:
    description: str
    x_mm: float | None
    y_mm: float | None


@dataclass(frozen=True, slots=True)
class NativeDrcFinding:
    category: str
    rule: str
    severity: str
    description: str
    excluded: bool
    items: tuple[NativeDrcItem, ...]


@dataclass(frozen=True, slots=True)
class NativeDrcReport:
    version: str
    source: str
    units: str
    findings: tuple[NativeDrcFinding, ...]


def _object(value: JsonValue, label: str) -> dict[str, JsonValue]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")  # noqa: TRY004
    return cast(dict[str, JsonValue], value)


def _list(value: JsonValue, label: str) -> list[JsonValue]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list")  # noqa: TRY004
    return cast(list[JsonValue], value)


def _text(value: JsonValue, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be nonempty text")
    return value


def _coordinate(value: JsonValue, label: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{label} must be a finite number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{label} must be a finite number")
    return number


def parse_native_drc(document: JsonValue) -> NativeDrcReport:
    """Convert the shared JSON boundary's decoded document to narrow typed records."""
    payload = _object(document, "DRC report")
    findings: list[NativeDrcFinding] = []
    for category in ("violations", "unconnected_items", "schematic_parity"):
        rows = _list(payload.get(category, []), f"DRC {category}")
        for row in rows:
            data = _object(row, "DRC finding")
            raw_excluded = data.get("excluded", False)
            if not isinstance(raw_excluded, bool):
                raise TypeError("DRC exclusion must be boolean")
            items: list[NativeDrcItem] = []
            for raw_item in _list(data.get("items", []), "DRC finding items"):
                item = _object(raw_item, "DRC finding item")
                position = _object(item.get("pos", {}), "DRC item position")
                description = item.get("description", "")
                if not isinstance(description, str):
                    raise TypeError("DRC item description must be text")
                items.append(
                    NativeDrcItem(
                        description=description,
                        x_mm=_coordinate(position.get("x"), "DRC x"),
                        y_mm=_coordinate(position.get("y"), "DRC y"),
                    )
                )
            findings.append(
                NativeDrcFinding(
                    category=category,
                    rule=_text(data.get("type"), "DRC rule"),
                    severity=_text(data.get("severity"), "DRC severity"),
                    description=_text(data.get("description"), "DRC description"),
                    excluded=raw_excluded,
                    items=tuple(items),
                )
            )
    return NativeDrcReport(
        version=_text(payload.get("kicad_version"), "DRC version"),
        source=_text(payload.get("source"), "DRC source"),
        units=_text(payload.get("coordinate_units"), "DRC coordinate units"),
        findings=tuple(findings),
    )
