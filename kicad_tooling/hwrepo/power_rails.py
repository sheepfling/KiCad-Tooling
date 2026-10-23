"""Conservative review hints for separately numbered positive supply nets."""

from __future__ import annotations

import re
from decimal import Decimal

from .models import NetlistContract
from .power_rail_models import NumberedPowerRailGroup

_NUMBERED_RAIL = re.compile(r"^(?P<stem>.+?)[\s_./-]+(?P<index>\d+)$")
_CHANNEL_NUMBERED_RAIL = re.compile(
    r"^(?P<namespace>P|CH|RAIL)[\s_./-]*(?P<index>\d+)[\s_./-]+(?P<stem>.+)$",
    re.IGNORECASE,
)
_RAIL_STEMS = {
    "pwr": "PWR",
    "power": "PWR",
    "supply": "SUPPLY",
    "vsupply": "SUPPLY",
    "vin": "VIN",
    "vcc": "VCC",
    "vdd": "VDD",
    "vdda": "VDDA",
    "vddd": "VDDD",
    "vddio": "VDDIO",
    "vccio": "VCCIO",
    "vbus": "VBUS",
    "vbat": "VBAT",
    "vraw": "VRAW",
    "vreg": "VREG",
    "5v": "5V",
    "5.0v": "5V",
    "3v3": "3V3",
    "3.3v": "3V3",
    "1v8": "1V8",
    "1.8v": "1V8",
    "2v5": "2V5",
    "2.5v": "2V5",
    "9v": "9V",
    "12v": "12V",
    "24v": "24V",
    "48v": "48V",
}

_EXPLICIT_VOLTAGE_RAIL_KEYS = frozenset({"1V8", "2V5", "3V3", "5V", "9V", "12V", "24V", "48V"})
_EXPLICIT_VOLTAGE_RAIL_VALUES = {
    "1V8": Decimal("1.8"),
    "2V5": Decimal("2.5"),
    "3V3": Decimal("3.3"),
    "5V": Decimal(5),
    "9V": Decimal(9),
    "12V": Decimal(12),
    "24V": Decimal(24),
    "48V": Decimal(48),
}


def _numbered_positive_rail(name: str) -> tuple[str, int] | None:
    match = _NUMBERED_RAIL.fullmatch(name)
    if match is not None:
        stem = match.group("stem").strip()
        if stem.startswith("-"):
            return None
        canonical_stem = _RAIL_STEMS.get(stem.removeprefix("+").casefold())
        if canonical_stem is not None:
            return canonical_stem, int(match.group("index"))

    match = _CHANNEL_NUMBERED_RAIL.fullmatch(name)
    if match is None:
        return None
    stem = match.group("stem").strip()
    if stem.startswith("-"):
        return None
    canonical_stem = _RAIL_STEMS.get(stem.removeprefix("+").casefold())
    if canonical_stem is None:
        return None
    namespace = match.group("namespace").upper()
    return f"{namespace} {canonical_stem}", int(match.group("index"))


def explicit_voltage_rail_value(name: str) -> Decimal | None:
    """Read a signed value from a narrowly recognized numeric rail spelling.

    Only the explicit numeric rails already present in ``_RAIL_STEMS`` are
    recognized. The label is evidence for review, not proof of potential.
    """
    compact = re.sub(r"\s+", "", name).casefold()
    sign = Decimal(1)
    if compact.startswith(("+", "-")):
        if compact.startswith(("++", "+-", "--", "-+")):
            return None
        if compact.startswith("-"):
            sign = Decimal(-1)
        compact = compact[1:]
    canonical = _RAIL_STEMS.get(compact)
    magnitude = _EXPLICIT_VOLTAGE_RAIL_VALUES.get(canonical or "")
    return None if magnitude is None else sign * magnitude


def negative_voltage_rail_key(name: str) -> str | None:
    """Return a narrow key for a net label explicitly prefixed with minus.

    This recognizes only numeric voltage rail spellings already known to the
    positive-rail vocabulary. The leading sign is evidence in the label, not
    proof of the net's electrical potential.
    """
    value = explicit_voltage_rail_value(name)
    if value is None or value >= 0:
        return None
    compact = re.sub(r"\s+", "", name).casefold()[1:]
    canonical = _RAIL_STEMS.get(compact)
    return canonical if canonical in _EXPLICIT_VOLTAGE_RAIL_KEYS else None


def numbered_power_rail_groups(
    observed: NetlistContract,
) -> tuple[NumberedPowerRailGroup, ...]:
    """Find separately numbered supply-like nets without inferring a required tie."""
    grouped: dict[str, list[tuple[str, int]]] = {}
    for name in sorted(observed.nets):
        indexed = _numbered_positive_rail(name)
        if indexed is None:
            continue
        stem, index = indexed
        grouped.setdefault(stem, []).append((name, index))
    return tuple(
        NumberedPowerRailGroup(
            stem=stem,
            nets={name: observed.nets[name] for name, _ in entries},
        )
        for stem, entries in sorted(grouped.items())
        if len({index for _, index in entries}) > 1
    )
