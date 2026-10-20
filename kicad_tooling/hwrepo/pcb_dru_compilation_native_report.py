"""Decode the narrow native DRC evidence needed by the sentinel probe."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

PROBE_BOARD_NAME = "pcb-dru-rule-compilation-probe.kicad_pcb"


def native_identity_and_matches(report_path: Path, sentinel_name: str) -> tuple[str, int]:
    """Validate report identity and count active terminal-sentinel violations."""
    raw: object = json.loads(report_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise TypeError("Native sentinel DRC report root must be an object")
    payload = cast(dict[str, object], raw)
    version = payload.get("kicad_version")
    source = payload.get("source")
    violations = payload.get("violations")
    if not isinstance(version, str) or not version.strip():
        raise TypeError("Native sentinel DRC report has no KiCad version")
    if not isinstance(source, str) or Path(source).name != PROBE_BOARD_NAME:
        raise TypeError("Native sentinel DRC report does not identify the synthetic probe board")
    if not isinstance(violations, list):
        raise TypeError("Native sentinel DRC report violations must be a list")

    matches = 0
    for index, raw_violation in enumerate(cast(list[object], violations)):
        if not isinstance(raw_violation, dict):
            raise TypeError(f"Native sentinel DRC violation {index} must be an object")
        violation = cast(dict[str, object], raw_violation)
        description = violation.get("description")
        if (
            violation.get("type") == "clearance"
            and violation.get("severity") == "error"
            and violation.get("excluded") is not True
            and isinstance(description, str)
            and sentinel_name in description
        ):
            matches += 1
    return version, matches
