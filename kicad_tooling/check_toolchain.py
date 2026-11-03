"""Fail before editing when the locally installed KiCad does not match the approved toolchain."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .hwrepo.layout import default_project_root
from .hwrepo.models import ToolchainAssessment
from .hwrepo.native_toolchain import (
    MACOS_KICAD_CLI,
    assessment,
    cli_executable,
    observed_version,
    toolchain,
)
from .hwrepo.project_models import ToolchainRecord

__all__ = [
    "MACOS_KICAD_CLI",
    "ToolchainAssessment",
    "ToolchainRecord",
    "assessment",
    "cli_executable",
    "observed_version",
    "toolchain",
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=default_project_root())
    parser.add_argument(
        "--toolchain", help="Catalogued ID; may be omitted only for a single toolchain"
    )
    parser.add_argument(
        "--cli",
        default="kicad-cli",
        help="KiCad CLI command or path (relative paths use the caller's cwd)",
    )
    args = parser.parse_args()
    try:
        record = toolchain(args.root.resolve(), args.toolchain)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    result = assessment(record, observed_version(args.cli))
    print(result.model_dump_json(indent=2))
    return 0 if result.status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
