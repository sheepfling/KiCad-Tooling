"""Explicit adapter selection for the KiCad CLI and report formats we understand."""

from __future__ import annotations

from typing import Literal

from .models import ProjectConfig, ToolchainRecord

KiCadCliProfile = Literal["kicad-10"]


def require_cli_profile(config: ProjectConfig | ToolchainRecord) -> KiCadCliProfile:
    """Select a command/report contract, never certify an untested KiCad build.

    Existing 10.x catalogs keep their default behavior. Another major version
    needs the repository author's explicit compatibility declaration before
    native commands run. Exact version and image checks remain independent.
    """
    if config.cli_profile is not None:
        return config.cli_profile
    if config.kicad_version.split(".", 1)[0] == "10":
        return "kicad-10"
    raise ValueError(
        f"KiCad {config.kicad_version} has no declared CLI compatibility profile. "
        'After reviewing its commands and report formats, set cli_profile to "kicad-10" '
        "in the toolchain record only if compatible; otherwise add a tooling adapter. "
        "Run the native acceptance lanes for that exact version before adopting it. "
        "Portable checks remain available."
    )
