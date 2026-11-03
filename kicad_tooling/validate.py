"""Fail-closed synthetic KiCad check; this is not hardware approval."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .hwrepo.layout import default_project_root
from .hwrepo.models import ValidationSummary
from .hwrepo.native_command import execute, svg_files, write_native_bom
from .hwrepo.native_project_validation import ValidationContract, validate_project
from .hwrepo.native_project_validation_models import NativeProjectValidationRequest
from .hwrepo.native_report_parsing import (
    check_netlist,
    check_report,
    native_report_examples,
    read_netlist,
)
from .hwrepo.project_source_hashes import hash_project_sources as hashes
from .hwrepo.project_source_hashes import is_local_kicad_state as local_state

__all__ = [
    "ValidationContract",
    "ValidationSummary",
    "check_netlist",
    "check_report",
    "execute",
    "hashes",
    "local_state",
    "native_report_examples",
    "read_netlist",
    "svg_files",
    "validate",
    "write_native_bom",
]


def validate(
    root: Path, output: Path, cli: str, config_path: Path | None = None
) -> ValidationSummary:
    """Compatibility adapter to the typed native project validation service."""
    return validate_project(
        root,
        NativeProjectValidationRequest(output=output, cli=cli, config_path=config_path),
    )


def main() -> int:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=default_project_root())
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--cli",
        default="kicad-cli",
        help="KiCad CLI command or path (relative paths use the caller's cwd)",
    )
    parser.add_argument(
        "--config", type=Path, default=Path("examples/projects/controller/project.json")
    )
    args: argparse.Namespace = parser.parse_args()
    summary = validate(args.root.resolve(), args.output.resolve(), args.cli, args.config)
    print(summary.model_dump_json(indent=2))
    return 0 if summary.status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
