"""Review board-mesh margins to a project-authored enclosure free-space box."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .hwrepo.assembly_clearance import build_assembly_clearance
from .hwrepo.layout import default_project_root


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=default_project_root())
    parser.add_argument("--project", required=True)
    parser.add_argument("--board-receipt", type=Path, required=True)
    parser.add_argument("--placement-contract", type=Path, required=True)
    parser.add_argument("--clearance-contract", type=Path, required=True)
    parser.add_argument("--output", type=Path, help="Fresh ignored build/ directory")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    try:
        report = build_assembly_clearance(
            args.root,
            args.project,
            args.board_receipt,
            args.placement_contract,
            args.clearance_contract,
            args.output,
        )
    except (OSError, ValueError, TypeError) as exc:
        print(f"Assembly clearance review could not finish: {exc}", file=sys.stderr)
        return 2
    if args.format == "json":
        print(report.model_dump_json(indent=2))
    else:
        print(f"Assembly clearance review: {report.status}")
        if report.minimum_margin_mm is not None:
            print(f"Minimum signed face margin: {report.minimum_margin_mm:.4f} mm")
        if report.surface_gap_mm is not None:
            print(f"Board/enclosure surface gap: {report.surface_gap_mm:.4f} mm")
        else:
            print("Board/enclosure surface gap: unassessed")
        print(f"Open: {report.output_directory}/index.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
