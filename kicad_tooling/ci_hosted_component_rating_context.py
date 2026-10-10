"""Shared typed context for component-rating native fixture checks."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .hwrepo.models import ProjectConfig


@dataclass(frozen=True)
class ComponentRatingFixtureContext:
    """Paths and reviewed project toolchain for one component-rating lane run."""

    root: Path
    project: str
    config: ProjectConfig
    pinned: str
    fixture_root: Path
    fixture: Path
    fixture_sha256: str
    power_fixture: Path
    power_fixture_sha256: str
    contact_fixture: Path
    contact_fixture_sha256: str
    mosfet_fixture_root: Path
    mosfet_fixture: Path
    mosfet_fixture_sha256: str
    scratch: Path
    output: Path
