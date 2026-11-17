"""Read plating and X2 metadata from fabrication drill files."""

from __future__ import annotations

import re
from pathlib import Path

from .fabrication_artwork import UnsupportedFabricationFormat


def drill_file_is_plated(path: Path) -> bool:
    """Classify KiCad PTH/NPTH drill outputs without relying on file order."""
    name = path.name.casefold()
    text = path.read_text(encoding="utf-8", errors="replace")[:4000].casefold()
    function = drill_file_function(path)
    if function is not None:
        if function[0] == "plated":
            return True
        if function[0] == "nonplated":
            return False
        raise UnsupportedFabricationFormat(f"unknown drill plating in {path.name} FileFunction")
    if "nonplated" in text or "non-plated" in text or "npth" in name:
        return False
    if "plated" in text or "pth" in name:
        return True
    raise UnsupportedFabricationFormat(f"cannot determine drill plating for {path.name}")


def drill_file_function(path: Path) -> tuple[str, ...] | None:
    """Read one KiCad X2 drill FileFunction attribute when present."""
    text = path.read_text(encoding="utf-8", errors="replace")[:4000]
    matches = re.findall(r"TF\.FileFunction,([^*%\r\n]+)", text, flags=re.IGNORECASE)
    if not matches:
        return None
    if len(matches) != 1:
        raise UnsupportedFabricationFormat(
            f"drill file has multiple FileFunction attributes in {path.name}"
        )
    fields = tuple(field.strip().casefold() for field in matches[0].split(","))
    if not fields or any(not field for field in fields):
        raise UnsupportedFabricationFormat(f"malformed drill FileFunction in {path.name}")
    return fields
