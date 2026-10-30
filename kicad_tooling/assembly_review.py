"""Review a retained board and explicitly positioned adjacent GLB offline."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .hwrepo.assembly_review import build_assembly_review
from .hwrepo.layout import default_project_root


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=default_project_root())
    parser.add_argument("--project", required=True)
    parser.add_argument("--board-receipt", type=Path, required=True)
    parser.add_argument("--placement-contract", type=Path, required=True)
    parser.add_argument("--output", type=Path, help="Fresh directory under ignored build/")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    try:
        report = build_assembly_review(
            args.root, args.project, args.board_receipt, args.placement_contract, args.output
        )
    except (OSError, ValueError) as exc:
        print(f"Mechanical assembly review could not finish: {exc}", file=sys.stderr)
        return 2
    if args.format == "json":
        print(report.model_dump_json(indent=2))
    else:
        print(f"Mechanical assembly review: {report.status}")
        print(f"Receipt: {report.output_directory}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
