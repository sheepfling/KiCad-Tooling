"""Typed projection of exact native KiCad ERC JSON, including sheet identity."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import cast

from pydantic import JsonValue


@dataclass(frozen=True, slots=True)
class KiCadErcItem:
    """One native ERC detail item and its recorded position."""

    description: str | None
    x: int | float | None
    y: int | float | None


@dataclass(frozen=True, slots=True)
class KiCadErcViolation:
    """One native ERC rule result on an exact schematic sheet occurrence."""

    type: str
    severity: str
    description: str | None
    items: tuple[KiCadErcItem, ...]
    excluded: bool = False
    sheet_path: str = ""
    sheet_uuid_path: str = ""


@dataclass(frozen=True, slots=True)
class KiCadErcReport:
    """Versioned, narrow ERC projection used by checks and review views."""

    kicad_version: str
    violations: tuple[KiCadErcViolation, ...]
    coordinate_units: str = ""
    source: str = ""


def _object(value: JsonValue, label: str) -> dict[str, JsonValue]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")  # noqa: TRY004 - native boundary
    return cast(dict[str, JsonValue], value)


def _list(value: JsonValue, label: str) -> list[JsonValue]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list")  # noqa: TRY004 - native boundary
    return cast(list[JsonValue], value)


def _coordinate(value: JsonValue, label: str) -> int | float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} has an invalid coordinate")  # noqa: TRY004 - native boundary
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"{label} has a non-finite coordinate")
    return value


def parse_native_erc(document: JsonValue) -> KiCadErcReport:
    """Validate the fields needed to retain and place native ERC findings."""
    report = _object(document, "ERC report")
    version = report.get("kicad_version")
    if not isinstance(version, str) or not version.strip():
        raise ValueError("ERC report has no KiCad version")
    raw_units = report.get("coordinate_units", "")
    raw_source = report.get("source", "")
    if not isinstance(raw_units, str) or not isinstance(raw_source, str):
        raise ValueError("ERC report has invalid coordinate units or source")  # noqa: TRY004 - native boundary
    sheets = _list(report.get("sheets"), "ERC report sheets")
    violations: list[KiCadErcViolation] = []
    for sheet_index, raw_sheet in enumerate(sheets):
        label = f"ERC sheet {sheet_index}"
        sheet = _object(raw_sheet, label)
        sheet_path = sheet.get("path", "")
        sheet_uuid_path = sheet.get("uuid_path", "")
        if not isinstance(sheet_path, str) or not isinstance(sheet_uuid_path, str):
            raise ValueError(f"{label} has an invalid sheet path")  # noqa: TRY004 - native boundary
        for finding_index, raw_finding in enumerate(
            _list(sheet.get("violations", []), f"{label} violations")
        ):
            finding_label = f"{label} violation {finding_index}"
            finding = _object(raw_finding, finding_label)
            rule = finding.get("type")
            severity = finding.get("severity")
            description = finding.get("description")
            excluded = finding.get("excluded", False)
            if not isinstance(rule, str) or not rule.strip():
                raise ValueError(f"{finding_label} has no type")
            if not isinstance(severity, str) or not severity.strip():
                raise ValueError(f"{finding_label} has no severity")
            if description is not None and not isinstance(description, str):
                raise ValueError(f"{finding_label} has an invalid description")
            if not isinstance(excluded, bool):
                raise ValueError(f"{finding_label} has an invalid exclusion")  # noqa: TRY004 - native boundary
            items: list[KiCadErcItem] = []
            for item_index, raw_item in enumerate(
                _list(finding.get("items", []), f"{finding_label} items")
            ):
                item_label = f"{finding_label} item {item_index}"
                item = _object(raw_item, item_label)
                item_description = item.get("description")
                if item_description is not None and not isinstance(item_description, str):
                    raise ValueError(f"{item_label} has an invalid description")
                position = _object(item.get("pos", {}), f"{item_label} position")
                items.append(
                    KiCadErcItem(
                        description=item_description,
                        x=_coordinate(position.get("x"), f"{item_label} x"),
                        y=_coordinate(position.get("y"), f"{item_label} y"),
                    )
                )
            violations.append(
                KiCadErcViolation(
                    type=rule,
                    severity=severity,
                    description=description,
                    items=tuple(items),
                    excluded=excluded,
                    sheet_path=sheet_path,
                    sheet_uuid_path=sheet_uuid_path,
                )
            )
    return KiCadErcReport(
        kicad_version=version,
        violations=tuple(violations),
        coordinate_units=raw_units,
        source=raw_source,
    )
