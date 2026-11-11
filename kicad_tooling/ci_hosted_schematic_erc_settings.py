"""Coordinate exact-version native lanes for saved schematic ERC settings."""

from __future__ import annotations

from pathlib import Path

from .ci_hosted_schematic_erc_exclusions import schematic_erc_exclusion_fixture_lane
from .ci_hosted_schematic_erc_global_severity import (
    schematic_erc_global_severity_fixture_lane,
)
from .ci_hosted_support import HostedLog


def schematic_erc_settings_fixture_lane(
    root: Path, *, project: str, image: str, log: HostedLog
) -> None:
    """Run each focused native check for persisted ERC project settings."""
    schematic_erc_exclusion_fixture_lane(root, project=project, image=image, log=log)
    schematic_erc_global_severity_fixture_lane(root, project=project, image=image, log=log)
