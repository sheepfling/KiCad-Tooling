"""Shared setup and event assertions for digest-pinned native PCB fixture lanes."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from kicad_tooling.ci_hosted import HostedLog
from tests.support import reference_root

NATIVE_KICAD_PROJECTS = (
    ("controller", "10.0.0"),
    ("raspberry-pi-status-led", "10.0.5"),
)


def copy_reference_checkout(destination: Path) -> Path:
    """Copy a caller-supplied public template checkout into isolated test storage."""
    shutil.copytree(
        reference_root(),
        destination,
        ignore=shutil.ignore_patterns(".git", "build", "__pycache__"),
    )
    return destination


def lane_event(log: HostedLog, stage: str) -> dict[str, Any]:
    events = tuple(json.loads(line) for line in log.events.read_text(encoding="utf-8").splitlines())
    matches = tuple(item for item in events if item.get("stage") == stage)
    assert len(matches) == 1
    return matches[0]
